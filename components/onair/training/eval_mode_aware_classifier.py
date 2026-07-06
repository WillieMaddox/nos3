#!/usr/bin/env python3
"""NOS3-301 — compare mode-aware attack classifiers against the global v3.

NOS3-302 established (frame-level, out-of-fold) that the single global v3
classifier labels far worse in PASSIVE than in the other ADCS modes — and that
this is intrinsic (the *same* technique cluster scores lower in PASSIVE), not a
composition artifact. A single model trained across all modes is dominated by
the dynamic modes and underfits PASSIVE's quiescent telemetry regime.

This harness runs leave-one-instance-out (LOIO) over the FROZEN v3 corpus
(`csv_corpus_v3stage` — see project_v3_corpus_drift) and scores three variants
on identical folds:

  - baseline   : global HistGB on the 894 v5 features (reproduces v3).
  - mode_feat  : baseline + a one-hot ADCS-mode block appended to the features
                 (single model, all data, learns mode-conditional splits).
  - per_mode   : one HistGB head per ADCS mode; each test frame is routed to its
                 mode's head (falls back to the global model for unseen modes).

For each variant it reports overall LOIO accuracy and — the metric that matters
for this ticket — per-mode cluster accuracy on attack frames, plus the ROBUST
tier accuracy (the no-regression guard).

Usage:
    python3 components/onair/training/eval_mode_aware_classifier.py \\
        --csv-dir data/onair/csv_corpus_v3stage \\
        --manifest-dir data/onair/scenarios \\
        --classifier data/onair/models/xgb_attack_classifier_v3.pkl \\
        --taxonomy data/onair/models/cluster_rescore/cluster_taxonomy.json \\
        --out data/onair/models/mode_aware/mode_aware_eval.json
    # fast path-check first:
    #   ... --smoke 4000 --max-iter 40 --out /tmp/ma_smoke.json
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time
from collections import defaultdict

import numpy as np

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from eval_classifier_clusters import (   # noqa: E402
    discover_instances, load_instance, make_clf, map_to_cluster)

# ROBUST tier (V5_DETECTOR_COVERAGE.md §4) — the no-regression guard.
ROBUST_CLUSTERS = {"EX-0008.02", "IMP-0005", "DE-0003.01", "DE-0003.10"}


def onehot_modes(mode_arr, mode_index):
    """(n,) string modes → (n, n_modes) float32 one-hot via a fixed index."""
    oh = np.zeros((len(mode_arr), len(mode_index)), dtype=np.float32)
    for i, m in enumerate(mode_arr):
        j = mode_index.get(m)
        if j is not None:
            oh[i, j] = 1.0
    return oh


def fit_predict_baseline(Xtr, ytr, Xte, hp):
    clf = make_clf(hp)
    clf.fit(Xtr, ytr)
    return clf.predict(Xte)


def fit_predict_modefeat(Xtr, ytr, mtr, Xte, mte, hp, mode_index):
    Xtr2 = np.hstack([Xtr, onehot_modes(mtr, mode_index)])
    Xte2 = np.hstack([Xte, onehot_modes(mte, mode_index)])
    clf = make_clf(hp)
    clf.fit(Xtr2, ytr)
    return clf.predict(Xte2)


def fit_predict_moderebal(Xtr, ytr, mtr, Xte, hp):
    """Global model with per-mode-balanced sample weights — each ADCS mode
    contributes equally, counteracting dynamic-mode dominance so PASSIVE rows
    aren't drowned out. (Composes multiplicatively with class_weight='balanced'.)"""
    sw = np.ones(len(ytr), dtype=np.float64)
    umodes, counts = np.unique(mtr, return_counts=True)
    target = len(ytr) / len(umodes)
    for m, c in zip(umodes, counts):
        sw[mtr == m] = target / c
    clf = make_clf(hp)
    clf.fit(Xtr, ytr, sample_weight=sw)
    return clf.predict(Xte)


