#!/usr/bin/env python3
"""Bin an OnAIR IF side-file by uptime and report FP-rate-vs-time.

The v5 detector's deployment-grade claim rests on the steady-state per-mode FP
rate staying low as the FSW accumulates uptime. v2 (invalidated) showed severe
drift at T+4h / T+6h; this tool measures whether v5 holds.

Operational FP = `alert` column (post-warmup + hysteresis), NOT raw
`is_anomaly`. The first ~2 min after a mode change is a known mode-entry
transient (see project_v5_mode_soak_protocol) and is excluded by default.

Usage:
    python3 components/onair/training/analyze_soak_drift.py \\
        [--side-file data/onair/csv/iforest_out_<ts>_pid<N>.csv] \\
        [--mode MODE_SUNSAFE] [--bin-min 30] [--hz 4.2] [--skip-min 2] \\
        [--json out.json]

With no --side-file, uses the newest iforest_out_*.csv.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys

import numpy as np
import pandas as pd


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--side-file", default=None,
                   help="iforest_out_*.csv; default = newest in data/onair/csv")
    p.add_argument("--mode", default="MODE_SUNSAFE")
    p.add_argument("--bin-min", type=float, default=30.0)
    p.add_argument("--hz", type=float, default=4.2,
                   help="sample rate for frame_idx→minutes conversion")
    p.add_argument("--skip-min", type=float, default=2.0,
                   help="drop first N min (mode-entry transient)")
    p.add_argument("--json", default=None, help="optional JSON dump path")
    args = p.parse_args()

    path = args.side_file
    if path is None:
        files = sorted(glob.glob("data/onair/csv/iforest_out_*.csv"))
        if not files:
            sys.exit("no iforest_out_*.csv found")
        path = files[-1]

    df = pd.read_csv(path)
    df = df[df["scenario"] == args.mode].reset_index(drop=True)
    if df.empty:
        sys.exit(f"no rows for mode {args.mode} in {path}")

    skip_frames = int(args.skip_min * 60 * args.hz)
    df = df[df["frame_idx"] >= df["frame_idx"].min() + skip_frames].reset_index(drop=True)

    binsize = max(1, int(args.bin_min * 60 * args.hz))
    base = df["frame_idx"].min()
    df["bin"] = (df["frame_idx"] - base) // binsize
    g = df.groupby("bin").agg(
        frames=("frame_idx", "size"),
        raw_fp=("is_anomaly", "mean"),
        alert_fp=("alert", "mean"),
        score_p01=("score", lambda s: s.quantile(0.01)),
        score_mean=("score", "mean"),
    )
    rows = []
    for b, r in g.iterrows():
        t0 = int(b * args.bin_min)
        rows.append({
            "window": f"T+{t0}-{t0 + int(args.bin_min)}min",
            "frames": int(r["frames"]),
            "raw_fp": round(float(r["raw_fp"]), 5),
            "alert_fp": round(float(r["alert_fp"]), 5),
            "score_p01": round(float(r["score_p01"]), 5),
            "score_mean": round(float(r["score_mean"]), 5),
        })

    total_min = len(df) / args.hz / 60
    overall = {
        "side_file": path,
        "mode": args.mode,
        "skip_min": args.skip_min,
        "total_frames": int(len(df)),
        "approx_uptime_min": round(total_min, 1),
        "overall_alert_fp": round(float(df["alert"].mean()), 5),
        "overall_raw_fp": round(float(df["is_anomaly"].mean()), 5),
        "bins": rows,
    }

    # Simple drift verdict: alert FP in the last third vs first third.
    if len(rows) >= 3:
        k = max(1, len(rows) // 3)
        first = float(np.mean([r["alert_fp"] for r in rows[:k]]))
        last = float(np.mean([r["alert_fp"] for r in rows[-k:]]))
        overall["drift_first_third_alert_fp"] = round(first, 5)
        overall["drift_last_third_alert_fp"] = round(last, 5)
        overall["drift_delta"] = round(last - first, 5)

    print(f"side-file: {path}")
    print(f"mode={args.mode}  uptime≈{total_min:.0f} min  "
          f"frames={len(df)}  (first {args.skip_min:.0f} min dropped)\n")
    hdr = f"{'window':>16} {'frames':>7} {'raw_fp':>8} {'alert_fp':>9} {'score_p01':>10} {'score_mean':>11}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['window']:>16} {r['frames']:>7} {r['raw_fp']:>8.4f} "
              f"{r['alert_fp']:>9.4f} {r['score_p01']:>10.4f} {r['score_mean']:>11.4f}")
    print(f"\noverall alert_fp={overall['overall_alert_fp']:.4f}  "
          f"raw_fp={overall['overall_raw_fp']:.4f}  (target ≤ 0.01)")
    if "drift_delta" in overall:
        verdict = ("NO DRIFT" if overall["drift_delta"] <= 0.005
                   else "POSSIBLE DRIFT")
        print(f"drift: first-third alert_fp={overall['drift_first_third_alert_fp']:.4f} "
              f"→ last-third={overall['drift_last_third_alert_fp']:.4f} "
              f"(Δ={overall['drift_delta']:+.4f}) → {verdict}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(overall, f, indent=2)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
