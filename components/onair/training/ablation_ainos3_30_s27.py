#!/usr/bin/env python3
"""AINOS3-30 (Sprint 27) — signal-feasibility ablation over the recorded MIDs.

Question
--------
AINOS3-70 (Sprint 25) and AINOS3-72 (Sprint 26) subscribed 16 extra MIDs and
re-pointed TO/CI for RECORDING only: the CSV schema grew from 250 kept columns
to 359, but the IF and the classifier still train on the original 894 v5
features derived from the 250. The frozen `csv_corpus_v3stage` predates those
columns, so they have never been ablated.

This script answers, before committing to a retrain: **does any recorded-but-
unused column block add discrimination for the weak-label classes?**

Corpus
------
A weak-class-biased 359-column slice collected 2026-08-11 by
`scenarios/run_attack_batch.py --input scenarios/batch_ainos3_30_weakclass.json`
(17 attacks, one execution each, `all_modes_dwell` bracketing, full stack
restart between runs). Attack selection was driven by the measured per-class F1
in `data/onair/models/cluster_rescore/cluster_taxonomy.json`:

    DEAD (F1 = 0.000)  DE-0003.03/.06/.08, EX-0012.08, EX-0014.03, EX-0014.04
    NEAR-DEAD (<0.07)  DE-0003.09, DE-0003.01, EX-0012.04
    HIGH-VARIANCE      EX-0014.01, EX-0012.03/.09/.12, IMP-0001
    ANCHOR (contrast)  IMP-0002, EX-0008.02, IMP-0005

The anchors are deliberate: a weak-class-only corpus makes per-class accuracy
uninterpretable, because the classifier would have no strong class to confuse
the weak ones with.

Candidate blocks
----------------
The 109 added columns are a strict superset of the frozen schema (0 removed),
grouped by the subsystem that owns them:

    INGRESS     10  CI.* + TO.* — command-ingest and telemetry-output counters
                    and route masks. Highest prior: AINOS3-82's benchmark of the
                    Fayyaz CuCD-ID dataset showed an independent group
                    classifying GPS memory-poke injection almost perfectly from
                    command-INGRESS features alone, while our telemetry-egress
                    view scores F1 = 0.000 on the same attack (EX-0014.03/.04).
    SENSOR_HK   35  Per-sensor app housekeeping (CSS/FSS/IMU/MAG/ST/TORQUER).
    SENSOR_DEV  18  Raw *_DEV device packets. Prior expectation: redundant with
                    the fused ADCS_DI view.
    CDH         40  DS + FM + LC — data storage, file manager, limit checker.
    TBL          6  CFE_TBL change-detect columns. Known NULL (Sprint-25
                    AINOS3-30: constant, ablation delta +0.000); included as a
                    negative control that the harness should reproduce.

Method
------
ONE feature matrix is built from the full 359-column corpus; every arm is a
COLUMN SUBSET of it. That guarantees the remaining features are byte-identical
across arms and the train/test split is the same row partition everywhere, so
the arm-to-arm delta is attributable to the candidate block and nothing else.

Split: chronological, per group (`build_group_split`, imported from the
Sprint-25 ablation) — the first `train_frac` of each group's rows train, the
rest test. Group = attack id for corruption rows, `nominal::<file_id>` for
nominal rows. A random row split would leak badly: adjacent frames are highly
autocorrelated and the delta features are literally `row[i] - row[i-1]`.

Provenance of the numbers this produces — READ THIS
---------------------------------------------------
Every attack technique in this corpus executes EXACTLY ONCE, so
leave-one-instance-out is impossible and the absolute accuracies below are
**within-instance, single-run** figures: optimistic, because the model can key
on this session's particular noise floor. They are NOT comparable to the
LOIO out-of-fold numbers in `V5_DETECTOR_COVERAGE.md` (hybrid 0.646) and must
never be quoted as if they were. See AINOS3-80 (metric-provenance-audit) and
the 76.9 % -> 42.3 % correction that motivated it.

The defensible deliverable is the **DELTA between arms**, which shares the
split, the rows and the estimator. Turning a positive delta into a deployable
number requires a second collection instance (AINOS3-45) so LOIO becomes
possible.

Usage
-----
    ~/.virtualenvs/nos3/bin/python \\
        components/onair/training/ablation_ainos3_30_s27.py \\
        --csv-dir data/onair/csv_ainos3_30_s27 \\
        --manifest-dir data/onair/scenarios_ainos3_30_s27 \\
        --out-json data/onair/models/ablation_ainos3_30_s27.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time

import numpy as np

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from loader import load_with_labels                      # noqa: E402
from features import build_features                      # noqa: E402
from eval_classifier_clusters import (                    # noqa: E402
    make_clf, per_class_f1, frame_labels,
)
from ablation_ainos3_30 import build_group_split          # noqa: E402

FROZEN_CORPUS = "data/onair/csv_corpus_v3stage"

# Candidate blocks, keyed by the column-name prefix that identifies them.
CANDIDATE_BLOCKS = {
    "INGRESS":    ("CI.", "TO."),
    "SENSOR_HK":  ("CSS.", "FSS.", "IMU.", "MAG.", "ST.", "TORQUER."),
    "SENSOR_DEV": ("CSS_DEV.", "FSS_DEV.", "IMU_DEV.", "MAG_DEV.", "ST_DEV."),
    "CDH":        ("DS.", "FM.", "LC."),
    "TBL":        ("CFE_TBL.",),
}

# Weak-label classes this ticket is trying to move, by tier.
WEAK_TIERS = {
    "DEAD": ["DE-0003.03", "DE-0003.06", "DE-0003.08",
             "EX-0012.08", "EX-0014.03", "EX-0014.04"],
    "NEAR_DEAD": ["DE-0003.09", "DE-0003.01", "EX-0012.04"],
    "HIGH_VAR": ["EX-0014.01", "EX-0012.03", "EX-0012.12",
                 "EX-0012.09", "IMP-0001"],
    "ANCHOR": ["IMP-0002", "EX-0008.02", "IMP-0005"],
}
WEAK_CLASSES = [c for tier in ("DEAD", "NEAR_DEAD", "HIGH_VAR")
                for c in WEAK_TIERS[tier]]


def frozen_schema_columns(frozen_dir: str) -> set[str]:
    """Column set of the frozen v3 corpus — defines the baseline arm."""
    files = sorted(glob.glob(os.path.join(frozen_dir, "*.csv")))
    if not files:
        raise FileNotFoundError(f"no CSVs under {frozen_dir}")
    with open(files[0]) as f:
        return set(next(csv.reader(f)))


def feature_slots_for(feat_names: list[str], tlm_columns: set[str]) -> list[int]:
    """Feature-matrix indices occupied by a set of telemetry columns.

    A telemetry column contributes a raw slot (`col`) and a delta slot
    (`d_col`); list-valued columns explode into indexed leaves (`col[0]`, ...),
    each with its own delta. Match on the exploded base name.
    """
    idx = []
    for i, fn in enumerate(feat_names):
        base = fn[2:] if fn.startswith("d_") else fn
        base = base.split("[", 1)[0]
        if base in tlm_columns:
            idx.append(i)
    return idx


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv-dir", default="data/onair/csv_ainos3_30_s27")
    p.add_argument("--manifest-dir", default="data/onair/scenarios_ainos3_30_s27")
    p.add_argument("--frozen-dir", default=FROZEN_CORPUS)
    p.add_argument("--out-json", default="data/onair/models/ablation_ainos3_30_s27.json")
    p.add_argument("--train-frac", type=float, default=0.7)
    p.add_argument("--seed-sweep", type=int, default=0,
                   help="DEAD INSTRUMENT — kept only so the finding is not "
                        "silently re-discovered. HistGradientBoostingClassifier "
                        "with early_stopping=False is DETERMINISTIC at this "
                        "corpus size (29k train rows is below the 200k binning "
                        "subsample threshold), so random_state changes nothing "
                        "and every seed returns an identical fit: measured "
                        "+/-0.0000 on all arms. A zero here is evidence of "
                        "nothing. Use --split-sweep instead.")
    p.add_argument("--split-sweep", default="",
                   help="Comma-separated train_frac values (e.g. "
                        "'0.6,0.65,0.7,0.75,0.8'). Refits the --sweep-arms at "
                        "each split point. This DOES size a real noise band: it "
                        "resamples which rows train, so a block whose delta "
                        "flips sign or varies by more than its own magnitude "
                        "across splits has not been shown to add anything.")
    p.add_argument("--bootstrap", type=int, default=0,
                   help="If > 0, bootstrap-resample the TEST rows this many "
                        "times (no refit) for a CI on each arm's macro-F1 and "
                        "on the arm-vs-baseline delta. Captures test-set "
                        "sampling noise only — NOT instance-level variance, "
                        "which is the dominant unmeasured term here.")
    p.add_argument("--sweep-arms", default="baseline,baseline+SENSOR_HK,baseline+ALL")
    args = p.parse_args()

    t0 = time.time()
    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)

    manifests = sorted(glob.glob(os.path.join(args.manifest_dir, "manifest_*.json")))
    if not manifests:
        sys.exit(f"no manifest_*.json under {args.manifest_dir}")
    print(f"{len(manifests)} manifests under {args.manifest_dir}")

    df, _stats = load_with_labels(csv_dir=args.csv_dir, manifest=manifests,
                                  drop_unlabeled=True, skip_warmup_rows=30)
    y = frame_labels(df)
    file_id = df["__file_id"].astype(str).to_numpy()
    print(f"loaded {df.shape[0]} labeled rows, {df.shape[1]} raw columns")

    # ─── partition the telemetry columns ────────────────────────────────
    tlm_cols = {c for c in df.columns if not c.startswith("__")}
    frozen = frozen_schema_columns(args.frozen_dir)
    baseline_cols = tlm_cols & frozen
    added_cols = tlm_cols - frozen
    removed = frozen - tlm_cols
    print(f"\nschema: {len(tlm_cols)} live, {len(frozen)} frozen, "
          f"{len(added_cols)} added, {len(removed)} removed")
    if removed:
        print(f"  WARNING: frozen columns absent from the new corpus: {sorted(removed)}")

    blocks: dict[str, set[str]] = {}
    for name, prefixes in CANDIDATE_BLOCKS.items():
        blocks[name] = {c for c in added_cols if c.startswith(prefixes)}
    claimed = set().union(*blocks.values()) if blocks else set()
    unclaimed = added_cols - claimed
    if unclaimed:
        blocks["UNCLAIMED"] = unclaimed
        print(f"  NOTE: {len(unclaimed)} added columns matched no block, "
              f"grouped as UNCLAIMED: {sorted(unclaimed)[:8]}")
    for name in blocks:
        print(f"  block {name:11s} {len(blocks[name]):3d} columns")

    # ─── one feature build; every arm is a column subset of it ──────────
    drop = [c for c in df.columns if c.startswith("__") and c != "__file_id"]
    X_full, schema = build_features(df.drop(columns=drop), include_deltas=True)
    feat_names = schema.feature_names
    print(f"\nfull feature matrix: {X_full.shape}")

    baseline_idx = feature_slots_for(feat_names, baseline_cols)
    block_idx = {n: feature_slots_for(feat_names, cols) for n, cols in blocks.items()}
    print(f"  baseline occupies {len(baseline_idx)} feature slots")
    for n, idx in block_idx.items():
        print(f"  block {n:11s} occupies {len(idx):4d} feature slots")

    # ─── split (identical rows for every arm) ───────────────────────────
    train_mask, test_mask = build_group_split(y, file_id, args.train_frac)
    labels_all = sorted(set(y.tolist()))
    labels_test = sorted(set(y[test_mask].tolist()))
    print(f"\nsplit: train={int(train_mask.sum())} test={int(test_mask.sum())} "
          f"({len(labels_all)} classes, {len(labels_test)} testable)")
    untested = sorted(set(labels_all) - set(labels_test))
    if untested:
        print(f"  classes with ZERO test rows: {untested}")

    support = {l: {"total": int((y == l).sum()),
                   "train": int((y[train_mask] == l).sum()),
                   "test": int((y[test_mask] == l).sum())} for l in labels_all}

    # ─── arms ───────────────────────────────────────────────────────────
    arms: dict[str, list[int]] = {"baseline": sorted(baseline_idx)}
    for n, idx in block_idx.items():
        arms[f"baseline+{n}"] = sorted(set(baseline_idx) | set(idx))
    arms["baseline+ALL"] = sorted(set(baseline_idx).union(*block_idx.values()))

    from sklearn.metrics import accuracy_score, f1_score
    results = {}
    for arm, idx in arms.items():
        t1 = time.time()
        X = X_full[:, idx]
        clf = make_clf({})
        clf.fit(X[train_mask], y[train_mask])
        pred = clf.predict(X[test_mask])
        acc = float(accuracy_score(y[test_mask], pred))
        macro = float(f1_score(y[test_mask], pred, labels=labels_test,
                               average="macro", zero_division=0))
        results[arm] = {
            "n_features": len(idx),
            "accuracy": round(acc, 4),
            "macro_f1": round(macro, 4),
            "f1_per_class": {k: round(float(v), 4)
                             for k, v in per_class_f1(y[test_mask], pred, labels_all).items()},
            "fit_seconds": round(time.time() - t1, 1),
        }
        print(f"  {arm:24s} feats={len(idx):5d} acc={acc:.4f} "
              f"macro_f1={macro:.4f}  ({time.time()-t1:.0f}s)")

    base = results["baseline"]

    # ─── deltas ─────────────────────────────────────────────────────────
    print(f"\n=== DELTA vs baseline ===")
    print(f"{'arm':<24}{'d_acc':>9}{'d_macroF1':>11}   weak-class movers (|dF1| >= 0.02)")
    deltas = {}
    for arm, r in results.items():
        if arm == "baseline":
            continue
        movers = {}
        for cls in WEAK_CLASSES:
            d = r["f1_per_class"].get(cls, 0.0) - base["f1_per_class"].get(cls, 0.0)
            if abs(d) >= 0.02:
                movers[cls] = round(d, 4)
        deltas[arm] = {
            "d_accuracy": round(r["accuracy"] - base["accuracy"], 4),
            "d_macro_f1": round(r["macro_f1"] - base["macro_f1"], 4),
            "weak_class_movers": dict(sorted(movers.items(), key=lambda kv: -abs(kv[1]))),
            "d_weak_macro_f1": round(
                float(np.mean([r["f1_per_class"].get(c, 0.0) for c in WEAK_CLASSES])
                      - np.mean([base["f1_per_class"].get(c, 0.0) for c in WEAK_CLASSES])), 4),
        }
        top = ", ".join(f"{k} {v:+.3f}" for k, v in list(deltas[arm]["weak_class_movers"].items())[:4])
        print(f"{arm:<24}{deltas[arm]['d_accuracy']:+9.4f}{deltas[arm]['d_macro_f1']:+11.4f}   {top or '—'}")

    # ─── per-tier weak-class table for the winning block ────────────────
    print(f"\n=== per-class F1 by tier (baseline -> baseline+ALL) ===")
    allr = results["baseline+ALL"]
    print(f"{'tier':<11}{'class':<22}{'support_test':>13}{'base':>8}{'+ALL':>8}{'delta':>9}")
    tier_rows = []
    for tier, classes in WEAK_TIERS.items():
        for cls in classes:
            b = base["f1_per_class"].get(cls, 0.0)
            a = allr["f1_per_class"].get(cls, 0.0)
            st = support.get(cls, {}).get("test", 0)
            tier_rows.append({"tier": tier, "class": cls, "support_test": st,
                              "f1_baseline": b, "f1_all": a, "delta": round(a - b, 4)})
            print(f"{tier:<11}{cls:<22}{st:>13}{b:>8.3f}{a:>8.3f}{a-b:>+9.3f}")

    # ─── seed sweep: how big is the noise band? ─────────────────────────
    sweep = {}
    if args.seed_sweep > 0:
        print(f"\n=== seed sweep ({args.seed_sweep} seeds) — sizing the noise band ===")
        for arm in [a.strip() for a in args.sweep_arms.split(",") if a.strip()]:
            if arm not in arms:
                print(f"  skipping unknown arm {arm}")
                continue
            idx = arms[arm]
            X = X_full[:, idx]
            accs, macros, per_cls = [], [], {c: [] for c in WEAK_CLASSES}
            for s in range(args.seed_sweep):
                clf = make_clf({})
                clf.set_params(random_state=42 + s)
                clf.fit(X[train_mask], y[train_mask])
                pred = clf.predict(X[test_mask])
                accs.append(float(accuracy_score(y[test_mask], pred)))
                macros.append(float(f1_score(y[test_mask], pred, labels=labels_test,
                                             average="macro", zero_division=0)))
                pc = per_class_f1(y[test_mask], pred, labels_all)
                for c in WEAK_CLASSES:
                    per_cls[c].append(float(pc.get(c, 0.0)))
            sweep[arm] = {
                "n_seeds": args.seed_sweep,
                "accuracy_mean": round(float(np.mean(accs)), 4),
                "accuracy_std": round(float(np.std(accs)), 4),
                "macro_f1_mean": round(float(np.mean(macros)), 4),
                "macro_f1_std": round(float(np.std(macros)), 4),
                "per_class_f1_mean": {c: round(float(np.mean(v)), 4) for c, v in per_cls.items()},
                "per_class_f1_std": {c: round(float(np.std(v)), 4) for c, v in per_cls.items()},
            }
            s_ = sweep[arm]
            print(f"  {arm:24s} acc={s_['accuracy_mean']:.4f}+/-{s_['accuracy_std']:.4f}  "
                  f"macro_f1={s_['macro_f1_mean']:.4f}+/-{s_['macro_f1_std']:.4f}")
        worst = max((v["per_class_f1_std"] for v in sweep.values()),
                    key=lambda d: max(d.values()), default={})
        if worst:
            top = sorted(worst.items(), key=lambda kv: -kv[1])[:5]
            print("  largest per-class seed noise: "
                  + ", ".join(f"{k} +/-{v:.3f}" for k, v in top))

    # ─── split sweep: the real noise band ───────────────────────────────
    split_sweep = {}
    if args.split_sweep:
        fracs = [float(f) for f in args.split_sweep.split(",") if f.strip()]
        sweep_arms = [a.strip() for a in args.sweep_arms.split(",")
                      if a.strip() and a.strip() in arms]
        print(f"\n=== split sweep over train_frac {fracs} — the real noise band ===")
        for frac in fracs:
            tr_m, te_m = build_group_split(y, file_id, frac)
            lt = sorted(set(y[te_m].tolist()))
            per_arm = {}
            for arm in sweep_arms:
                X = X_full[:, arms[arm]]
                clf = make_clf({})
                clf.fit(X[tr_m], y[tr_m])
                pred = clf.predict(X[te_m])
                per_arm[arm] = {
                    "accuracy": round(float(accuracy_score(y[te_m], pred)), 4),
                    "macro_f1": round(float(f1_score(y[te_m], pred, labels=lt,
                                                     average="macro", zero_division=0)), 4),
                    "f1_per_class": {k: round(float(v), 4) for k, v in
                                     per_class_f1(y[te_m], pred, labels_all).items()},
                }
            split_sweep[str(frac)] = per_arm
            line = "  ".join(f"{a.replace('baseline','base'):16s}"
                             f"mF1={per_arm[a]['macro_f1']:.4f}" for a in sweep_arms)
            print(f"  train_frac={frac:<5} {line}")

        # Across-split delta stability for each non-baseline arm.
        print(f"\n  delta vs baseline, per split (macro-F1):")
        for arm in sweep_arms:
            if arm == "baseline":
                continue
            ds = [split_sweep[str(f)][arm]["macro_f1"]
                  - split_sweep[str(f)]["baseline"]["macro_f1"] for f in fracs]
            sign_flip = min(ds) < 0 < max(ds)
            print(f"    {arm:24s} " + " ".join(f"{d:+.4f}" for d in ds)
                  + f"   mean={np.mean(ds):+.4f} std={np.std(ds):.4f}"
                  + ("  <-- SIGN FLIPS" if sign_flip else ""))
            split_sweep.setdefault("_delta_summary", {})[arm] = {
                "per_split": [round(float(d), 4) for d in ds],
                "mean": round(float(np.mean(ds)), 4),
                "std": round(float(np.std(ds)), 4),
                "sign_flips": bool(sign_flip),
            }

    # ─── bootstrap CI on the test set (no refit) ────────────────────────
    boot = {}
    if args.bootstrap > 0:
        print(f"\n=== test-set bootstrap ({args.bootstrap} resamples) ===")
        rng = np.random.default_rng(0)
        te_idx = np.flatnonzero(test_mask)
        preds = {}
        for arm in [a.strip() for a in args.sweep_arms.split(",")
                    if a.strip() and a.strip() in arms]:
            X = X_full[:, arms[arm]]
            clf = make_clf({})
            clf.fit(X[train_mask], y[train_mask])
            preds[arm] = clf.predict(X[test_mask])
        yte = y[test_mask]
        draws = [rng.integers(0, len(te_idx), len(te_idx)) for _ in range(args.bootstrap)]
        for arm, pred in preds.items():
            vals = [f1_score(yte[d], pred[d], average="macro", zero_division=0)
                    for d in draws]
            lo, hi = np.percentile(vals, [2.5, 97.5])
            boot[arm] = {"macro_f1_mean": round(float(np.mean(vals)), 4),
                         "ci95": [round(float(lo), 4), round(float(hi), 4)]}
            print(f"  {arm:24s} macro_f1={np.mean(vals):.4f}  95% CI [{lo:.4f}, {hi:.4f}]")
        if "baseline" in preds:
            bp = preds["baseline"]
            for arm, pred in preds.items():
                if arm == "baseline":
                    continue
                dv = [f1_score(yte[d], pred[d], average="macro", zero_division=0)
                      - f1_score(yte[d], bp[d], average="macro", zero_division=0)
                      for d in draws]
                lo, hi = np.percentile(dv, [2.5, 97.5])
                crosses = lo < 0 < hi
                boot[f"delta::{arm}"] = {"mean": round(float(np.mean(dv)), 4),
                                         "ci95": [round(float(lo), 4), round(float(hi), 4)],
                                         "ci_includes_zero": bool(crosses)}
                print(f"  delta {arm:18s} {np.mean(dv):+.4f}  95% CI "
                      f"[{lo:+.4f}, {hi:+.4f}]" + ("  <-- INCLUDES ZERO" if crosses else ""))

    out = {
        "ticket": "AINOS3-30 (Sprint 27) signal-feasibility",
        "corpus": {
            "csv_dir": args.csv_dir,
            "manifest_dir": args.manifest_dir,
            "n_manifests": len(manifests),
            "n_rows_labeled": int(df.shape[0]),
            "n_tlm_columns": len(tlm_cols),
            "n_baseline_columns": len(baseline_cols),
            "n_added_columns": len(added_cols),
            "blocks": {n: sorted(c) for n, c in blocks.items()},
        },
        "provenance": "within-instance chronological split, ONE execution per "
                      "technique — absolute numbers are optimistic and NOT "
                      "comparable to the LOIO out-of-fold figures in "
                      "V5_DETECTOR_COVERAGE.md; only the arm-to-arm deltas are "
                      "defensible",
        "loio_possible": False,
        "train_frac": args.train_frac,
        "n_train": int(train_mask.sum()),
        "n_test": int(test_mask.sum()),
        "classes_without_test_rows": untested,
        "support": support,
        "arms": results,
        "deltas": deltas,
        "weak_tier_table": tier_rows,
        "seed_sweep": sweep,
        "seed_sweep_note": "random_state is inert for this estimator at this "
                           "corpus size — a +/-0.0000 result here measures "
                           "nothing. See split_sweep / bootstrap.",
        "split_sweep": split_sweep,
        "bootstrap": boot,
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    with open(args.out_json, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {args.out_json}  ({time.time()-t0:.0f}s total)")


if __name__ == "__main__":
    main()