def fit_predict_permode(Xtr, ytr, mtr, Xte, mte, hp):
    """One head per training mode; route each test row to its mode's head.
    Unseen-mode rows fall back to a global head — fit lazily, only if some test
    mode has no head (avoids a redundant full-corpus fit when all modes are
    well-populated, which is the usual case)."""
    heads = {}
    for m in np.unique(mtr):
        sel = mtr == m
        if sel.sum() < 50 or len(np.unique(ytr[sel])) < 2:
            continue  # too thin / single-class → use global fallback
        h = make_clf(hp)
        h.fit(Xtr[sel], ytr[sel])
        heads[m] = h
    global_clf = None
    if any(m not in heads for m in np.unique(mte)):
        global_clf = make_clf(hp)
        global_clf.fit(Xtr, ytr)
    ypred = np.empty(len(Xte), dtype=object)
    for m in np.unique(mte):
        sel = mte == m
        clf = heads.get(m, global_clf)
        ypred[sel] = clf.predict(Xte[sel])
    return ypred


def per_mode_report(y_true, y_pred, mode, ct, cp, modes):
    """Attack-frame accuracy per mode: sub-technique and cluster."""
    atk = y_true != "nominal"
    out = {}
    for mo in modes:
        mm = atk & (mode == mo)
        n = int(mm.sum())
        out[mo] = {
            "attack_frames": n,
            "subtech_acc": round(float((y_true[mm] == y_pred[mm]).mean()), 4) if n else None,
            "cluster_acc": round(float((ct[mm] == cp[mm]).mean()), 4) if n else None,
        }
    # ROBUST-tier cluster accuracy (no-regression guard), all modes pooled
    rob = atk & np.isin(ct, list(ROBUST_CLUSTERS))
    out["_robust_tier"] = {
        "attack_frames": int(rob.sum()),
        "cluster_acc": round(float((ct[rob] == cp[rob]).mean()), 4) if rob.sum() else None,
    }
    out["_overall_attack_cluster_acc"] = round(
        float((ct[atk] == cp[atk]).mean()), 4) if atk.sum() else None
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv-dir", default="data/onair/csv_corpus_v3stage")
    p.add_argument("--manifest-dir", default="data/onair/scenarios")
    p.add_argument("--classifier",
                   default="data/onair/models/xgb_attack_classifier_v3.pkl")
    p.add_argument("--taxonomy",
                   default="data/onair/models/cluster_rescore/cluster_taxonomy.json")
    p.add_argument("--variants", default="baseline,mode_feat,per_mode")
    p.add_argument("--max-iter", type=int, default=None,
                   help="override HistGB max_iter (screening); default = v3 hp")
    p.add_argument("--smoke", type=int, default=None,
                   help="subsample each instance to N rows for a fast path-check")
    p.add_argument("--out", default="data/onair/models/mode_aware/mode_aware_eval.json")
    args = p.parse_args()

    t0 = time.time()
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]

    with open(args.classifier, "rb") as f:
        v3 = pickle.load(f)
    schema = v3["schema"]
    hp = dict(v3["clf"].get_params())
    if args.max_iter:
        hp["max_iter"] = args.max_iter
    allowed = set(v3["labels"])
    n_feat = len(schema.get("feature_names", []))

    clusters = json.load(open(args.taxonomy))["clusters"]

    instances = discover_instances(args.manifest_dir)
    print(f"{len(instances)} instances: {[len(m) for m in instances]} manifests; "
          f"variants={variants}; max_iter={hp['max_iter']}")
    if len(instances) < 2:
        sys.exit("need >= 2 instances for LOIO")

    data = []
    for i, manifests in enumerate(instances):
        X, y, meta = load_instance(args.csv_dir, manifests, schema, allowed)
        assert X.shape[1] == n_feat, f"feature mismatch {X.shape[1]} != {n_feat}"
        m = meta["adcs_mode"]
        if args.smoke and len(y) > args.smoke:
            rs = np.random.RandomState(42 + i)
            keep = rs.choice(len(y), args.smoke, replace=False)
            X, y, m = X[keep], y[keep], m[keep]
        print(f"  instance {i}: X={X.shape}  modes={sorted(set(m.tolist()))}")
        data.append((X, y, m))

    # Fixed mode index across folds (real ADCS modes only; drop MODE_UNKNOWN).
    all_modes = sorted({mm for _, _, m in data for mm in set(m.tolist())})
    real_modes = [m for m in all_modes if m != "MODE_UNKNOWN"]
    mode_index = {m: j for j, m in enumerate(real_modes)}
    print(f"modes: {real_modes}")

    # Accumulate per-variant out-of-fold predictions (aligned to y_true/mode).
    yt_all, mode_all = [], []
    pred_all = {v: [] for v in variants}
    fold_overall = {v: [] for v in variants}
    from sklearn.metrics import accuracy_score

    for held in range(len(data)):
        Xtr = np.vstack([data[j][0] for j in range(len(data)) if j != held])
        ytr = np.concatenate([data[j][1] for j in range(len(data)) if j != held])
        mtr = np.concatenate([data[j][2] for j in range(len(data)) if j != held])
        Xte, yte, mte = data[held]
        yt_all.append(yte)
        mode_all.append(mte)
        for v in variants:
            t1 = time.time()
            if v == "baseline":
                yp = fit_predict_baseline(Xtr, ytr, Xte, hp)
            elif v == "mode_feat":
                yp = fit_predict_modefeat(Xtr, ytr, mtr, Xte, mte, hp, mode_index)
            elif v == "per_mode":
                yp = fit_predict_permode(Xtr, ytr, mtr, Xte, mte, hp)
            elif v == "mode_rebal":
                yp = fit_predict_moderebal(Xtr, ytr, mtr, Xte, hp)
            else:
                sys.exit(f"unknown variant {v}")
            pred_all[v].append(yp)
            acc = accuracy_score(yte, yp)
            fold_overall[v].append(acc)
            print(f"  fold {held} {v:10}: acc={acc:.4f} ({time.time()-t1:.0f}s)")

    y_true = np.concatenate(yt_all).astype(object)
    mode = np.concatenate(mode_all).astype(object)
    ct = map_to_cluster(y_true, clusters)

    report = {"corpus": args.csv_dir, "max_iter": hp["max_iter"],
              "smoke": args.smoke, "modes": real_modes, "variants": {}}
    for v in variants:
        yp = np.concatenate(pred_all[v]).astype(object)
        cp = map_to_cluster(yp, clusters)
        report["variants"][v] = {
            "loio_overall_acc_mean": round(float(np.mean(fold_overall[v])), 4),
            "loio_overall_acc_per_fold": [round(a, 4) for a in fold_overall[v]],
            "per_mode": per_mode_report(y_true, yp, mode, ct, cp, real_modes),
        }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)

    # ─── console summary: the decision table ───────────────────────────
    print(f"\n{'='*72}\nMODE-AWARE CLASSIFIER LOIO  (frozen corpus, max_iter={hp['max_iter']})")
    print(f"{'='*72}")
    hdr = f"{'variant':10} {'overall':>8} " + " ".join(f"{m.replace('MODE_',''):>9}" for m in real_modes) + f" {'ROBUST':>8}"
    print(hdr)
    print("(cluster-acc on attack frames; overall = LOIO sub-technique acc)")
    base_pm = report["variants"].get("baseline", {}).get("per_mode", {})
    for v in variants:
        pm = report["variants"][v]["per_mode"]
        row = f"{v:10} {report['variants'][v]['loio_overall_acc_mean']:>8.3f} "
        row += " ".join(f"{(pm[m]['cluster_acc'] if pm[m]['cluster_acc'] is not None else 0):>9.3f}" for m in real_modes)
        row += f" {(pm['_robust_tier']['cluster_acc'] or 0):>8.3f}"
        print(row)
    # PASSIVE deltas vs baseline (the headline)
    if "baseline" in variants and base_pm:
        bp = base_pm.get("MODE_PASSIVE", {}).get("cluster_acc")
        if bp is not None:
            print(f"\nPASSIVE cluster-acc vs baseline ({bp:.3f}):")
            for v in variants:
                if v == "baseline":
                    continue
                vp = report["variants"][v]["per_mode"]["MODE_PASSIVE"]["cluster_acc"]
                print(f"  {v:10} {vp:.3f}  ({vp-bp:+.3f})")
    print(f"\nwrote {args.out}\ntotal: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
