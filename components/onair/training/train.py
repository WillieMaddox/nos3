"""Train an Isolation Forest on nominal OnAIR security CSVs.

Tier 1 of the AI anomaly detection plan. Reads CSVs from
`fsw/build/exe/cpu1/data/onair/csv`, builds raw + delta features, fits an
Isolation Forest, and pickles the model + feature schema to
`data/onair/models/iforest_v1.pkl`.

The pickle contains everything the inference plugin needs to reproduce the
exact same feature transformation at runtime.
"""

from __future__ import annotations

import argparse
import os
import pickle
import time
from dataclasses import asdict

import numpy as np
from sklearn.ensemble import IsolationForest

from features import FeatureSchema, build_features
from loader import load, load_with_labels


def _summarize_scores(scores: np.ndarray) -> dict:
    return {
        "min": float(scores.min()),
        "max": float(scores.max()),
        "mean": float(scores.mean()),
        "p1": float(np.percentile(scores, 1)),
        "p5": float(np.percentile(scores, 5)),
        "p50": float(np.percentile(scores, 50)),
        "p95": float(np.percentile(scores, 95)),
    }


def train(
    csv_dir: str,
    *,
    n_estimators: int = 200,
    contamination: float = 0.01,
    random_state: int = 42,
    include_deltas: bool = True,
    manifest: str | list[str] | None = None,
) -> dict:
    t0 = time.perf_counter()
    if manifest:
        df, stats = load_with_labels(csv_dir, manifest, drop_unlabeled=True)
    else:
        df, stats = load(csv_dir)
    print(f"loaded {stats.files_kept}/{stats.files_total} files, {df.shape[0]} rows "
          f"(skipped: leaks={stats.files_skipped_leaks} align={stats.files_skipped_alignment})")
    if "__scenario" in df.columns:
        print("  scenario distribution:")
        for name, n in df["__scenario"].value_counts().items():
            print(f"    {name}: {n}")

    t1 = time.perf_counter()
    X, schema = build_features(df, include_deltas=include_deltas)
    print(f"feature matrix: {X.shape}  (scalars={len(schema.scalar_columns)}, "
          f"list-cols={len(schema.list_columns)}, dropped-text={len(schema.dropped_text_columns)})")
    print(f"  feature build: {time.perf_counter()-t1:.2f}s")

    t2 = time.perf_counter()
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X)
    print(f"  IF fit: {time.perf_counter()-t2:.2f}s ({n_estimators} trees, contamination={contamination})")

    scores = model.decision_function(X)
    score_stats = _summarize_scores(scores)
    print("  training-set decision_function stats:")
    for k, v in score_stats.items():
        print(f"    {k:>5}: {v:+.4f}")
    n_flagged = int((scores < 0).sum())
    print(f"  flagged-as-anomaly on training: {n_flagged}/{len(scores)} "
          f"({100*n_flagged/len(scores):.2f}%)")
    print(f"  total: {time.perf_counter()-t0:.2f}s")

    return {
        "model": model,
        "schema": asdict(schema),
        "n_train_rows": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "score_stats": score_stats,
        "config": {
            "n_estimators": n_estimators,
            "contamination": contamination,
            "random_state": random_state,
            "include_deltas": include_deltas,
        },
    }


def save(artifact: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(artifact, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"saved -> {path} ({os.path.getsize(path)/1e6:.2f} MB)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv-dir", default="fsw/build/exe/cpu1/data/onair/csv")
    p.add_argument("--out", default="data/onair/models/iforest_v1.pkl")
    p.add_argument("--n-estimators", type=int, default=200)
    p.add_argument("--contamination", type=float, default=0.01)
    p.add_argument("--no-deltas", action="store_true",
                   help="Train on raw values only (no delta features)")
    p.add_argument("--manifest", default=None,
                   help="Manifest path/dir/comma-list. With this, only labeled rows train.")
    args = p.parse_args()

    manifest = args.manifest
    if manifest and "," in manifest:
        manifest = manifest.split(",")
    art = train(
        args.csv_dir,
        n_estimators=args.n_estimators,
        contamination=args.contamination,
        include_deltas=not args.no_deltas,
        manifest=manifest,
    )
    save(art, args.out)


if __name__ == "__main__":
    main()
