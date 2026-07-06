#!/usr/bin/env python3
"""Phase 3 follow-up — re-score the v3 attack classifier at *cluster*
granularity instead of per-technique.

Motivation
----------
The v3 XGBoost (sklearn HistGradientBoosting) classifier reports 64.5 % LOIO
top-1 accuracy across 26 classes, but 6 classes are "DEAD" (F1 ~ 0): their
telemetry signatures are not separable from a sibling technique in the
894-feature v5 space (e.g. EX-0012.04 ≡ EX-0012.03, EX-0014.01 ≡ EX-0012.12).
Asking the model to pick the exact sub-technique is then a coin-flip that
*understates* operational usefulness: "propulsion-command-class attack" is a
correct and actionable verdict even when ".03 vs .04" is not recoverable.

This script reconstructs the v3 LOIO evaluation EXACTLY (same 3 instances, same
894-feature recipe, same hyper-parameters read from the deployed pickle), then:

  1. Runs leave-one-instance-out (LOIO); collects per-frame (y_true, y_pred).
  2. Reports technique-level accuracy / macro-F1 (should reproduce ~0.645).
  3. Builds the summed attack-vs-attack confusion matrix.
  4. Derives telemetry-indistinguishable CLUSTERS as connected components of
     the "mutually/heavily confused" graph (nominal excluded from merges —
     an attack predicted nominal is a *detection* miss, not a sibling
     ambiguity).
  5. Re-maps both y_true and y_pred through the cluster map and recomputes
     accuracy / macro-F1 — the SAME model, a coarser read-out. No retraining.

Outputs (to --out-dir):
  - cluster_taxonomy.json   : clusters, members, representatives, rationale,
                              technique-level vs cluster-level metrics.
  - confusion_attack.csv    : summed row-normalized attack-vs-attack confusion.
  - cluster_rescore_report.md

Usage:
    python3 components/onair/training/eval_classifier_clusters.py \\
        --csv-dir data/onair/csv \\
        --manifest-dir data/onair/scenarios \\
        --classifier data/onair/models/xgb_attack_classifier_v3.pkl \\
        --out-dir data/onair/models/cluster_rescore
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import pickle
import sys
import time
from collections import defaultdict

import numpy as np

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from loader import load_with_labels       # noqa: E402
from features import build_features        # noqa: E402

# The three v3 corpus instances live on these session dates. batch1/batch2 of
# 2026-05-29 split across the midnight boundary into 2026-05-30, so we restrict
# to these dates and re-discover the batches by a time gap.
V3_DATES = ("2026-05-16", "2026-05-29", "2026-05-30")
BATCH_GAP_MIN = 90          # >90 min idle between sessions ⇒ new batch
MIN_ATTACK_MANIFESTS = 5    # a real instance has many attack manifests

# Known telemetry-identical pairs documented during attack-footprint
# validation (memory: attack-footprint-validation-wave2). Forced into the same
# cluster even if a given LOIO confusion happens to fall below threshold.
DOMAIN_IDENTICAL_PAIRS = [
    ("EX-0014.01", "EX-0012.12"),
    ("EX-0012.03", "EX-0012.04"),
]


def _session_ts(sid: str) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(sid, "%Y-%m-%dT%H-%M-%SZ")
    except ValueError:
        return None


def discover_instances(manifest_dir: str) -> list[list[str]]:
    """Return a list of instances; each instance is a list of manifest paths.

    Restricts to the v3 corpus dates, drops soak/dryrun manifests, then splits
    the time-ordered attack manifests into batches on >BATCH_GAP_MIN idle gaps.
    """
    recs: list[tuple[dt.datetime, str, int]] = []
    for p in sorted(glob.glob(os.path.join(manifest_dir, "manifest_*.json"))):
        b = os.path.basename(p)
        if "_dryrun" in b or "soak" in b:
            continue
        try:
            m = json.load(open(p))
        except (OSError, json.JSONDecodeError):
            continue
        sid = m.get("session_id", "")
        if sid[:10] not in V3_DATES:
            continue
        ts = _session_ts(sid)
        if ts is None:
            continue
        recs.append((ts, p, len(m.get("attacks", []))))
    recs.sort(key=lambda r: r[0])

    batches: list[list[tuple[dt.datetime, str, int]]] = []
    cur: list[tuple[dt.datetime, str, int]] = []
    prev: dt.datetime | None = None
    for ts, p, na in recs:
        if prev and (ts - prev).total_seconds() > BATCH_GAP_MIN * 60:
            batches.append(cur)
            cur = []
        cur.append((ts, p, na))
        prev = ts
    if cur:
        batches.append(cur)

    instances: list[list[str]] = []
    for bt in batches:
        n_attack = sum(1 for _, _, na in bt if na > 0)
        if n_attack >= MIN_ATTACK_MANIFESTS:
            instances.append([p for _, p, _ in bt])
    return instances


def frame_labels(df) -> np.ndarray:
    """Per-row class label: the attack id inside the corruption window, else
    'nominal'. Mirrors the v3 training label convention."""
    attack_id = df["__attack_id"].fillna("").astype(str).to_numpy()
    in_corr = df["__corruption_window"].astype(bool).to_numpy()
    y = np.where(in_corr & (attack_id != ""), attack_id, "nominal")
    return y.astype(object)


def load_instance(csv_dir: str, manifests: list[str], schema: dict,
                  allowed_labels: set[str] | None = None):
    """Load one instance, build the 894-feature matrix + per-frame labels.

    __file_id is retained through build_features so deltas are masked at file
    boundaries (matching the runtime plugin's per-process prev_raw reset).

    If `allowed_labels` is given, rows whose label is outside that set are
    dropped *after* feature-building (so deltas stay intact across the full
    contiguous stream). v3 trained on 26 labels — it excludes the CONCEPTUAL
    no-op / UNSUBSCRIBED attacks that emit no distinct telemetry; restricting
    here makes this a faithful re-score of the deployed model."""
    df, _ = load_with_labels(csv_dir=csv_dir, manifest=manifests,
                             drop_unlabeled=True, skip_warmup_rows=30)
    y = frame_labels(df)
    # Per-frame metadata, aligned to X/y rows, so the out-of-fold predictions can
    # later drive incident aggregation keyed by (file_id, row_idx) (NOS3-302).
    meta = {
        "file_id": df["__file_id"].astype(str).to_numpy(),
        "row_idx": df["__row_idx"].to_numpy().astype(np.int64),
        "adcs_mode": df["__adcs_mode"].astype(str).to_numpy(),
        "in_corruption": df["__corruption_window"].astype(bool).to_numpy(),
        "attack_id": df["__attack_id"].fillna("").astype(str).to_numpy(),
    }
    # Keep __file_id for boundary masking; build_features ignores non-schema cols.
    drop = [c for c in df.columns if c.startswith("__") and c != "__file_id"]
    X, _ = build_features(df.drop(columns=drop), include_deltas=True, schema=schema)
    if allowed_labels is not None:
        keep = np.array([lbl in allowed_labels for lbl in y], dtype=bool)
        dropped_ids = sorted(set(y[~keep]) - {""})
        if dropped_ids:
            print(f"  restricting to classifier label set: dropped "
                  f"{int((~keep).sum())} rows of out-of-set classes {dropped_ids}")
        X, y = X[keep], y[keep]
        meta = {k: v[keep] for k, v in meta.items()}
    return X, y, meta


def make_clf(hp: dict):
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(
        max_iter=hp.get("max_iter", 300),
        learning_rate=hp.get("learning_rate", 0.1),
        max_depth=hp.get("max_depth", 8),
        max_leaf_nodes=hp.get("max_leaf_nodes", 31),
        min_samples_leaf=hp.get("min_samples_leaf", 20),
        l2_regularization=hp.get("l2_regularization", 0.0),
        early_stopping=False,
        class_weight="balanced",
        random_state=42,
        max_bins=hp.get("max_bins", 255),
    )


def per_class_f1(y_true, y_pred, labels):
    from sklearn.metrics import f1_score
    f1 = f1_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    return dict(zip(labels, f1))


def derive_clusters(conf_counts: dict, labels: list[str], tau: float,
                    mutual: bool = True):
    """Connected-components clustering of attack classes.

    conf_counts[(a, b)] = number of frames with true=a, pred=b (summed over
    folds). C[a->b] = conf_counts[a,b] / support(a).

    Edge rule:
      - mutual=True  (default): a~b iff min(C[a->b], C[b->a]) >= tau. This is
        *genuine indistinguishability* — each class's frames land on the other.
        It deliberately does NOT merge a rare DEAD class that merely dumps onto
        a robust class one-way (e.g. DE-0003.06 -> EX-0008.02), which would
        wrongly pollute a reliably-classified technique.
      - mutual=False: a~b iff max(C[a->b], C[b->a]) >= tau (absorption).

    Nominal is excluded. Known domain-identical pairs are force-merged.
    """
    support = defaultdict(int)
    for (a, _b), c in conf_counts.items():
        support[a] += c
    attacks = [l for l in labels if l != "nominal"]

    # Union-Find
    parent = {a: a for a in attacks}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    edges = []
    for a in attacks:
        for b in attacks:
            if a == b:
                continue
            sa = support.get(a, 0)
            sb = support.get(b, 0)
            cab = conf_counts.get((a, b), 0) / sa if sa else 0.0
            cba = conf_counts.get((b, a), 0) / sb if sb else 0.0
            link = (min(cab, cba) >= tau) if mutual else (max(cab, cba) >= tau)
            if link:
                union(a, b)
                edges.append((a, b, round(cab, 3), round(cba, 3)))
    for a, b in DOMAIN_IDENTICAL_PAIRS:
        if a in parent and b in parent:
            union(a, b)

    groups = defaultdict(list)
    for a in attacks:
        groups[find(a)].append(a)

    clusters = {}
    for members in groups.values():
        members = sorted(members)
        rep = _representative(members)
        clusters[rep] = sorted(members)
    return clusters, edges


def _representative(members: list[str]) -> str:
    """Name a cluster. Singletons keep their id. Multi-member clusters get a
    '<common-prefix>.{a,b,...}' label when they share a SPARTA technique prefix,
    else a '/'-joined label."""
    if len(members) == 1:
        return members[0]
    prefixes = {m.rsplit(".", 1)[0] for m in members if "." in m}
    if len(prefixes) == 1:
        base = next(iter(prefixes))
        subs = sorted(m.rsplit(".", 1)[1] for m in members if "." in m)
        return f"{base}.{{{','.join(subs)}}}"
    return "/".join(members)


def map_to_cluster(labels_arr, clusters: dict):
    member_to_rep = {}
    for rep, members in clusters.items():
        for m in members:
            member_to_rep[m] = rep
    return np.array([member_to_rep.get(l, l) for l in labels_arr], dtype=object)


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv-dir", default="data/onair/csv")
    p.add_argument("--manifest-dir", default="data/onair/scenarios")
    p.add_argument("--classifier",
                   default="data/onair/models/xgb_attack_classifier_v3.pkl",
                   help="deployed v3 pickle — source of schema + hyper-params")
    p.add_argument("--out-dir", default="data/onair/models/cluster_rescore")
    p.add_argument("--tau", type=float, default=0.30,
                   help="confusion fraction at/above which two attack classes "
                        "are judged telemetry-indistinguishable")
    args = p.parse_args()

    t0 = time.time()
    os.makedirs(args.out_dir, exist_ok=True)

    # ─── recipe from the deployed v3 pickle ────────────────────────────
    with open(args.classifier, "rb") as f:
        v3 = pickle.load(f)
    schema = v3["schema"]
    hp = v3["clf"].get_params()
    allowed_labels = set(v3["labels"])
    n_feat = len(schema.get("feature_names", []))
    print(f"restricting eval to v3's {len(allowed_labels)} labels")
    print(f"v3 recipe: {n_feat} features, max_iter={hp['max_iter']}, "
          f"max_depth={hp['max_depth']}, class_weight={hp['class_weight']}")

    # ─── discover the 3 instances ──────────────────────────────────────
    instances = discover_instances(args.manifest_dir)
    print(f"discovered {len(instances)} instances: "
          f"{[len(m) for m in instances]} manifests each")
    if len(instances) < 2:
        sys.exit("need >= 2 instances for LOIO")

    # ─── load + featurize each instance once ───────────────────────────
    data = []
    for i, manifests in enumerate(instances):
        print(f"\n=== instance {i} ({len(manifests)} manifests) ===")
        X, y, meta = load_instance(args.csv_dir, manifests, schema, allowed_labels)
        assert X.shape[1] == n_feat, f"feature mismatch {X.shape[1]} != {n_feat}"
        print(f"  X={X.shape}  classes={len(set(y))}  "
              f"attack_rows={(y != 'nominal').sum()}  nominal_rows={(y == 'nominal').sum()}")
        data.append((X, y, meta))

    labels = sorted(set().union(*[set(y) for _, y, _ in data]))
    print(f"\nglobal label space: {len(labels)} classes")

    # ─── LOIO ──────────────────────────────────────────────────────────
    from sklearn.metrics import accuracy_score, f1_score
    conf_counts: dict = defaultdict(int)
    fold_tech_acc = []
    per_fold_f1: list[dict] = []
    all_true: list = []
    all_pred: list = []
    all_conf: list = []
    meta_keys = ("file_id", "row_idx", "adcs_mode", "in_corruption", "attack_id")
    all_meta: dict = {k: [] for k in meta_keys}

    for held in range(len(data)):
        Xtr = np.vstack([data[j][0] for j in range(len(data)) if j != held])
        ytr = np.concatenate([data[j][1] for j in range(len(data)) if j != held])
        Xte, yte, mte = data[held]
        t1 = time.time()
        clf = make_clf(hp)
        clf.fit(Xtr, ytr)
        # predict_proba (not predict) so we keep the top-1 confidence for the
        # out-of-fold incident aggregation; argmax of proba == predict().
        proba = clf.predict_proba(Xte)
        am = proba.argmax(axis=1)
        ypred = clf.classes_[am]
        conf = proba[np.arange(len(am)), am]
        acc = accuracy_score(yte, ypred)
        fold_tech_acc.append(acc)
        per_fold_f1.append(per_class_f1(yte, ypred, labels))
        all_true.append(yte)
        all_pred.append(ypred)
        all_conf.append(conf)
        for k in meta_keys:
            all_meta[k].append(mte[k])
        for t, pr in zip(yte, ypred):
            conf_counts[(t, pr)] += 1
        print(f"  fold held={held}: train={len(ytr)} test={len(yte)} "
              f"acc={acc:.4f} ({time.time()-t1:.0f}s)")

    # Persist raw per-fold predictions so tau / cluster-rule sweeps need no
    # retrain — recluster_from_cache.py loads y_true/y_pred/fold_of_row/labels.
    # The file_id/row_idx/mode/corruption/attack_id/confidence columns are the
    # out-of-fold record NOS3-302's incident rescore joins on (file_id, row_idx).
    np.savez(
        os.path.join(args.out_dir, "loio_predictions.npz"),
        fold_held=np.array(list(range(len(data)))),
        y_true=np.concatenate(all_true).astype(str),
        y_pred=np.concatenate(all_pred).astype(str),
        confidence=np.concatenate(all_conf).astype(np.float64),
        fold_of_row=np.concatenate([
            np.full(len(all_true[h]), h) for h in range(len(data))]),
        file_id=np.concatenate(all_meta["file_id"]).astype(str),
        row_idx=np.concatenate(all_meta["row_idx"]).astype(np.int64),
        adcs_mode=np.concatenate(all_meta["adcs_mode"]).astype(str),
        in_corruption=np.concatenate(all_meta["in_corruption"]).astype(bool),
        attack_id=np.concatenate(all_meta["attack_id"]).astype(str),
        labels=np.array(labels, dtype=str),
        provenance_csv_dir=np.array(args.csv_dir),
        provenance_manifest_dir=np.array(args.manifest_dir),
        provenance_skip_warmup_rows=np.array(30),
    )

    tech_acc_mean = float(np.mean(fold_tech_acc))
    tech_acc_std = float(np.std(fold_tech_acc))
    print(f"\nTECHNIQUE-level LOIO: {tech_acc_mean:.4f} ± {tech_acc_std:.4f}  "
          f"folds={[round(a, 4) for a in fold_tech_acc]}")

    # ─── derive clusters from summed attack-vs-attack confusion ─────────
    clusters, edges = derive_clusters(conf_counts, labels, args.tau)
    multi = {r: m for r, m in clusters.items() if len(m) > 1}
    print(f"\nclusters: {len(clusters)} ({len(multi)} multi-member) at tau={args.tau}")
    for rep, members in sorted(multi.items()):
        print(f"  {rep}: {members}")

    # ─── re-score at cluster granularity (same predictions) ────────────
    fold_clu_acc = []
    clu_true_all: list = []
    clu_pred_all: list = []
    for held in range(len(data)):
        yt = map_to_cluster(all_true[held], clusters)
        yp = map_to_cluster(all_pred[held], clusters)
        fold_clu_acc.append(float(accuracy_score(yt, yp)))
        clu_true_all.append(yt)
        clu_pred_all.append(yp)
    clu_acc_mean = float(np.mean(fold_clu_acc))
    clu_acc_std = float(np.std(fold_clu_acc))

    clu_labels = sorted(set().union(*[set(y) for y in clu_true_all]))
    tech_macro_f1 = float(f1_score(
        np.concatenate(all_true), np.concatenate(all_pred),
        labels=labels, average="macro", zero_division=0))
    clu_macro_f1 = float(f1_score(
        np.concatenate(clu_true_all), np.concatenate(clu_pred_all),
        labels=clu_labels, average="macro", zero_division=0))

    print(f"\nCLUSTER-level   LOIO: {clu_acc_mean:.4f} ± {clu_acc_std:.4f}  "
          f"folds={[round(a, 4) for a in fold_clu_acc]}")
    print(f"macro-F1  technique={tech_macro_f1:.4f}  cluster={clu_macro_f1:.4f}")
    print(f"accuracy  lift: {tech_acc_mean:.4f} -> {clu_acc_mean:.4f} "
          f"(+{clu_acc_mean - tech_acc_mean:.4f})")

    # ─── per-class / per-cluster F1 (mean over folds) ──────────────────
    def mean_f1(per_fold, keys):
        out = {}
        for k in keys:
            vals = [pf.get(k, 0.0) for pf in per_fold]
            out[k] = {"mean_f1": round(float(np.mean(vals)), 3),
                      "std_f1": round(float(np.std(vals)), 3)}
        return out

    tech_f1 = mean_f1(per_fold_f1, labels)
    clu_per_fold = []
    for held in range(len(data)):
        clu_per_fold.append(per_class_f1(clu_true_all[held], clu_pred_all[held], clu_labels))
    clu_f1 = mean_f1(clu_per_fold, clu_labels)

    # ─── write confusion CSV (row-normalized attack-vs-attack) ─────────
    attacks = [l for l in labels if l != "nominal"]
    support = defaultdict(int)
    for (a, _b), c in conf_counts.items():
        support[a] += c
    conf_csv = os.path.join(args.out_dir, "confusion_attack.csv")
    with open(conf_csv, "w") as f:
        f.write("true\\pred," + ",".join(attacks) + "\n")
        for a in attacks:
            sa = support.get(a, 0) or 1
            row = [f"{conf_counts.get((a, b), 0) / sa:.3f}" for b in attacks]
            f.write(a + "," + ",".join(row) + "\n")

    # ─── taxonomy JSON ─────────────────────────────────────────────────
    taxonomy = {
        "generated_utc": None,  # stamped by caller / git; avoid Date.now in-script
        "source_classifier": os.path.basename(args.classifier),
        "n_instances": len(data),
        "instance_manifest_counts": [len(m) for m in instances],
        "tau": args.tau,
        "technique_level": {
            "loio_accuracy_mean": round(tech_acc_mean, 4),
            "loio_accuracy_std": round(tech_acc_std, 4),
            "loio_per_fold": [round(a, 4) for a in fold_tech_acc],
            "macro_f1": round(tech_macro_f1, 4),
            "n_classes": len(labels),
        },
        "cluster_level": {
            "loio_accuracy_mean": round(clu_acc_mean, 4),
            "loio_accuracy_std": round(clu_acc_std, 4),
            "loio_per_fold": [round(a, 4) for a in fold_clu_acc],
            "macro_f1": round(clu_macro_f1, 4),
            "n_clusters": len(clu_labels),
            "accuracy_lift": round(clu_acc_mean - tech_acc_mean, 4),
        },
        "clusters": {rep: members for rep, members in sorted(clusters.items())},
        "multi_member_clusters": {rep: members for rep, members in sorted(multi.items())},
        "merge_edges": [
            {"a": a, "b": b, "C_a_to_b": cab, "C_b_to_a": cba}
            for a, b, cab, cba in edges
        ],
        "domain_forced_pairs": DOMAIN_IDENTICAL_PAIRS,
        "per_class_f1_technique": tech_f1,
        "per_cluster_f1": clu_f1,
    }
    tax_path = os.path.join(args.out_dir, "cluster_taxonomy.json")
    with open(tax_path, "w") as f:
        json.dump(taxonomy, f, indent=2)

    # ─── markdown report ───────────────────────────────────────────────
    md = []
    md.append("# v3 Attack Classifier — Cluster-Granularity Re-score\n")
    md.append(f"Source model: `{os.path.basename(args.classifier)}`  ·  "
              f"instances: {[len(m) for m in instances]}  ·  tau={args.tau}\n")
    md.append("## Headline\n")
    md.append(f"| granularity | LOIO accuracy | macro-F1 | classes |")
    md.append("|---|---|---|---|")
    md.append(f"| technique (26-class) | **{tech_acc_mean:.1%} ± {tech_acc_std:.1%}** "
              f"| {tech_macro_f1:.3f} | {len(labels)} |")
    md.append(f"| cluster | **{clu_acc_mean:.1%} ± {clu_acc_std:.1%}** "
              f"| {clu_macro_f1:.3f} | {len(clu_labels)} |")
    md.append(f"\nAccuracy lift from collapsing telemetry-indistinguishable "
              f"techniques: **+{clu_acc_mean - tech_acc_mean:.1%}** "
              f"(no retraining — same model, coarser read-out).\n")
    md.append("## Multi-member clusters\n")
    md.append("| cluster | members | per-cluster F1 |")
    md.append("|---|---|---|")
    for rep, members in sorted(multi.items()):
        md.append(f"| `{rep}` | {', '.join(members)} | "
                  f"{clu_f1.get(rep, {}).get('mean_f1', '—')} |")
    md.append("\n## Technique-level per-class F1 (mean over LOIO folds)\n")
    md.append("| class | mean F1 | std |")
    md.append("|---|---|---|")
    for l in labels:
        md.append(f"| {l} | {tech_f1[l]['mean_f1']} | {tech_f1[l]['std_f1']} |")
    md_path = os.path.join(args.out_dir, "cluster_rescore_report.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md) + "\n")

    print(f"\nwrote:\n  {tax_path}\n  {conf_csv}\n  {md_path}")
    print(f"total: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
