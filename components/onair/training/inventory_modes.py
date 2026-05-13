"""v4 step 1 — mode inventory on the 4 multi-uptime manifests.

Read-only diagnostic. Loads the 4 long-uptime baselines, derives `__adcs_mode`
from each row's `ADCS_GNC.Mode`, prints rows-per-mode (the gate for the
decision between full 4-IF retrain vs partial-mode retrain + static fallback),
and scores each mode bucket through the v3 `nominal_ops` IsolationForest so we
can see the per-mode score distribution the v3 routing premise was implicitly
modeling.

Does NOT train, save, or modify any pickle. Run:

    /home/maddoxw/.virtualenvs/nos3/bin/python3 \
        components/onair/training/inventory_modes.py
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from features import build_features  # noqa: E402
from loader import load_with_labels  # noqa: E402


MODE_NAMES = {
    0: "MODE_PASSIVE",
    1: "MODE_BDOT",
    2: "MODE_SUNSAFE",
    3: "MODE_INERTIAL",
}

DEFAULT_MANIFESTS = [
    "data/onair/scenarios/manifest_2026-05-08T19-45-04Z.json",  # T+30min
    "data/onair/scenarios/manifest_2026-05-08T21-15-45Z.json",  # T+2h
    "data/onair/scenarios/manifest_2026-05-08T23-15-21Z.json",  # T+4h
    "data/onair/scenarios/manifest_2026-05-09T01-14-56Z.json",  # T+6h
]

DEFAULT_MODEL = "data/onair/models/iforest_per_scenario_v3_multiuptime.pkl"
ADCS_MODE_COL = "ADCS_GNC.Mode"


def _derive_adcs_mode(df: pd.DataFrame) -> pd.Series:
    """Map ADCS_GNC.Mode → MODE_PASSIVE/BDOT/SUNSAFE/INERTIAL/MODE_UNKNOWN.

    The CSV column stores either a numeric string (e.g. `'2'`) or the
    `[0]` placeholder used for "never received yet". Anything that does
    not parse to one of {0,1,2,3} is bucketed as MODE_UNKNOWN.
    """
    raw = df[ADCS_MODE_COL].astype(str)
    nums = pd.to_numeric(raw, errors="coerce")
    out = nums.map(MODE_NAMES)
    return out.fillna("MODE_UNKNOWN")


def _summarize_scores(s: np.ndarray) -> dict:
    return {
        "rows": int(s.size),
        "%flag": float(100.0 * (s < 0).mean()),
        "min": float(s.min()),
        "p1": float(np.percentile(s, 1)),
        "p5": float(np.percentile(s, 5)),
        "p50": float(np.percentile(s, 50)),
        "p95": float(np.percentile(s, 95)),
        "mean": float(s.mean()),
    }


def _print_mode_row(name: str, s: np.ndarray) -> None:
    if s.size == 0:
        print(f"{name:<18}{0:>8}      —")
        return
    n_flag = int((s < 0).sum())
    pct_flag = 100.0 * n_flag / s.size
    print(
        f"{name:<18}{s.size:>8} {pct_flag:>5.1f}% "
        f"{s.min():>+9.4f} {np.percentile(s,1):>+9.4f} "
        f"{np.percentile(s,5):>+9.4f} {np.percentile(s,50):>+9.4f} "
        f"{np.percentile(s,95):>+9.4f} {s.mean():>+9.4f}"
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv-dir", default="data/onair/csv")
    p.add_argument(
        "--manifest", nargs="+", default=DEFAULT_MANIFESTS,
        help="manifest_*.json paths to load (default: 4 multi-uptime).",
    )
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument(
        "--skip-warmup-rows", type=int, default=30,
        help="Match v3 training (default 30).",
    )
    p.add_argument(
        "--score-scenario", default="nominal_ops",
        help="Which per-scenario IF in the pickle to score with.",
    )
    p.add_argument(
        "--no-score", action="store_true",
        help="Skip feature build + IF scoring. Useful for quick mode-distribution "
             "checks against probe manifests where stack uptime makes IF scores OOD.",
    )
    args = p.parse_args()

    t0 = time.perf_counter()

    missing = [m for m in args.manifest if not os.path.exists(m)]
    if missing:
        print("missing manifest paths:", missing)
        return 2
    if not args.no_score and not os.path.exists(args.model):
        print("missing model pickle:", args.model)
        return 2

    print(f"manifests ({len(args.manifest)}):")
    for m in args.manifest:
        print(f"  {m}")
    print(f"model: {args.model}")
    print(f"score-scenario IF: {args.score_scenario}")
    print(f"skip_warmup_rows: {args.skip_warmup_rows}")
    print()

    print("loading + labeling rows...")
    df, stats = load_with_labels(
        args.csv_dir, args.manifest,
        drop_unlabeled=True,
        skip_warmup_rows=args.skip_warmup_rows,
    )
    print(f"  rows kept: {len(df)} from {stats.files_kept}/{stats.files_total} files")
    if ADCS_MODE_COL not in df.columns:
        print(f"ERROR: '{ADCS_MODE_COL}' not in loaded columns. Did the CSV schema change?")
        return 3

    print()
    print("scenario distribution:")
    for name, n in df["__scenario"].value_counts().sort_index().items():
        print(f"  {name:<20} {n:>8}")

    df["__adcs_mode"] = _derive_adcs_mode(df)

    print()
    print("=" * 78)
    print("rows-per-mode (the v4 gate):")
    print("=" * 78)
    mode_counts = df["__adcs_mode"].value_counts()
    for name in list(MODE_NAMES.values()) + ["MODE_UNKNOWN"]:
        n = int(mode_counts.get(name, 0))
        marker = ""
        if name in ("MODE_PASSIVE", "MODE_BDOT") and 0 < n < 5000:
            marker = "  <-- LOW (< 5K threshold)"
        elif n == 0:
            marker = "  <-- EMPTY"
        print(f"  {name:<18} {n:>8}{marker}")

    print()
    print("scenario x mode crosstab (rows):")
    xtab = pd.crosstab(df["__scenario"], df["__adcs_mode"], margins=True, margins_name="ALL")
    print(xtab.to_string())

    raw_mode_counts = (
        df[ADCS_MODE_COL]
        .astype(str)
        .value_counts()
        .head(8)
        .to_dict()
    )
    print()
    print(f"raw {ADCS_MODE_COL} value distribution (top 8):")
    for k, v in raw_mode_counts.items():
        print(f"  {k!r:<10} {v:>8}")

    if args.no_score:
        print()
        print(f"--no-score: skipping IF scoring. total: {time.perf_counter()-t0:.2f}s")
        return 0

    print()
    print("loading v3 model + scoring per-mode under nominal_ops IF...")
    with open(args.model, "rb") as f:
        art = pickle.load(f)
    schema = art.get("schema")
    models = art.get("models")
    if models is None:
        print("ERROR: model pickle missing 'models' dict (expected per-scenario layout).")
        return 4
    if args.score_scenario not in models:
        print(f"ERROR: '{args.score_scenario}' not in models. Available: {sorted(models)}")
        return 4
    expected_features = int(art.get("n_features", -1))

    t_feat = time.perf_counter()
    X, _schema_out = build_features(df, include_deltas=True, schema=schema)
    print(f"  feature matrix: {X.shape} (build {time.perf_counter()-t_feat:.2f}s)")
    if expected_features > 0 and X.shape[1] != expected_features:
        print(
            f"WARNING: feature width {X.shape[1]} != trained {expected_features}. "
            "Scores will be unreliable."
        )

    model = models[args.score_scenario]
    t_score = time.perf_counter()
    scores = model.decision_function(X)
    print(f"  scored {len(scores)} rows in {time.perf_counter()-t_score:.2f}s")

    print()
    print("=" * 78)
    print(f"per-mode score distribution under v3 {args.score_scenario!r} IF:")
    print("=" * 78)
    hdr = (
        f"{'mode':<18}{'rows':>8} {'%flag':>6} "
        f"{'min':>9} {'p1':>9} {'p5':>9} {'p50':>9} {'p95':>9} {'mean':>9}"
    )
    print(hdr)
    print("-" * len(hdr))
    modes_present = (
        list(MODE_NAMES.values()) + ["MODE_UNKNOWN"]
    )
    mode_arr = df["__adcs_mode"].to_numpy()
    for name in modes_present:
        mask = (mode_arr == name)
        if not mask.any():
            continue
        _print_mode_row(name, scores[mask])

    print()
    print("=" * 78)
    print("per-(scenario, mode) score distribution (only cells with rows):")
    print("=" * 78)
    print(hdr)
    print("-" * len(hdr))
    scn_arr = df["__scenario"].to_numpy()
    for scn in sorted(df["__scenario"].unique()):
        for mode in modes_present:
            mask = (scn_arr == scn) & (mode_arr == mode)
            n = int(mask.sum())
            if n == 0:
                continue
            label = f"{scn[:11]}|{mode[5:]}"
            _print_mode_row(label, scores[mask])

    print()
    print(f"total: {time.perf_counter()-t0:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
