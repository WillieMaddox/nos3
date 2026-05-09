"""Pick per-scenario IF score thresholds at a target false-positive rate.

The `decision_function` output of `sklearn.ensemble.IsolationForest` is offset
so that "score < 0" means "below the contamination percentile of training
scores". That semantic is fragile across stack/data drift: v2 (single-uptime)
flagged at threshold ≈ −0.019 for 1% nominal FP; v3 (multi-uptime) needs
≈ +0.07 because the score distribution shifts when the model spans more
nominal variance. The hardcoded `AnomalyThreshold = 0.0` in
`nos3_security.ini` doesn't survive that shift.

This calibrator scores a recent-nominal corpus through a per-scenario model,
sorts the scores per scenario, and picks the threshold at which a chosen
fraction of the nominal data flags. The JSON it writes can be consumed
directly by the inference plugin (or by `eval_attacks.py --threshold-file`,
when that lands).

Usage:
    python3 components/onair/training/calibrate.py \\
        --model data/onair/models/iforest_per_scenario_v3_multiuptime.pkl \\
        --manifest data/onair/scenarios/manifest_2026-05-08T19-45-04Z.json,\\
                   data/onair/scenarios/manifest_2026-05-08T21-15-45Z.json
    # Output: <model>.calibration.json next to the model.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pickle
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import build_features  # noqa: E402
from loader import load_with_labels  # noqa: E402

DEFAULT_MODEL = "data/onair/models/iforest_per_scenario_v2_warmup30.pkl"
DEFAULT_CSV_DIR = "data/onair/csv"
MIN_ROWS_PER_SCENARIO = 100  # below this, calibration is unreliable


def calibrate(
    scores: np.ndarray, scenarios: np.ndarray, models: dict,
    *, target_fp_rate: float,
) -> tuple[dict[str, float | None], dict[str, dict]]:
    """Per-scenario percentile threshold at target_fp_rate.

    Returns (thresholds, diagnostics). thresholds[scn] is None when the
    scenario has too few rows to calibrate reliably.
    """
    thresholds: dict[str, float | None] = {}
    diag: dict[str, dict] = {}
    for scn in sorted(models):
        mask = (scenarios == scn)
        n = int(mask.sum())
        diag[scn] = {"n_rows": n}
        if n < MIN_ROWS_PER_SCENARIO:
            thresholds[scn] = None
            diag[scn]["reason"] = f"too few rows (<{MIN_ROWS_PER_SCENARIO})"
            continue
        s = np.sort(scores[mask])
        # Threshold at which `target_fp_rate` of nominal flags. Taking the
        # k-th smallest score (1-indexed: k = round(target_fp * n), clipped
        # to [1, n]) means exactly k rows have score < threshold under
        # strict inequality, matching the FP semantic the plugin uses.
        k = int(round(target_fp_rate * n))
        k = max(1, min(n, k))
        thr = float(s[k - 1])
        thresholds[scn] = thr
        diag[scn].update({
            "threshold": thr,
            "min": float(s[0]),
            "p1": float(np.percentile(s, 1)),
            "p5": float(np.percentile(s, 5)),
            "p50": float(np.percentile(s, 50)),
            "max": float(s[-1]),
            "n_below_thr": k,
            "actual_fp_rate": k / n,
        })
    return thresholds, diag


def _print_table(diag: dict[str, dict], target_fp_rate: float) -> None:
    print(f"\nper-scenario thresholds @ FP={target_fp_rate*100:.1f}%:")
    print(f"  {'scenario':>20s}  {'rows':>5s}  {'threshold':>10s}  "
          f"{'min':>9s}  {'p1':>9s}  {'p50':>9s}  {'note':>30s}")
    print("  " + "-" * 100)
    for scn in sorted(diag):
        d = diag[scn]
        if "threshold" not in d:
            print(f"  {scn:>20s}  {d['n_rows']:>5d}  {'(skip)':>10s}  "
                  f"{'':>9s}  {'':>9s}  {'':>9s}  {d.get('reason', ''):>30s}")
            continue
        print(f"  {scn:>20s}  {d['n_rows']:>5d}  {d['threshold']:>+10.4f}  "
              f"{d['min']:>+9.4f}  {d['p1']:>+9.4f}  {d['p50']:>+9.4f}  "
              f"{d['n_below_thr']}/{d['n_rows']} below")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="Per-scenario IF pickle (output of train.py --per-scenario)")
    p.add_argument("--manifest", required=True,
                   help="Path/dir/comma-list of nominal baseline manifests "
                        "to score against. Attack rows (__corruption_window) "
                        "are excluded automatically.")
    p.add_argument("--csv-dir", default=DEFAULT_CSV_DIR)
    p.add_argument("--target-fp-rate", type=float, default=0.01,
                   help="Fraction of nominal rows allowed to flag. Default 0.01.")
    p.add_argument("--skip-warmup-rows", type=int, default=30,
                   help="Should match what the model was trained with")
    p.add_argument("--out", default=None,
                   help="Output JSON path. Default: <model>.calibration.json.")
    args = p.parse_args()

    if not 0 < args.target_fp_rate < 0.5:
        p.error(f"--target-fp-rate must be in (0, 0.5), got {args.target_fp_rate}")

    out_path = args.out or args.model.removesuffix(".pkl") + ".calibration.json"

    t0 = time.perf_counter()
    with open(args.model, "rb") as f:
        art = pickle.load(f)
    if "models" not in art:
        raise SystemExit(f"{args.model} is not a per-scenario pickle "
                         f"(top-level keys: {list(art.keys())})")
    models = art["models"]
    print(f"loaded model: {len(models)} per-scenario IFs from {args.model}")

    manifest = args.manifest.split(",") if "," in args.manifest else args.manifest
    df, _ = load_with_labels(
        args.csv_dir, manifest,
        drop_unlabeled=True,
        skip_warmup_rows=args.skip_warmup_rows,
    )
    # Exclude attack/corruption rows so calibration sees only nominal data.
    if "__corruption_window" in df.columns:
        n_attack = int(df["__corruption_window"].sum())
        if n_attack:
            df = df[~df["__corruption_window"]].reset_index(drop=True)
            print(f"  excluded {n_attack} attack/corruption rows")

    print(f"\ncalibration corpus: {len(df)} nominal rows")
    for name, n in df["__scenario"].value_counts().items():
        print(f"  {name}: {n}")
    if len(df) == 0:
        raise SystemExit("no nominal rows to calibrate against — check the manifest list")

    t1 = time.perf_counter()
    X, _ = build_features(df, include_deltas=True, schema=art.get("schema"))
    print(f"\nfeature build: {time.perf_counter()-t1:.1f}s ({X.shape})")

    t2 = time.perf_counter()
    scenarios = df["__scenario"].to_numpy()
    scores = np.full(len(df), np.nan)
    for scn, m in models.items():
        mask = (scenarios == scn)
        if mask.any():
            scores[mask] = m.decision_function(X[mask])
    print(f"scoring: {time.perf_counter()-t2:.1f}s")

    thresholds, diag = calibrate(
        scores, scenarios, models, target_fp_rate=args.target_fp_rate,
    )
    _print_table(diag, args.target_fp_rate)

    out = {
        "model_path": os.path.abspath(args.model),
        "target_fp_rate": args.target_fp_rate,
        "thresholds": thresholds,
        "diagnostics": diag,
        "calibrated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "manifest": manifest if isinstance(manifest, list) else [manifest],
        "skip_warmup_rows": args.skip_warmup_rows,
    }
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {out_path}")
    n_skipped = sum(1 for v in thresholds.values() if v is None)
    if n_skipped:
        print(f"  WARNING: {n_skipped}/{len(thresholds)} scenarios skipped "
              f"(too few rows). Run with more manifests to cover all scenarios.")
    print(f"\ntotal: {time.perf_counter()-t0:.1f}s")


if __name__ == "__main__":
    main()
