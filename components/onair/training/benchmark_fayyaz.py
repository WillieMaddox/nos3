#!/usr/bin/env python3
"""AINOS3-82 — evaluation-honesty audit of the CuCD-ID NOS3/cFS IDS dataset.

Context
-------
Fayyaz et al., "CubeSat cybersecurity dataset for intrusion detection (CuCD-ID):
Labelled NOS3/cFS telemetry (raw + augmented) with COSMOS reproduction scripts",
Data in Brief 65 (2026) 112598, doi:10.1016/j.dib.2026.112598. Dataset released
under CC BY 4.0 at Mendeley doi:10.17632/7n2d42pm3n.3.

It is the closest published benchmark to our work: same simulator (NOS3 1.7.2 +
cFS), same ground system family (COSMOS), SPARTA-aligned attack scenarios. This
script does the *evaluation-honesty cross-check* the AINOS3-82 acceptance
criteria call for — the external counterpart to our own 76.9 % -> 42.3 % OOF
correction (see AINOS3-34 and the Sprint-26 coverage-overlay fix).

What it measures
----------------
The released raw table is 25,000 rows x 31 columns, exactly 5,000 rows per
class, and each class is ONE contiguous scenario run of 5,000 commands. That
layout makes class identity perfectly confounded with run identity, so the
question is not "is the model accurate" but "how much of the accuracy is the
attack and how much is the recording session".

Six arms, all using the same model family as our deployed v3 classifier
(sklearn HistGradientBoostingClassifier, see
`eval_classifier_clusters.py::make_clf`) so the numbers are comparable to ours:

  A1  all features        + random stratified 80/20   (the split the README
                                                       explicitly warns against)
  A2  all features        + the README's recommended per-class chronological
                                                       split (Option 1)
  A3  TimeRadians ONLY    + random stratified 80/20   (leak probe: how far does
                                                       a wall-clock feature get
                                                       you on its own?)
  A4  memory columns ONLY + random stratified 80/20   (leak probe: how far does
                                                       the host's memory baseline
                                                       get you on its own?)
  A5  CCSDS + sliding-window features only, TimeRadians and memory dropped,
                            random stratified 80/20   (the "attack-only" signal)
  A6  same feature set as A5 + the README's chronological split

The gap A1 - A5 is the run-identity contribution. The gap A5 - A6 is what the
temporal split costs once the run-identity features are gone.

Note on what CANNOT be done here
--------------------------------
Our leave-one-instance-out (LOIO) discipline needs >= 2 independent collection
runs per class; our corpus has 3. CuCD-ID ships exactly one run per class, so
LOIO is structurally impossible on it and no split of the released table can
separate "the attack" from "that afternoon's process memory baseline". That is
the single most important methodological difference between the two datasets,
and it is a property of the release, not a mistake in this script.

Usage
-----
    ~/.virtualenvs/nos3/bin/python components/onair/training/benchmark_fayyaz.py \\
        --data-dir data/onair/external/cucdid_v3 \\
        --out-json data/onair/models/benchmark_fayyaz.json

Fetch the dataset first (CC BY 4.0, ~3 MB zip):
    curl -L -o /tmp/cucdid.zip \\
        https://data.mendeley.com/public-api/zip/7n2d42pm3n/download/3
    unzip /tmp/cucdid.zip -d data/onair/external/
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

LABEL_NAMES = {
    0: "command_flooding",
    1: "data_injection",
    2: "defence_impairment",
    3: "normal",
    4: "storage_exhaustion",
}

# Published SHA-256 of the two released tables (Data/Metadata/checksums.txt).
# The shipped checksums.txt has no filenames on its hash lines, so the
# `sha256sum -c` command its own README recommends cannot work; we verify by
# position instead and report the mismatch as a finding rather than an error.
PUBLISHED_SHA256 = {
    "Data/Raw/consolidated_dataset_raw.csv":
        "2a6bb7bc9856099eef468dfe7df0043718a57c6ce84328e26b1883fa560c6ca2",
    "Data/Augmented/noised_dataset.csv":
        "656fc2f23544469d8cbdca631747debc8dae7164621a2cd6740a5928cfae3c68",
}

MEMORY_COLS = [
    "MemoryAnonMB", "MemoryFileMB", "MemoryKernelstackMB", "MemoryPageTableMB",
    "MemorySocketMB", "MemoryPercpuMB", "MemoryShmemMB",
    "MemorySlabUnreclaimableMB", "MemoryPageFaults",
]
TIME_COLS = ["TimeRadians"]


def make_clf():
    """Same estimator family + hyperparameters as our deployed v3 classifier."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.1, max_depth=8, max_leaf_nodes=31,
        min_samples_leaf=20, l2_regularization=0.0, early_stopping=False,
        class_weight="balanced", random_state=42, max_bins=255,
    )


