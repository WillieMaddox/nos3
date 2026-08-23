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
        [--mode MODE_SUNSAFE] [--bin-min 30] [--skip-min 2] \\
        [--hz 5.5] [--json out.json]

With no --side-file, uses the newest iforest_out_*.csv.

Sample rate is DERIVED from the data, not assumed (AINOS3-92): the side-file
carries no clock, so the rate comes from `CFE_TIME.SecondsMET` in the paired
`csv_out_*` log of the same session. The old hardcoded 4.2 Hz was ~24% low
against a measured ~5.5, which mislabelled every uptime bin. `--hz` remains as
an override and warns when it disagrees with the derived rate by >10%.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

# Used only when the rate cannot be derived AND no --hz is given. Measured, not
# assumed: 4.78-5.55 Hz across four 2026-08-15 sessions (AINOS3-92). Deriving is
# always preferred; this exists so the tool degrades loudly rather than silently.
FALLBACK_HZ = 5.5

# A derived rate outside this band means the pairing or the clock is wrong, not
# that the pipeline sped up. Reject rather than propagate.
HZ_SANE = (1.0, 20.0)

# Minimum MET span before a derived rate is trusted; short files give a rate
# dominated by startup jitter.
MIN_SPAN_S = 60.0

_SIDE_RE = re.compile(r"iforest_out_(?P<ts>.+?)_pid(?P<pid>\d+)\.csv$")
_MAIN_RE = re.compile(r"csv_out_(?P<ts>.+?)_pid(?P<pid>\d+)\.csv$")
_TS_FMT = "%Y-%m-%dT%H-%M-%S-%f"


def _parse_ts(ts: str):
    try:
        return datetime.datetime.strptime(ts, _TS_FMT)
    except ValueError:
        return None


def find_paired_main_csv(side_path: str, max_skew_s: float = 30.0):
    """Locate the `csv_out_*` log written by the same OnAIR session as `side_path`.

    OnAIR opens every side-file and the main CSV within the same second of the
    same process, so the pair is (same pid, closest timestamp). Returns None when
    no candidate lands inside `max_skew_s`.
    """
    m = _SIDE_RE.search(os.path.basename(side_path))
    if not m:
        return None
    want = _parse_ts(m.group("ts"))
    if want is None:
        return None
    pid = m.group("pid")
    best, best_skew = None, None
    for cand in glob.glob(os.path.join(os.path.dirname(side_path) or ".",
                                       f"csv_out_*_pid{pid}.csv")):
        cm = _MAIN_RE.search(os.path.basename(cand))
        if not cm:
            continue
        got = _parse_ts(cm.group("ts"))
        if got is None:
            continue
        skew = abs((got - want).total_seconds())
        if best_skew is None or skew < best_skew:
            best, best_skew = cand, skew
    if best is None or best_skew > max_skew_s:
        return None
    return best


def derive_hz(side_path: str):
    """Derive the frame rate (Hz) from the session's mission-elapsed-time clock.

    The side-file carries no clock at all — only `frame_idx` — so the rate comes
    from `CFE_TIME.SecondsMET` in the paired main CSV, which is frame-aligned with
    it. MET is only ~0.25 Hz-granular in the HK packet, so per-sample diffs are
    useless; the endpoints over a long span are not. MET is also non-monotonic
    across the OnAIR double buffer, hence max-min rather than last-first.

    Returns `(hz, provenance)`; `hz` is None when it cannot be derived.
    """
    main = find_paired_main_csv(side_path)
    if main is None:
        return None, "no paired csv_out_* found for this session"
    try:
        cols = pd.read_csv(main, nrows=0).columns
    except Exception as exc:                      # unreadable / truncated
        return None, f"could not read {os.path.basename(main)}: {exc}"
    if "CFE_TIME.SecondsMET" not in cols:
        return None, f"{os.path.basename(main)} has no CFE_TIME.SecondsMET column"

    usecols = ["CFE_TIME.SecondsMET"]
    if "CFE_TIME.SubsecsMET" in cols:
        usecols.append("CFE_TIME.SubsecsMET")
    d = pd.read_csv(main, usecols=usecols, low_memory=False)
    met = pd.to_numeric(d["CFE_TIME.SecondsMET"], errors="coerce")
    if "CFE_TIME.SubsecsMET" in usecols:
        met = met + pd.to_numeric(d["CFE_TIME.SubsecsMET"], errors="coerce") / 2 ** 32
    met = met.dropna()
    if len(met) < 2:
        return None, f"{os.path.basename(main)} has <2 usable MET samples"

    span = float(met.max() - met.min())
    if span < MIN_SPAN_S:
        return None, (f"MET span {span:.1f}s < {MIN_SPAN_S:.0f}s "
                      f"in {os.path.basename(main)} — too short to trust")
    hz = (len(met) - 1) / span
    if not (HZ_SANE[0] <= hz <= HZ_SANE[1]):
        return None, (f"derived {hz:.3f} Hz from {os.path.basename(main)} is "
                      f"outside the sane band {HZ_SANE} — ignoring")
    return hz, (f"derived from CFE_TIME.SecondsMET in "
                f"{os.path.basename(main)} ({len(met)} frames / {span:.0f}s)")


def resolve_hz(side_path: str, override):
    """Combine the derived rate with any `--hz` override. Returns (hz, provenance).

    The override always wins — but it is checked against the data, and a >10%
    disagreement is reported rather than silently accepted. That check is the
    point of the ticket: the tool shipped for four sprints with a hardcoded 4.2
    against a true ~5.5 — a rate 24% low, which stretches the uptime axis it
    derives by 32% (an 86.9 h soak reported as 6,911 min against a true 5,229).
    """
    derived, why = derive_hz(side_path)
    if override is None:
        if derived is None:
            print(f"WARNING: sample rate not derivable ({why}); falling back to "
                  f"{FALLBACK_HZ} Hz. Uptime bins may be mislabelled — pass --hz "
                  f"if you know the true rate.", file=sys.stderr)
            return FALLBACK_HZ, f"fallback {FALLBACK_HZ} Hz ({why})"
        return derived, why
    if derived is not None and abs(override - derived) / derived > 0.10:
        print(f"WARNING: --hz {override:g} disagrees with the derived rate "
              f"{derived:.3f} Hz by {abs(override - derived) / derived:.0%} "
              f"({why}). Using the override; every uptime bin below is scaled by "
              f"it.", file=sys.stderr)
    return override, (f"--hz override {override:g}"
                      + (f" (derived was {derived:.3f}; {why})" if derived else
                         f" (not derivable: {why})"))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--side-file", default=None,
                   help="iforest_out_*.csv; default = newest in data/onair/csv")
    p.add_argument("--mode", default="MODE_SUNSAFE")
    p.add_argument("--bin-min", type=float, default=30.0)
    p.add_argument("--hz", type=float, default=None,
                   help="override the derived sample rate (Hz) used for the "
                        "frame_idx→minutes conversion; warns on >10%% disagreement")
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

    hz, hz_provenance = resolve_hz(path, args.hz)

    skip_frames = int(args.skip_min * 60 * hz)
    df = df[df["frame_idx"] >= df["frame_idx"].min() + skip_frames].reset_index(drop=True)

    binsize = max(1, int(args.bin_min * 60 * hz))
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

    total_min = len(df) / hz / 60
    overall = {
        "side_file": path,
        "mode": args.mode,
        "skip_min": args.skip_min,
        "hz": round(hz, 4),
        "hz_provenance": hz_provenance,
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
    print(f"rate: {hz:.3f} Hz — {hz_provenance}")
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
