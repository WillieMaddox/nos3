#!/usr/bin/env python3
"""AINOS3-30 feature-ablation retrain — do 6 new CFE_TBL columns recover the
4 DEAD table-load attack classes?

Context
-------
The deployed v3 attack classifier (sklearn HistGradientBoostingClassifier,
see `eval_classifier_clusters.py::make_clf`) has 4 classes with F1~0 in the
mode-balanced LOIO eval:

    de_0003_03_command_receiver_mode   (DE-0003.03)
    de_0003_08_received_commands       (DE-0003.08)
    de_0003_09_system_clock_for_evasion(DE-0003.09)
    ex_0014_03_sensor_data             (EX-0014.03)

AINOS3-30 added 6 new telemetry-derived columns intended to give the model a
handle on table-load activity:

    CFE_TBL.FileLoadChanged, CFE_TBL.FileLoadCount, CFE_TBL.TableUpdateChanged,
    CFE_TBL.TableUpdateCount, CFE_TBL.TableLoadChanged, CFE_TBL.TableLoadCount

This script measures whether those 6 columns move the needle, using a freshly
collected ONE-instance, new-256-column-schema corpus staged at
`data/onair/csv_ainos3_30/` (32 CSVs + 32 manifests, one execution per attack
technique).

Methodology
-----------
Single instance ⇒ no leave-one-instance-out is possible, and any absolute F1
is optimistic (single-instance overfit — the model can key on this instance's
particular noise floor). The primary, defensible deliverable is therefore the
ABLATION DELTA between two arms trained/evaluated identically:

    ARM A ("with")    — full feature set, including the 6 derived columns
                         (raw + delta, i.e. 12 columns in the 2x[raw,delta]
                         feature matrix).
    ARM B ("without")  — identical feature matrix with those 12 columns
                         removed post-hoc (guarantees byte-identical remaining
                         features and an identical train/test split).

Because every attack technique in this corpus executes exactly ONCE (one
manifest, one contiguous corruption window — verified against the staged
manifests), a leave-one-execution-out split would leave zero test examples
for every class. Instead we use a WITHIN-INSTANCE CHRONOLOGICAL split,
grouped so no split boundary falls inside a temporally-contiguous block:

  - group key = attack_id for corruption-window rows (each attack's frames
    are one contiguous block in this corpus); "nominal::<file_id>" for
    nominal rows (each file's nominal frames are one contiguous block).
  - within each group, rows are already in chronological order (the loader
    concatenates CSVs in filename-sorted / chronological order, and each
    CSV's rows are already time-ordered) — the FIRST `train_frac` fraction of
    a group's rows go to train, the LAST `1 - train_frac` go to test.

This avoids the leakage a random row shuffle would create: adjacent frames
are highly autocorrelated (the model's delta features are literally
row[i] - row[i-1]), so a row-level random split would let the model see
row i-1 in train and trivially predict row i in test. A chronological
per-group split keeps train and test temporally disjoint within every class.

The SAME split (row indices) is used for both arms — it depends only on
labels/grouping, not on feature values, so it is identical whether or not
the 6 derived columns are present.

Usage
-----
    ~/.virtualenvs/nos3/bin/python components/onair/training/ablation_ainos3_30.py \\
        --csv-dir data/onair/csv_ainos3_30 \\
        --out-json data/onair/models/ablation_ainos3_30.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

import numpy as np

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from loader import load_with_labels          # noqa: E402
from features import build_features           # noqa: E402
from eval_classifier_clusters import (         # noqa: E402
    make_clf, per_class_f1, frame_labels,
)

# The 6 AINOS3-30 derived columns under test.
DERIVED_COLUMNS = [
    "CFE_TBL.FileLoadChanged",
    "CFE_TBL.FileLoadCount",
    "CFE_TBL.TableUpdateChanged",
    "CFE_TBL.TableUpdateCount",
    "CFE_TBL.TableLoadChanged",
    "CFE_TBL.TableLoadCount",
]

# The 4 target DEAD classes, as they appear as `id` in the manifests.
TARGET_CLASSES = ["DE-0003.03", "DE-0003.08", "DE-0003.09", "EX-0014.03"]


def build_group_split(y: np.ndarray, file_id: np.ndarray, train_frac: float):
    """Chronological, per-group train/test split. See module docstring.

    Returns (train_mask, test_mask) boolean arrays aligned to y's row order.
    Groups with < 2 rows go entirely to train (cannot be tested; flagged by
    the caller via the support table).
    """
    n = len(y)
    train_mask = np.zeros(n, dtype=bool)
    test_mask = np.zeros(n, dtype=bool)

    group = np.where(y == "nominal",
                      np.char.add("nominal::", file_id.astype(str)),
                      y.astype(str))

    # Positions are already chronological (concat order == file order == row
    # order); iterating the array in index order preserves that order per
    # group, so order[g] is naturally chronological within group g.
    order: dict[str, list[int]] = {}
    for idx, g in enumerate(group):
        order.setdefault(g, []).append(idx)

    for g, idxs in order.items():
        n_g = len(idxs)
        if n_g < 2:
            train_mask[idxs] = True
            continue
        n_test = max(1, round(n_g * (1 - train_frac)))
        n_test = min(n_test, n_g - 1)  # keep >=1 train row
        n_train = n_g - n_test
        train_mask[idxs[:n_train]] = True
        test_mask[idxs[n_train:]] = True

    return train_mask, test_mask


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv-dir", default="data/onair/csv_ainos3_30")
    p.add_argument("--manifest-dir", default=None,
                   help="defaults to --csv-dir (manifests are staged alongside the CSVs)")
    p.add_argument("--out-json", default="data/onair/models/ablation_ainos3_30.json")
    p.add_argument("--train-frac", type=float, default=0.7)
    args = p.parse_args()
    manifest_dir = args.manifest_dir or args.csv_dir

    t0 = time.time()
    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)

    manifests = sorted(glob.glob(os.path.join(manifest_dir, "manifest_*.json")))
    if not manifests:
        sys.exit(f"no manifest_*.json found under {manifest_dir}")
    print(f"discovered {len(manifests)} manifests under {manifest_dir}")

    # ─── load + label ───────────────────────────────────────────────────
    df, stats = load_with_labels(csv_dir=args.csv_dir, manifest=manifests,
                                 drop_unlabeled=True, skip_warmup_rows=30)
    y = frame_labels(df)
    file_id = df["__file_id"].astype(str).to_numpy()
    print(f"loaded {df.shape[0]} labeled rows, {df.shape[1]} raw columns")

    # ─── sanity check: do the 6 derived columns actually vary? ─────────
    print("\n=== sanity check: derived-column variance ===")
    variance_report = {}
    for col in DERIVED_COLUMNS:
        if col not in df.columns:
            variance_report[col] = {"present": False}
            print(f"  {col}: MISSING from corpus columns")
            continue
        vals_all = pd_to_numeric_safe(df[col])
        entry = {
            "present": True,
            "nunique_overall": int(vals_all.nunique()),
            "unique_values_overall": sorted(set(vals_all.unique().tolist()))[:10],
            "per_target": {},
        }
        for t in TARGET_CLASSES:
            sub = vals_all[y == t]
            entry["per_target"][t] = {
                "n_rows": int(len(sub)),
                "nunique": int(sub.nunique()) if len(sub) else 0,
                "unique_values": sorted(set(sub.unique().tolist()))[:10] if len(sub) else [],
            }
        variance_report[col] = entry
        print(f"  {col}: nunique_overall={entry['nunique_overall']} "
              f"values={entry['unique_values_overall']}")
        for t in TARGET_CLASSES:
            e = entry["per_target"][t]
            print(f"      {t}: n={e['n_rows']} nunique={e['nunique']} values={e['unique_values']}")

    any_variance = any(
        v.get("present") and v.get("nunique_overall", 0) > 1 for v in variance_report.values()
    )
    print(f"\n  ANY derived column varies anywhere in the corpus: {any_variance}")

    # ─── build features (single build; arm B derived by column removal) ─
    drop = [c for c in df.columns if c.startswith("__") and c != "__file_id"]
    X_full, schema = build_features(df.drop(columns=drop), include_deltas=True)
    print(f"\nfull feature matrix: {X_full.shape}")

    feat_names = schema.feature_names
    derived_raw_idx = [feat_names.index(c) for c in DERIVED_COLUMNS if c in feat_names]
    derived_delta_idx = [feat_names.index(f"d_{c}") for c in DERIVED_COLUMNS if f"d_{c}" in feat_names]
    missing = [c for c in DERIVED_COLUMNS if c not in feat_names]
    if missing:
        print(f"  WARNING: derived columns missing from feature schema (dropped as "
              f"text/unparseable?): {missing}")
    drop_idx = sorted(set(derived_raw_idx + derived_delta_idx))
    print(f"  derived columns occupy {len(drop_idx)} of {X_full.shape[1]} feature slots "
          f"({len(derived_raw_idx)} raw + {len(derived_delta_idx)} delta)")

    keep_mask = np.ones(X_full.shape[1], dtype=bool)
    keep_mask[drop_idx] = False
    X_without = X_full[:, keep_mask]
    X_with = X_full
    print(f"  ARM A (with)    : {X_with.shape}")
    print(f"  ARM B (without) : {X_without.shape}")

    # ─── chronological grouped split (identical for both arms) ─────────
    train_mask, test_mask = build_group_split(y, file_id, args.train_frac)
    print(f"\nsplit: train={int(train_mask.sum())} test={int(test_mask.sum())} "
          f"(train_frac={args.train_frac})")

    labels_all = sorted(set(y.tolist()))
    labels_test = sorted(set(y[test_mask].tolist()))
    untested = sorted(set(labels_all) - set(labels_test))
    if untested:
        print(f"  classes with ZERO test rows (support < 2, all-train): {untested}")

    support_total = {l: int((y == l).sum()) for l in labels_all}
    support_train = {l: int((y[train_mask] == l).sum()) for l in labels_all}
    support_test = {l: int((y[test_mask] == l).sum()) for l in labels_all}

    # ─── fit + evaluate both arms ────────────────────────────────────────
    results = {}
    for arm_name, X in (("without", X_without), ("with", X_with)):
        print(f"\n=== ARM {arm_name} ===")
        Xtr, ytr = X[train_mask], y[train_mask]
        Xte, yte = X[test_mask], y[test_mask]
        t1 = time.time()
        clf = make_clf({})
        clf.fit(Xtr, ytr)
        ypred = clf.predict(Xte)
        from sklearn.metrics import accuracy_score, f1_score
        acc = float(accuracy_score(yte, ypred))
        macro_f1 = float(f1_score(yte, ypred, labels=labels_test, average="macro", zero_division=0))
        f1_per_class = per_class_f1(yte, ypred, labels_all)
        results[arm_name] = {
            "n_features": int(X.shape[1]),
            "accuracy": acc,
            "macro_f1": macro_f1,
            "n_test_classes": len(labels_test),
            "f1_per_class": {k: round(float(v), 4) for k, v in f1_per_class.items()},
            "fit_predict_seconds": round(time.time() - t1, 1),
        }
        print(f"  n_features={X.shape[1]} accuracy={acc:.4f} macro_f1={macro_f1:.4f} "
              f"({time.time()-t1:.0f}s)")

    # ─── target-class table ─────────────────────────────────────────────
    print("\n=== TARGET CLASS F1: without vs with ===")
    print(f"{'class':<40}{'support_total':>14}{'support_test':>13}"
          f"{'F1_without':>12}{'F1_with':>10}{'delta':>9}")
    target_table = []
    for cls in TARGET_CLASSES:
        f1_wo = results["without"]["f1_per_class"].get(cls, 0.0)
        f1_w = results["with"]["f1_per_class"].get(cls, 0.0)
        delta = round(f1_w - f1_wo, 4)
        row = {
            "class": cls,
            "support_total": support_total.get(cls, 0),
            "support_train": support_train.get(cls, 0),
            "support_test": support_test.get(cls, 0),
            "f1_without": f1_wo,
            "f1_with": f1_w,
            "delta": delta,
        }
        target_table.append(row)
        print(f"{cls:<40}{row['support_total']:>14}{row['support_test']:>13}"
              f"{f1_wo:>12.4f}{f1_w:>10.4f}{delta:>+9.4f}")

    print(f"\n{'OVERALL macro-F1':<40}{'':>14}{'':>13}"
          f"{results['without']['macro_f1']:>12.4f}{results['with']['macro_f1']:>10.4f}"
          f"{results['with']['macro_f1'] - results['without']['macro_f1']:>+9.4f}")
    print(f"{'OVERALL accuracy':<40}{'':>14}{'':>13}"
          f"{results['without']['accuracy']:>12.4f}{results['with']['accuracy']:>10.4f}"
          f"{results['with']['accuracy'] - results['without']['accuracy']:>+9.4f}")

    # ─── write JSON ──────────────────────────────────────────────────────
    out = {
        "ticket": "AINOS3-30",
        "corpus": {
            "csv_dir": args.csv_dir,
            "manifest_dir": manifest_dir,
            "n_manifests": len(manifests),
            "n_labeled_rows": int(len(df)),
            "n_raw_columns": int(df.shape[1]),
        },
        "split": {
            "method": "chronological_per_group",
            "train_frac": args.train_frac,
            "n_train": int(train_mask.sum()),
            "n_test": int(test_mask.sum()),
            "classes_with_zero_test_rows": untested,
        },
        "derived_columns": DERIVED_COLUMNS,
        "derived_columns_variance": variance_report,
        "any_derived_column_varies": any_variance,
        "target_classes": TARGET_CLASSES,
        "target_class_table": target_table,
        "support_total": support_total,
        "support_train": support_train,
        "support_test": support_test,
        "arms": results,
        "caveats": [
            "SINGLE INSTANCE: this corpus is one execution per attack technique. "
            "There is no leave-one-instance-out here; absolute F1 numbers are "
            "optimistic (single-instance overfit) for BOTH arms equally. The "
            "ablation DELTA (with - without) is the robust signal, not the "
            "absolute F1.",
            "A deploy decision additionally requires >= 1 more new-schema "
            "(256-column) instance so a genuine LOIO can be run and the delta "
            "re-measured out-of-instance before touching the deployed v3 model.",
        ],
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    with open(args.out_json, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {args.out_json}")
    print(f"total: {time.time()-t0:.0f}s")


def pd_to_numeric_safe(series):
    import pandas as pd
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


if __name__ == "__main__":
    main()