def sha256_of(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def describe_structure(df: pd.DataFrame) -> dict:
    """Run-identity diagnostics: contiguity, per-class time arcs, dead columns."""
    import itertools
    runs = [(int(k), len(list(g))) for k, g in itertools.groupby(df["Label"])]
    zero_var = [c for c in df.columns if df[c].nunique(dropna=False) <= 1]

    arcs = {}
    for lbl, g in df.groupby("Label"):
        tr = g["TimeRadians"].to_numpy()
        arcs[LABEL_NAMES[int(lbl)]] = {
            "n": int(len(g)),
            "time_radians_min": round(float(tr.min()), 4),
            "time_radians_max": round(float(tr.max()), 4),
            "monotonic": bool(np.all(np.diff(tr) >= 0)),
        }

    # Which class pairs have non-overlapping TimeRadians support? Any such pair
    # is separable by the clock alone, with no reference to attack behaviour.
    disjoint = []
    items = list(arcs.items())
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i][1], items[j][1]
            if (a["time_radians_max"] < b["time_radians_min"]
                    or b["time_radians_max"] < a["time_radians_min"]):
                disjoint.append([items[i][0], items[j][0]])

    return {
        "n_rows": int(len(df)),
        "n_cols": int(df.shape[1]),
        "label_counts": {LABEL_NAMES[int(k)]: int(v)
                         for k, v in df["Label"].value_counts().sort_index().items()},
        "label_runs": [[LABEL_NAMES[k], n] for k, n in runs],
        "n_label_runs": len(runs),
        "one_contiguous_run_per_class": len(runs) == df["Label"].nunique(),
        "zero_variance_columns": zero_var,
        "per_class_time_arc": arcs,
        "clock_separable_class_pairs": disjoint,
    }


def split_random(df: pd.DataFrame, test_ratio: float, seed: int):
    from sklearn.model_selection import train_test_split
    idx = np.arange(len(df))
    tr, te = train_test_split(idx, test_size=test_ratio, random_state=seed,
                              stratify=df["Label"].to_numpy())
    return tr, te


def split_time_based(df: pd.DataFrame, test_ratio: float):
    """The README's recommended Option 1: sort by TimeRadians, per class take
    the first (1 - ratio) as train and the trailing ratio as test."""
    train_idx, test_idx = [], []
    order = df.sort_values("TimeRadians", kind="mergesort").index
    ordered = df.loc[order]
    for lbl in ordered["Label"].unique():
        pos = ordered.index[ordered["Label"] == lbl].to_numpy()
        n_test = int(len(pos) * test_ratio)
        if n_test > 0:
            train_idx.append(pos[:-n_test])
            test_idx.append(pos[-n_test:])
        else:
            train_idx.append(pos)
    tr = np.concatenate(train_idx)
    te = np.concatenate(test_idx) if test_idx else np.array([], dtype=int)
    # positional, not label-based
    pos_of = {lab: i for i, lab in enumerate(df.index)}
    return (np.array([pos_of[i] for i in tr]),
            np.array([pos_of[i] for i in te]))


