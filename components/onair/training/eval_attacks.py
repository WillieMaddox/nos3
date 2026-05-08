"""Score per-scenario IsolationForest models against attack-labeled CSVs.

Phase-2 readout. Loads the v2 per-scenario IF artifact + every manifest in
`data/onair/scenarios/`, builds features over all labeled rows, then scores
each row through `models[__scenario]`. Splits results by `__attack_window`
to compute:

  1. Per-scenario nominal flag rate (FP, since these rows are all nominal).
  2. Per-attack flag rate (TP at threshold 0).
  3. A small threshold sweep so you can read TP@FP=1% / FP@TP=95% directly.

If no attack rows exist (e.g., only baseline manifests loaded), the attack
diagnostic is skipped and the script reports an FP-only sanity check —
useful for confirming the loader extension didn't shift the v2 baseline.

Usage:
    python3 components/onair/training/eval_attacks.py
    # Restrict to one manifest (e.g. just an attack run):
    python3 components/onair/training/eval_attacks.py \\
        --manifest data/onair/scenarios/manifest_<session>.json
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import build_features  # noqa: E402
from loader import load_with_labels  # noqa: E402

DEFAULT_MODEL = "data/onair/models/iforest_per_scenario_v2_warmup30.pkl"
DEFAULT_CSV_DIR = "fsw/build/exe/cpu1/data/onair/csv"
DEFAULT_MANIFESTS = "data/onair/scenarios"


def _row_table(label: str, headers: list[str], rows: list[list]) -> None:
    """Tiny right-aligned table printer."""
    widths = [max(len(h), *(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    line = "  ".join(h.rjust(w) for h, w in zip(headers, widths))
    print(label)
    print(line)
    print("-" * len(line))
    for r in rows:
        print("  ".join(str(c).rjust(w) for c, w in zip(r, widths)))


def _score_distribution(scores: np.ndarray) -> dict:
    return {
        "min": float(scores.min()),
        "p1": float(np.percentile(scores, 1)),
        "p5": float(np.percentile(scores, 5)),
        "p25": float(np.percentile(scores, 25)),
        "p50": float(np.percentile(scores, 50)),
        "mean": float(scores.mean()),
        "max": float(scores.max()),
    }


def _fmt(x: float) -> str:
    return f"{x:+.4f}"


def _pct(num: int, den: int) -> str:
    if den == 0:
        return "0.0%"
    return f"{100.0 * num / den:.1f}%"


def score_per_scenario(
    df: pd.DataFrame, X: np.ndarray, models: dict[str, object]
) -> np.ndarray:
    """Route each row through models[__scenario], return a flat scores array.

    Rows whose scenario has no matching model (shouldn't happen in practice)
    get NaN so they're visible downstream.
    """
    scenarios = df["__scenario"].to_numpy()
    out = np.full(len(df), np.nan, dtype=np.float64)
    for scn, model in models.items():
        mask = (scenarios == scn)
        n = int(mask.sum())
        if n == 0:
            continue
        out[mask] = model.decision_function(X[mask])
    n_unmatched = int(np.isnan(out).sum())
    if n_unmatched:
        present = sorted(set(scenarios) - set(models))
        print(f"  WARNING: {n_unmatched} rows had no matching scenario model "
              f"(scenarios not in pickle: {present})")
    return out


def report_per_scenario_fp(df: pd.DataFrame, scores: np.ndarray) -> None:
    """Per-scenario nominal flag rate (rows with __attack_window=False)."""
    nominal = ~df["__attack_window"].to_numpy()
    if not nominal.any():
        print("  (no nominal rows in this dataset — skipping per-scenario FP table)")
        return
    headers = ["scenario", "rows", "%flag@0", "min", "p1", "p5", "p25", "p50"]
    rows = []
    scn_arr = df["__scenario"].to_numpy()
    for scn in sorted(set(scn_arr)):
        mask = nominal & (scn_arr == scn)
        s = scores[mask]
        if len(s) == 0:
            continue
        n_flag = int((s < 0).sum())
        d = _score_distribution(s)
        rows.append([
            scn, len(s), _pct(n_flag, len(s)),
            _fmt(d["min"]), _fmt(d["p1"]), _fmt(d["p5"]),
            _fmt(d["p25"]), _fmt(d["p50"]),
        ])
    _row_table("per-scenario nominal score distribution (FP):",
               headers, rows)


def report_per_attack_tp(df: pd.DataFrame, scores: np.ndarray) -> bool:
    """Per-attack flag rate (rows with __attack_window=True). Returns True
    if any attack rows existed."""
    attack_mask = df["__attack_window"].to_numpy()
    if not attack_mask.any():
        return False
    headers = ["attack_id", "scenario", "rows", "%flag@0",
               "min", "p1", "p5", "p25", "p50"]
    rows = []
    aid_arr = df["__attack_id"].to_numpy()
    scn_arr = df["__scenario"].to_numpy()
    for aid in sorted(set(aid_arr[attack_mask])):
        for scn in sorted(set(scn_arr[attack_mask & (aid_arr == aid)])):
            mask = attack_mask & (aid_arr == aid) & (scn_arr == scn)
            s = scores[mask]
            n_flag = int((s < 0).sum())
            d = _score_distribution(s)
            rows.append([
                aid, scn, len(s), _pct(n_flag, len(s)),
                _fmt(d["min"]), _fmt(d["p1"]), _fmt(d["p5"]),
                _fmt(d["p25"]), _fmt(d["p50"]),
            ])
    _row_table("per-attack score distribution (TP):", headers, rows)
    return True


def report_threshold_sweep(
    df: pd.DataFrame, scores: np.ndarray,
    thresholds: list[float] | None = None,
) -> None:
    """For each threshold, report aggregate TP rate (attack rows flagged) and
    FP rate (nominal rows flagged)."""
    if thresholds is None:
        thresholds = [-0.10, -0.05, -0.03, -0.02, -0.01, 0.0]
    attack = df["__attack_window"].to_numpy()
    nominal = ~attack
    n_attack = int(attack.sum())
    n_nominal = int(nominal.sum())
    headers = ["threshold", "TP_count", "TP_total", "TP%",
               "FP_count", "FP_total", "FP%"]
    rows = []
    for t in thresholds:
        flagged = scores < t
        tp = int((flagged & attack).sum()) if n_attack else 0
        fp = int((flagged & nominal).sum())
        rows.append([
            f"{t:+.3f}", tp, n_attack, _pct(tp, n_attack),
            fp, n_nominal, _pct(fp, n_nominal),
        ])
    _row_table("threshold sweep (TP=attack_window, FP=nominal):",
               headers, rows)

    if n_attack and n_nominal:
        # TP @ FP=1% — find the threshold where FP rate is closest to 1%
        order = np.argsort(scores)  # ascending → most-anomalous first
        # Walk thresholds derived from sorted nominal scores
        nominal_scores_sorted = np.sort(scores[nominal])
        target_fp_count = max(1, int(round(0.01 * n_nominal)))
        if target_fp_count <= len(nominal_scores_sorted):
            t_at_1pct_fp = float(nominal_scores_sorted[target_fp_count - 1])
            tp_at_1pct = int((scores[attack] < t_at_1pct_fp).sum())
            print(f"\n  TP @ FP=1%: {tp_at_1pct}/{n_attack} "
                  f"({100.0*tp_at_1pct/n_attack:.1f}%) at threshold {t_at_1pct_fp:+.4f}")
        # FP @ TP=95% — threshold where 95% of attack rows flag
        attack_scores_sorted = np.sort(scores[attack])  # most-anomalous first (negative)
        target_tp_count = int(round(0.95 * n_attack))
        if 1 <= target_tp_count <= len(attack_scores_sorted):
            t_at_95pct_tp = float(attack_scores_sorted[target_tp_count - 1])
            fp_at_95pct = int((scores[nominal] < t_at_95pct_tp).sum())
            print(f"  FP @ TP=95%: {fp_at_95pct}/{n_nominal} "
                  f"({100.0*fp_at_95pct/n_nominal:.1f}%) at threshold {t_at_95pct_tp:+.4f}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="Pickle written by train.py --per-scenario")
    p.add_argument("--csv-dir", default=DEFAULT_CSV_DIR)
    p.add_argument("--manifest", default=DEFAULT_MANIFESTS,
                   help="Manifest path/dir/comma-list (same semantics as the trainer)")
    p.add_argument("--skip-warmup-rows", type=int, default=30,
                   help="Should match what the model was trained with")
    args = p.parse_args()

    t0 = time.perf_counter()
    with open(args.model, "rb") as f:
        art = pickle.load(f)
    if "models" not in art:
        raise SystemExit(f"{args.model} doesn't look per-scenario "
                         f"(top-level keys: {list(art.keys())})")
    models = art["models"]
    print(f"loaded model: {len(models)} per-scenario IFs from {args.model}")
    print(f"  config: {art.get('config', {})}")

    manifest = args.manifest
    if manifest and "," in manifest:
        manifest = manifest.split(",")

    df, _ = load_with_labels(
        args.csv_dir, manifest,
        drop_unlabeled=True,
        skip_warmup_rows=args.skip_warmup_rows,
    )
    print(f"\nloaded dataset: {df.shape[0]} rows")
    print("  scenario distribution:")
    for name, n in df["__scenario"].value_counts().items():
        print(f"    {name}: {n}")
    n_attack = int(df["__attack_window"].sum())
    if n_attack:
        print(f"  attack rows: {n_attack}")
        for aid in sorted(df.loc[df["__attack_window"], "__attack_id"].unique()):
            n = int((df["__attack_id"] == aid).sum())
            print(f"    {aid}: {n}")
    else:
        print("  attack rows: 0  (FP-only baseline — no attack manifests in this load)")

    t1 = time.perf_counter()
    X, _ = build_features(df, include_deltas=True)
    print(f"\nfeature build: {time.perf_counter()-t1:.1f}s ({X.shape})")

    t2 = time.perf_counter()
    scores = score_per_scenario(df, X, models)
    print(f"scoring: {time.perf_counter()-t2:.1f}s")

    print()
    report_per_scenario_fp(df, scores)
    print()
    had_attacks = report_per_attack_tp(df, scores)
    print()
    if had_attacks:
        report_threshold_sweep(df, scores)
    else:
        print("(no attack rows — skipping threshold sweep)")
    print(f"\ntotal: {time.perf_counter()-t0:.1f}s")


if __name__ == "__main__":
    main()
