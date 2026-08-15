#!/usr/bin/env python3
"""Re-derive the per-mode IF alarm thresholds on HELD-OUT nominal flight.

Why
---
AINOS3-80 **F1**: the deployed thresholds in
`iforest_per_mode_v5_invariant_bolstered.calibration.json` were picked as the
1 % quantile of the model's OWN TRAINING SCORES — the calibration row counts are
identical to `n_train_rows_per_scenario` in all four modes. A threshold fitted
on the data the model memorised is not a prediction of live false-alarm rate.

AINOS3-81 measured the consequence: against a 1 % target, live nominal delivers
0.0× (BDOT), **7.5×** (INERTIAL), 0.0× (PASSIVE), 0.9× (SUNSAFE). Only SUNSAFE —
with by far the most training rows — lands where the calibration promised.
INERTIAL's operational FP is 0.54 % against a documented 0.00 %.

Method — and the trap this script exists to avoid
-------------------------------------------------
The 7 h AINOS3-81 soak is genuinely independent of training, so it is a
legitimate calibration set. But calibrating on the soak and then reporting the
false-alarm rate on that same soak would repeat the exact error being fixed,
one level down. So the soak is SPLIT, chronologically, per mode:

    part A (first `--calib-frac`)  -> pick the threshold
    part B (the remainder)         -> measure the false-alarm rate

Part B is never used to choose anything, so its FP is an honest out-of-sample
estimate. The split is chronological rather than random because adjacent frames
are highly autocorrelated and the feature vector contains deltas
(`row[i] - row[i-1]`); a random split would leak neighbours across the boundary.

This yields a three-way separation overall:

    train    = the model's original (unrecorded, see AINOS3-80 F2) corpus
    calibrate= soak part A          [held out of training]
    test     = soak part B          [held out of training AND of calibration]

Output
------
Writes a NEW calibration JSON to `--out` (a staging path by default). It does
NOT touch the deployed file — flipping thresholds changes live detector
behaviour and goes through review + the one-line-rollback discipline used for
the AINOS3-37 cutover.

Usage
-----
    ~/.virtualenvs/nos3/bin/python \\
        components/onair/training/recalibrate_heldout.py \\
        --csv-dir data/onair/csv \\
        --csv-glob 'csv_out_2026-08-11T06-05-26*.csv' \\
        --manifest-glob 'data/onair/scenarios/manifest_soak_*2026-08-11*.json' \\
        --out data/onair/models/recalibrated_heldout.calibration.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pickle
import sys

import numpy as np

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from features import build_features      # noqa: E402
from loader import load                  # noqa: E402

DEFAULT_MODEL = "data/onair/models/iforest_per_mode_v5_invariant_bolstered.pkl"
MIN_ROWS = 100


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--csv-dir", default="data/onair/csv")
    p.add_argument("--csv-glob", required=True,
                   help="Glob (within --csv-dir) selecting the nominal soak CSV(s).")
    p.add_argument("--target-fp-rate", type=float, default=0.01)
    p.add_argument("--calib-frac", type=float, default=0.6,
                   help="Chronological fraction of each mode used to PICK the "
                        "threshold; the remainder measures it. Default 0.6.")
    p.add_argument("--skip-warmup-rows", type=int, default=30)
    p.add_argument("--mode-entry-skip", type=int, default=700,
                   help="Frames to drop after each mode entry (~2 min at 5.6 Hz). "
                        "The mode-entry transient is a known, separately-handled "
                        "effect; including it would bias the threshold loose.")
    p.add_argument("--out", default="data/onair/models/recalibrated_heldout.calibration.json")
    p.add_argument("--target-sweep", default="",
                   help="Comma-separated target FP rates to sweep (e.g. "
                        "'0.0001,0.0005,0.001,0.005,0.01'). For each, report the "
                        "held-out FP per mode. Answers 'what target actually "
                        "delivers the operational behaviour we want', rather than "
                        "assuming the nominal 1%% design figure is the right one.")
    args = p.parse_args()

    with open(args.model, "rb") as f:
        bundle = pickle.load(f)
    models = bundle["models"]
    schema = bundle["schema"]

    paths = sorted(glob.glob(os.path.join(args.csv_dir, args.csv_glob)))
    if not paths:
        sys.exit(f"no CSVs matched {args.csv_glob} under {args.csv_dir}")
    print(f"soak CSVs: {[os.path.basename(p) for p in paths]}")

    # Load only the matched files by pointing the loader at a temp view.
    import tempfile
    import shutil
    tmp = tempfile.mkdtemp(prefix="recal_")
    try:
        for src in paths:
            os.symlink(os.path.abspath(src), os.path.join(tmp, os.path.basename(src)))
        df, stats = load(csv_dir=tmp, skip_warmup_rows=args.skip_warmup_rows)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"loaded {len(df)} rows, {df.shape[1]} columns")

    mode_col = bundle.get("label_column", "__adcs_mode")
    if mode_col not in df.columns:
        # The loader derives __adcs_mode from the raw mode field; fall back to
        # deriving it here so this script does not depend on loader internals.
        code_to_mode = {0: "MODE_PASSIVE", 1: "MODE_BDOT",
                        2: "MODE_SUNSAFE", 3: "MODE_INERTIAL"}
        import pandas as pd
        codes = pd.to_numeric(df["ADCS_GNC.Mode"], errors="coerce")
        df[mode_col] = codes.map(code_to_mode).fillna("MODE_UNKNOWN")
    modes = df[mode_col].to_numpy()

    drop = [c for c in df.columns if c.startswith("__")]
    X, _ = build_features(df.drop(columns=drop), include_deltas=True, schema=schema)
    print(f"feature matrix: {X.shape}")

    # Deployed calibration sits next to the model as <stem>.calibration.json
    # (the .pkl suffix is REPLACED, not appended).
    old_path = os.path.splitext(args.model)[0] + ".calibration.json"
    if not os.path.exists(old_path):
        print(f"  WARNING: no deployed calibration at {old_path} — "
              f"old-vs-new comparison unavailable")
    old = json.load(open(old_path)) if os.path.exists(old_path) else {"thresholds": {}}

    out = {
        "model_path": os.path.abspath(args.model),
        "target_fp_rate": args.target_fp_rate,
        "provenance": "HELD-OUT: thresholds picked on a chronological part-A "
                      "split of independent nominal soak data (never used in "
                      "training); the reported false-alarm rate is measured on "
                      "part B, which was used for neither training nor "
                      "threshold selection. Supersedes the in-sample "
                      "calibration flagged by AINOS3-80 F1.",
        "source_csvs": [os.path.basename(p) for p in paths],
        "calib_frac": args.calib_frac,
        "mode_entry_skip_frames": args.mode_entry_skip,
        "thresholds": {},
        "diagnostics": {},
    }

    print(f"\n{'mode':16s}{'nA':>7}{'nB':>7}{'old_thr':>12}{'new_thr':>12}"
          f"{'oldFP_B':>9}{'newFP_B':>9}")
    for scn in sorted(models):
        mask = (modes == scn)
        idx = np.flatnonzero(mask)
        if len(idx) < MIN_ROWS:
            out["thresholds"][scn] = None
            out["diagnostics"][scn] = {"n_rows": int(len(idx)),
                                       "reason": f"too few rows (<{MIN_ROWS})"}
            print(f"{scn:16s}{len(idx):>7}{'':>7}{'':>12}{'(skip)':>12}")
            continue
        # Drop the mode-entry transient: the first N frames of this mode's run.
        idx = idx[args.mode_entry_skip:] if len(idx) > args.mode_entry_skip * 2 else idx
        scores = models[scn].decision_function(X[idx])

        cut = int(len(scores) * args.calib_frac)
        a, b = scores[:cut], scores[cut:]
        if len(a) < MIN_ROWS or len(b) < MIN_ROWS:
            out["thresholds"][scn] = None
            out["diagnostics"][scn] = {"n_rows": int(len(scores)),
                                       "reason": "split leaves too few rows"}
            print(f"{scn:16s}{len(a):>7}{len(b):>7}{'':>12}{'(skip)':>12}")
            continue

        s = np.sort(a)
        k = max(1, min(len(s), int(round(args.target_fp_rate * len(s)))))
        new_thr = float(s[k - 1])
        old_thr = old.get("thresholds", {}).get(scn)

        new_fp_b = float((b < new_thr).mean())
        old_fp_b = float((b < old_thr).mean()) if old_thr is not None else float("nan")

        out["thresholds"][scn] = new_thr
        out["diagnostics"][scn] = {
            "n_calib_rows": int(len(a)),
            "n_test_rows": int(len(b)),
            "threshold": new_thr,
            "old_threshold": old_thr,
            "heldout_fp_new": round(new_fp_b, 5),
            "heldout_fp_old": round(old_fp_b, 5) if old_thr is not None else None,
            "score_min": float(scores.min()),
            "score_p01": float(np.percentile(scores, 1)),
            "score_median": float(np.median(scores)),
            # Retained only for the in-process target sweep; stripped before write.
            "_scores_a": a.tolist(),
            "_scores_b": b.tolist(),
        }
        print(f"{scn:16s}{len(a):>7}{len(b):>7}"
              f"{(old_thr if old_thr is not None else float('nan')):>12.2e}"
              f"{new_thr:>12.2e}{old_fp_b:>9.4f}{new_fp_b:>9.4f}")

    # ── target sweep ────────────────────────────────────────────────────
    # The deployed thresholds all sit near 0 and were never chosen against
    # live data, so the four modes are not comparable to each other. Sweeping
    # the target shows what a *consistent* live-calibrated target costs in each
    # mode — and whether 1 % (the stated design figure) is even the right one,
    # given the system currently BEATS it in three modes.
    if args.target_sweep:
        targets = [float(t) for t in args.target_sweep.split(",") if t.strip()]
        print(f"\n=== target sweep — held-out (part B) FP per mode ===")
        print(f"{'target':>10}" + "".join(f"{s.replace('MODE_',''):>12}" for s in sorted(models)))
        sweep = {}
        for tgt in targets:
            row = {}
            for scn in sorted(models):
                d = out["diagnostics"].get(scn, {})
                sc = d.get("_scores_a"), d.get("_scores_b")
                if sc[0] is None:
                    row[scn] = None
                    continue
                a, b = np.asarray(sc[0]), np.asarray(sc[1])
                s = np.sort(a)
                k = max(1, min(len(s), int(round(tgt * len(s)))))
                thr = float(s[k - 1])
                row[scn] = {"threshold": thr, "heldout_fp": round(float((b < thr).mean()), 5)}
            sweep[str(tgt)] = row
            print(f"{tgt:>10.4f}" + "".join(
                f"{(row[s]['heldout_fp'] if row[s] else float('nan')):>12.4f}"
                for s in sorted(models)))
        out["target_sweep"] = sweep

    # Drop the bulky score arrays before serialising.
    for d in out["diagnostics"].values():
        d.pop("_scores_a", None)
        d.pop("_scores_b", None)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {args.out}")
    print("NOT deployed — review, then point CalibrationPath at it (one-line "
          "ini change, one-line rollback).")


if __name__ == "__main__":
    main()
