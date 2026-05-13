"""Train an Isolation Forest on nominal OnAIR security CSVs.

Tier 1 of the AI anomaly detection plan. Reads CSVs from `data/onair/csv`,
builds raw + delta features, fits an Isolation Forest, and pickles the model +
feature schema to `data/onair/models/iforest_v1.pkl`.

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
import pandas as pd
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


def _per_scenario_report(scores: np.ndarray, scenarios: pd.Series) -> None:
    """Print per-scenario score distribution.

    Columns: rows, %flag (score<0), min, p1, p5, p25, p50, mean.
    """
    header = (f"{'scenario':<20}{'rows':>7} {'%flag':>6} "
              f"{'min':>9} {'p1':>9} {'p5':>9} {'p25':>9} {'p50':>9} {'mean':>9}")
    print(header)
    print("-" * len(header))
    for name in sorted(scenarios.unique()):
        mask = (scenarios.to_numpy() == name)
        s = scores[mask]
        _print_scenario_row(name, s)


def _print_scenario_row(name: str, s: np.ndarray) -> None:
    n_flag = int((s < 0).sum())
    pct_flag = 100.0 * n_flag / len(s)
    print(f"{name:<20}{len(s):>7} {pct_flag:>5.1f}% "
          f"{s.min():>+9.4f} {np.percentile(s,1):>+9.4f} "
          f"{np.percentile(s,5):>+9.4f} {np.percentile(s,25):>+9.4f} "
          f"{np.percentile(s,50):>+9.4f} {s.mean():>+9.4f}")


def _cross_mode_min(
    models: dict, X: np.ndarray, df_scenarios: pd.Series, scenarios: list[str]
) -> np.ndarray:
    """Compute the worst (most negative) score for each (train, score) pair."""
    n = len(scenarios)
    out = np.zeros((n, n), dtype=np.float64)
    masks = {scn: (df_scenarios.to_numpy() == scn) for scn in scenarios}
    for i, train_scn in enumerate(scenarios):
        m = models[train_scn]
        for j, score_scn in enumerate(scenarios):
            sub = X[masks[score_scn]]
            out[i, j] = float(m.decision_function(sub).min())
    return out


def _print_min_matrix(matrix: np.ndarray, scenarios: list[str]) -> None:
    short = [s[:9] for s in scenarios]
    header = " " * 20 + "".join(f"{c:>11}" for c in short)
    print(header)
    print("-" * len(header))
    for i, train_scn in enumerate(scenarios):
        row = "".join(f"{matrix[i, j]:>+11.4f}" for j in range(len(scenarios)))
        print(f"{train_scn:<20}{row}")


def train(
    csv_dir: str,
    *,
    n_estimators: int = 200,
    contamination: float = 0.01,
    random_state: int = 42,
    include_deltas: bool = True,
    manifest: str | list[str] | None = None,
    balance: bool = False,
    exclude_scenarios: list[str] | None = None,
    skip_warmup_rows: int = 0,
) -> dict:
    exclude_scenarios = list(exclude_scenarios or [])
    t0 = time.perf_counter()
    if manifest:
        df, stats = load_with_labels(csv_dir, manifest, drop_unlabeled=True,
                                     skip_warmup_rows=skip_warmup_rows)
    else:
        df, stats = load(csv_dir, skip_warmup_rows=skip_warmup_rows)
    print(f"loaded {stats.files_kept}/{stats.files_total} files, {df.shape[0]} rows "
          f"(skipped: leaks={stats.files_skipped_leaks} align={stats.files_skipped_alignment})")
    if "__scenario" in df.columns:
        print("  scenario distribution:")
        for name, n in df["__scenario"].value_counts().items():
            print(f"    {name}: {n}")

    t1 = time.perf_counter()
    # Build features on the FULL labeled df so per-row deltas are computed
    # against the true chronological neighbour (file boundaries respected).
    # Subsampling for class balance happens AFTER feature build so it only
    # affects which rows the IF sees during fit, not the deltas themselves.
    X, schema = build_features(df, include_deltas=include_deltas)
    print(f"feature matrix: {X.shape}  (scalars={len(schema.scalar_columns)}, "
          f"list-cols={len(schema.list_columns)}, dropped-text={len(schema.dropped_text_columns)})")
    print(f"  feature build: {time.perf_counter()-t1:.2f}s")

    fit_idx: np.ndarray | None = None
    if exclude_scenarios or balance:
        if "__scenario" not in df.columns:
            raise ValueError("--balance / --exclude-scenarios require manifest-labeled rows")
        kept = df
        if exclude_scenarios:
            unknown = set(exclude_scenarios) - set(df["__scenario"].unique())
            if unknown:
                raise ValueError(f"--exclude-scenarios names not present: {sorted(unknown)}")
            kept = df[~df["__scenario"].isin(exclude_scenarios)]
            print(f"  excluding scenarios {exclude_scenarios}: "
                  f"{len(df) - len(kept)} rows removed from fit, {len(kept)} retained")
        if balance:
            per_scn = kept["__scenario"].value_counts()
            n_per = int(per_scn.min())
            sampled = (
                kept.groupby("__scenario", group_keys=False)
                    .sample(n=n_per, random_state=random_state)
            )
            fit_idx = np.sort(sampled.index.to_numpy())
            print(f"  balanced fit subset: {len(fit_idx)} rows "
                  f"({n_per} per scenario × {len(per_scn)} scenarios)")
        else:
            fit_idx = np.sort(kept.index.to_numpy())

    X_fit = X[fit_idx] if fit_idx is not None else X

    t2 = time.perf_counter()
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_fit)
    print(f"  IF fit: {time.perf_counter()-t2:.2f}s "
          f"({n_estimators} trees, contamination={contamination}, fit_rows={X_fit.shape[0]})")

    scores = model.decision_function(X)
    score_stats = _summarize_scores(scores)
    print("  full-labeled-set decision_function stats:")
    for k, v in score_stats.items():
        print(f"    {k:>5}: {v:+.4f}")
    n_flagged = int((scores < 0).sum())
    print(f"  flagged-as-anomaly on full labeled set: {n_flagged}/{len(scores)} "
          f"({100*n_flagged/len(scores):.2f}%)")

    if "__scenario" in df.columns:
        print("  per-scenario score distribution (full labeled set):")
        _per_scenario_report(scores, df["__scenario"])

    print(f"  total: {time.perf_counter()-t0:.2f}s")

    return {
        "model": model,
        "schema": asdict(schema),
        "n_train_rows": int(X_fit.shape[0]),
        "n_features": int(X.shape[1]),
        "score_stats": score_stats,
        "config": {
            "n_estimators": n_estimators,
            "contamination": contamination,
            "random_state": random_state,
            "include_deltas": include_deltas,
            "balance": balance,
            "exclude_scenarios": list(exclude_scenarios),
            "skip_warmup_rows": skip_warmup_rows,
        },
    }


def train_per_scenario(
    csv_dir: str,
    *,
    n_estimators: int = 200,
    contamination: float = 0.01,
    random_state: int = 42,
    include_deltas: bool = True,
    manifest: str | list[str] | None = None,
    skip_warmup_rows: int = 0,
    label_column: str = "__scenario",
    mode_transient_skip: int = 0,
    min_rows_per_label: int = 100,
    exclude_labels: list[str] | None = None,
) -> dict:
    """Train one IsolationForest per label group; share the feature schema.

    `label_column` selects which loader-attached column drives the grouping
    (default `__scenario`; pass `__adcs_mode` for v4 per-ADCS-mode IFs).
    Label groups with fewer than `min_rows_per_label` rows are skipped with
    a warning — catches `MODE_UNKNOWN` placeholder rows without forcing
    callers to remember the magic exclude.
    """
    exclude_labels = list(exclude_labels or [])
    if not manifest:
        raise ValueError("--per-scenario requires --manifest")
    t0 = time.perf_counter()
    df, stats = load_with_labels(csv_dir, manifest, drop_unlabeled=True,
                                 skip_warmup_rows=skip_warmup_rows,
                                 mode_transient_skip=mode_transient_skip)
    print(f"loaded {stats.files_kept}/{stats.files_total} files, {df.shape[0]} rows "
          f"(skipped: leaks={stats.files_skipped_leaks} align={stats.files_skipped_alignment})")
    if label_column not in df.columns:
        raise ValueError(
            f"--label-column {label_column!r} not present in loaded frame. "
            f"Available bookkeeping cols: {[c for c in df.columns if c.startswith('__')]}"
        )
    print(f"  grouping on {label_column!r}")
    print("  label distribution:")
    for name, n in df[label_column].value_counts().items():
        print(f"    {name}: {n}")

    t1 = time.perf_counter()
    X, schema = build_features(df, include_deltas=include_deltas)
    print(f"feature matrix: {X.shape}  (scalars={len(schema.scalar_columns)}, "
          f"list-cols={len(schema.list_columns)}, dropped-text={len(schema.dropped_text_columns)})")
    print(f"  feature build: {time.perf_counter()-t1:.2f}s")

    all_labels = sorted(df[label_column].unique())
    counts = df[label_column].value_counts().to_dict()
    skipped: list[tuple[str, str]] = []
    scenarios: list[str] = []
    for lbl in all_labels:
        if lbl in exclude_labels:
            skipped.append((lbl, "explicit --exclude"))
            continue
        if counts[lbl] < min_rows_per_label:
            skipped.append((lbl, f"only {counts[lbl]} rows < min_rows_per_label={min_rows_per_label}"))
            continue
        scenarios.append(lbl)
    if skipped:
        print("  skipped label groups:")
        for lbl, why in skipped:
            print(f"    {lbl}: {why}")
    if not scenarios:
        raise ValueError(
            "no label groups large enough to train. Check --label-column and --min-rows-per-label."
        )

    models: dict[str, IsolationForest] = {}
    fit_sizes: dict[str, int] = {}
    score_stats: dict[str, dict] = {}

    t2 = time.perf_counter()
    for scn in scenarios:
        mask = (df[label_column].to_numpy() == scn)
        Xs = X[mask]
        m = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        )
        m.fit(Xs)
        models[scn] = m
        fit_sizes[scn] = int(Xs.shape[0])
        score_stats[scn] = _summarize_scores(m.decision_function(Xs))
    print(f"  IF fit ({len(scenarios)} models): {time.perf_counter()-t2:.2f}s "
          f"({n_estimators} trees each, contamination={contamination})")

    print(f"  per-{label_column} diagonal (each IF scored on its OWN group):")
    header = (f"{'scenario':<20}{'rows':>7} {'%flag':>6} "
              f"{'min':>9} {'p1':>9} {'p5':>9} {'p25':>9} {'p50':>9} {'mean':>9}")
    print(header)
    print("-" * len(header))
    for scn in scenarios:
        mask = (df[label_column].to_numpy() == scn)
        s = models[scn].decision_function(X[mask])
        _print_scenario_row(scn, s)

    print("  cross-mode min (rows=train, cols=score; values=min decision_function):")
    matrix = _cross_mode_min(models, X, df[label_column], scenarios)
    _print_min_matrix(matrix, scenarios)

    print(f"  total: {time.perf_counter()-t0:.2f}s")

    return {
        "models": models,
        "schema": asdict(schema),
        "n_train_rows_per_scenario": fit_sizes,
        "n_features": int(X.shape[1]),
        "score_stats": score_stats,
        "cross_mode_min": {
            scenarios[i]: {scenarios[j]: float(matrix[i, j]) for j in range(len(scenarios))}
            for i in range(len(scenarios))
        },
        "label_column": label_column,
        "config": {
            "n_estimators": n_estimators,
            "contamination": contamination,
            "random_state": random_state,
            "include_deltas": include_deltas,
            "per_scenario": True,
            "skip_warmup_rows": skip_warmup_rows,
            "label_column": label_column,
            "mode_transient_skip": mode_transient_skip,
            "exclude_labels": list(exclude_labels),
            "min_rows_per_label": min_rows_per_label,
        },
    }


def save(artifact: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(artifact, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"saved -> {path} ({os.path.getsize(path)/1e6:.2f} MB)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv-dir", default="data/onair/csv")
    p.add_argument("--out", default="data/onair/models/iforest_v1.pkl")
    p.add_argument("--n-estimators", type=int, default=200)
    p.add_argument("--contamination", type=float, default=0.01)
    p.add_argument("--no-deltas", action="store_true",
                   help="Train on raw values only (no delta features)")
    p.add_argument("--manifest", default=None,
                   help="Manifest path/dir/comma-list. With this, only labeled rows train.")
    p.add_argument("--balance", action="store_true",
                   help="Subsample each __scenario to the smallest class size before fitting "
                        "(deltas are still built on the full labeled df). Requires --manifest.")
    p.add_argument("--exclude-scenarios", default="",
                   help="Comma-separated __scenario names to exclude from fitting. "
                        "Excluded rows still appear in the per-scenario diagnostic so you "
                        "can see how the model scores held-out modes. Requires --manifest.")
    p.add_argument("--per-scenario", action="store_true",
                   help="Train one IsolationForest per __scenario (shared feature schema). "
                        "Pickle stores `models: dict[scenario -> IF]` instead of a single "
                        "`model`. Inference must route by mode. Requires --manifest.")
    p.add_argument("--skip-warmup-rows", type=int, default=30,
                   help="Drop the first N rows of each CSV file at load time. Removes "
                        "MID-arrival transients (huge first-arrival deltas). 0 disables.")
    p.add_argument("--label-column", default="__scenario",
                   help="Loader-attached column to group --per-scenario IFs on "
                        "(default __scenario; v4 per-ADCS-mode IFs use __adcs_mode).")
    p.add_argument("--mode-transient-skip", type=int, default=0,
                   help="When grouping on __adcs_mode, drop the first N rows after "
                        "each mode change (per file). Removes FSW state-propagation "
                        "transients the same way --skip-warmup-rows removes SBN ones.")
    p.add_argument("--min-rows-per-label", type=int, default=100,
                   help="Per-scenario IFs: skip any label group with fewer rows than "
                        "this. Catches MODE_UNKNOWN placeholder rows automatically.")
    p.add_argument("--exclude-labels", default="",
                   help="Comma-separated label values to skip when --per-scenario "
                        "groups by --label-column. Mode-flavoured analog of "
                        "--exclude-scenarios.")
    args = p.parse_args()

    manifest = args.manifest
    if manifest and "," in manifest:
        manifest = manifest.split(",")
    if args.per_scenario:
        if args.balance or args.exclude_scenarios:
            raise SystemExit("--per-scenario is incompatible with --balance / --exclude-scenarios")
        exclude_labels = [s.strip() for s in args.exclude_labels.split(",") if s.strip()]
        art = train_per_scenario(
            args.csv_dir,
            n_estimators=args.n_estimators,
            contamination=args.contamination,
            include_deltas=not args.no_deltas,
            manifest=manifest,
            skip_warmup_rows=args.skip_warmup_rows,
            label_column=args.label_column,
            mode_transient_skip=args.mode_transient_skip,
            min_rows_per_label=args.min_rows_per_label,
            exclude_labels=exclude_labels,
        )
    else:
        exclude = [s.strip() for s in args.exclude_scenarios.split(",") if s.strip()]
        art = train(
            args.csv_dir,
            n_estimators=args.n_estimators,
            contamination=args.contamination,
            include_deltas=not args.no_deltas,
            manifest=manifest,
            balance=args.balance,
            exclude_scenarios=exclude,
            skip_warmup_rows=args.skip_warmup_rows,
        )
    save(art, args.out)


if __name__ == "__main__":
    main()