def run_arm(name: str, df: pd.DataFrame, feature_cols: list[str],
            split: str, test_ratio: float, seed: int) -> dict:
    from sklearn.metrics import accuracy_score, f1_score

    X = df[feature_cols].to_numpy(dtype=float)
    y = df["Label"].to_numpy()

    if split == "random":
        tr, te = split_random(df, test_ratio, seed)
    elif split == "time":
        tr, te = split_time_based(df, test_ratio)
    else:
        raise ValueError(split)

    clf = make_clf()
    clf.fit(X[tr], y[tr])
    pred = clf.predict(X[te])

    labels = sorted(df["Label"].unique())
    per_class = f1_score(y[te], pred, labels=labels, average=None, zero_division=0)
    return {
        "arm": name,
        "split": split,
        "n_features": len(feature_cols),
        "features": feature_cols,
        "n_train": int(len(tr)),
        "n_test": int(len(te)),
        "accuracy": round(float(accuracy_score(y[te], pred)), 4),
        "macro_f1": round(float(f1_score(y[te], pred, average="macro",
                                         zero_division=0)), 4),
        "per_class_f1": {LABEL_NAMES[int(l)]: round(float(v), 4)
                         for l, v in zip(labels, per_class)},
    }


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default="data/onair/external/cucdid_v3",
                   help="Unpacked CuCD-ID release root (contains Data/ and Code/).")
    p.add_argument("--out-json", default="data/onair/models/benchmark_fayyaz.json")
    p.add_argument("--test-ratio", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    raw_path = os.path.join(args.data_dir, "Data/Raw/consolidated_dataset_raw.csv")
    if not os.path.exists(raw_path):
        sys.exit(f"raw table not found at {raw_path} — see the fetch command in "
                 f"this script's docstring")

    integrity = {}
    for rel, want in PUBLISHED_SHA256.items():
        path = os.path.join(args.data_dir, rel)
        got = sha256_of(path) if os.path.exists(path) else None
        integrity[rel] = {"published": want, "computed": got, "match": got == want}

    df = pd.read_csv(raw_path)
    structure = describe_structure(df)

    all_feats = [c for c in df.columns if c != "Label"]
    live = [c for c in all_feats if c not in structure["zero_variance_columns"]]
    behaviour_only = [c for c in live if c not in MEMORY_COLS and c not in TIME_COLS]
    memory_live = [c for c in MEMORY_COLS if c in live]

    # Single-feature sweep: how many individual columns already saturate the
    # 5-class problem on their own? On a balanced 5-class task chance is 0.20,
    # so anything near 1.0 means that one column is a scenario fingerprint.
    singles = sorted(
        (run_arm(f"S_{c}", df, [c], "random", args.test_ratio, args.seed)
         for c in live),
        key=lambda a: -a["accuracy"],
    )
    single_feature_accuracy = {a["features"][0]: a["accuracy"] for a in singles}

    arms = [
        run_arm("A1_all_random", df, live, "random", args.test_ratio, args.seed),
        run_arm("A2_all_timesplit", df, live, "time", args.test_ratio, args.seed),
        run_arm("A3_timeradians_only", df, TIME_COLS, "random", args.test_ratio, args.seed),
        run_arm("A4_memory_only", df, memory_live, "random", args.test_ratio, args.seed),
        run_arm("A5_behaviour_random", df, behaviour_only, "random", args.test_ratio, args.seed),
        run_arm("A6_behaviour_timesplit", df, behaviour_only, "time", args.test_ratio, args.seed),
    ]
    by = {a["arm"]: a for a in arms}

    result = {
        "dataset": "CuCD-ID v3 (Mendeley 10.17632/7n2d42pm3n.3)",
        "paper": "Fayyaz et al., Data in Brief 65 (2026) 112598",
        "model": "sklearn HistGradientBoostingClassifier (same hyperparameters as "
                 "our deployed v3 attack classifier)",
        "integrity": integrity,
        "structure": structure,
        "arms": arms,
        "single_feature_accuracy": single_feature_accuracy,
        "n_single_features_above_0_95": sum(
            1 for v in single_feature_accuracy.values() if v >= 0.95),
        "deltas": {
            "run_identity_contribution_acc": round(
                by["A1_all_random"]["accuracy"] - by["A5_behaviour_random"]["accuracy"], 4),
            "temporal_split_cost_acc": round(
                by["A5_behaviour_random"]["accuracy"] - by["A6_behaviour_timesplit"]["accuracy"], 4),
            "readme_split_leak_remaining_acc": round(
                by["A2_all_timesplit"]["accuracy"] - by["A6_behaviour_timesplit"]["accuracy"], 4),
        },
        "loio_possible": False,
        "loio_reason": "one contiguous collection run per class (5,000 rows each); "
                       "leave-one-instance-out needs >= 2 independent runs per class",
    }

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w") as f:
        json.dump(result, f, indent=2)

    print(f"integrity: " + ", ".join(
        f"{os.path.basename(k)}={'OK' if v['match'] else 'MISMATCH'}"
        for k, v in integrity.items()))
    print(f"structure: {structure['n_rows']} rows x {structure['n_cols']} cols, "
          f"{structure['n_label_runs']} label runs "
          f"(one per class = {structure['one_contiguous_run_per_class']})")
    print(f"clock-separable class pairs: {structure['clock_separable_class_pairs']}")
    print()
    print(f"{'arm':26s} {'split':6s} {'feats':>5s} {'acc':>7s} {'macroF1':>8s}")
    for a in arms:
        print(f"{a['arm']:26s} {a['split']:6s} {a['n_features']:5d} "
              f"{a['accuracy']:7.4f} {a['macro_f1']:8.4f}")
    print()
    print(f"single-feature accuracy (5-class balanced, chance = 0.20) — "
          f"{result['n_single_features_above_0_95']}/{len(live)} columns reach >= 0.95 alone:")
    for name, acc in list(single_feature_accuracy.items())[:12]:
        print(f"  {name:32s} {acc:.4f}")
    print()
    for k, v in result["deltas"].items():
        print(f"{k:38s} {v:+.4f}")
    print(f"\nwrote {args.out_json}")


if __name__ == "__main__":
    main()
