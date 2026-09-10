#!/usr/bin/env python3
"""Measure the deployed IF's false-alarm rate on CONTROLLED INERTIAL flight.

WHY A SEPARATE TOOL (AINOS3-86 AC3)
-----------------------------------
`analyze_soak_drift.py` bins an IF side-file by uptime and filters on the
`scenario` column — i.e. on the ADCS mode LABEL. For INERTIAL that filter is not
sufficient, and trusting it is exactly how 33.6 % came to be published as
"INERTIAL nominal FP" when it actually described uncontrolled tumble:

    ADCS_GNC.Mode == 3          the vehicle SAYS it is in INERTIAL
    ADCS_GNC.qValid == 0        but the star tracker is Earth-occluded, so
                                AC_inertial() is skipped and nothing controls
                                the attitude — free drift wearing the label

So a frame only counts as nominal controlled INERTIAL if the control loop was
actually closed on it. This tool gates on `qValid`, not on the mode label.

⚠ Frames are joined by INDEX. `iforest_out_<ts>_pid<N>.csv` and
`csv_out_<ts>_pid<N>.csv` from the same session are written per frame by the same
plugin pass, so side-file `frame_idx` is the main-log row index. The tool
verifies the pairing (same timestamp+pid, same length) and refuses otherwise
rather than silently misaligning.

WHAT IS REPORTED
----------------
  operational FP = mean of the `alert` column — post-warmup, post-hysteresis.
                   This is the number an operator sees and the one the 1 %
                   design target refers to (project_v5_mode_soak_protocol).
  raw FP         = mean of `is_anomaly` — pre-hysteresis, always higher.

Both are reported because quoting only one has caused confusion before
(AINOS3-81: 0.54 % operational vs 7.5 % raw for the same window).

USAGE
    python3 analyze_inertial_fp.py [--start-frame N] [--skip-min 2] [--json out.json]
"""
from __future__ import annotations

import argparse
import ast
import csv
import datetime
import glob
import json
import math
import os
import re
import sys

SENTINEL = "[0]"
_SIDE_RE = re.compile(r"iforest_out_(?P<key>.+_pid\d+)\.csv$")

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
CSV_DIR = os.path.join(ROOT, "data", "onair", "csv")


def newest(pattern):
    files = glob.glob(os.path.join(CSV_DIR, pattern))
    return max(files, key=os.path.getmtime) if files else None


_TS_RE = re.compile(r"_(?P<ts>\d{4}-\d{2}-\d{2}T[\d-]+)_pid(?P<pid>\d+)\.csv$")
_TS_FMT = "%Y-%m-%dT%H-%M-%S-%f"


def _parse_ts(path):
    m = _TS_RE.search(os.path.basename(path))
    if not m:
        return None, None
    try:
        return datetime.datetime.strptime(m.group("ts"), _TS_FMT), m.group("pid")
    except ValueError:
        return None, m.group("pid")


def pair_main_log(side_path):
    """Find the csv_out_* written by the same OnAIR process.

    ⚠ Match on the SESSION TIMESTAMP, not on mtime. The two files share a
    timestamp and pid but are opened a fraction of a second apart. An earlier
    version took the newest pid-matching file, which silently paired a 2026-08-15
    side-file with a 2026-09-10 main log whenever both ran as pid 11 — pids
    recycle across launches, so "newest" is not "same session". The row-count
    guard below caught it, but only by luck of the lengths differing.
    """
    ts, pid = _parse_ts(side_path)
    if pid is None:
        raise SystemExit(f"unrecognised side-file name: {side_path}")
    cands = [p for p in glob.glob(os.path.join(CSV_DIR, "csv_out_*.csv"))
             if p.endswith(f"_pid{pid}.csv")]
    if not cands:
        raise SystemExit(f"no csv_out_*_pid{pid}.csv paired with {os.path.basename(side_path)}")
    if ts is not None:
        dated = [(abs((_parse_ts(p)[0] - ts).total_seconds()), p)
                 for p in cands if _parse_ts(p)[0] is not None]
        if dated:
            delta, best = min(dated)
            if delta > 120:
                raise SystemExit(
                    f"nearest csv_out for {os.path.basename(side_path)} is "
                    f"{delta:.0f}s away ({os.path.basename(best)}) — no same-session pair")
            return best
    return max(cands, key=os.path.getmtime)


def vec_mag_deg(text):
    try:
        v = ast.literal_eval(text)
        return math.sqrt(sum(float(c) ** 2 for c in v)) * 180.0 / math.pi
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--side-file", default=None)
    ap.add_argument("--start-frame", type=int, default=0,
                    help="first frame of the measurement window (exclude the "
                         "pre-capture history of the session)")
    ap.add_argument("--end-frame", type=int, default=None,
                    help="last frame of the window. ⚠ For a session recorded by "
                         "run_attack.py this MUST be set to the end of the nominal "
                         "PRE-window: frames inside the attack window are true "
                         "positives, and counting them as false alarms inflates FP.")
    ap.add_argument("--skip-min", type=float, default=2.0,
                    help="drop this much after the window start as mode-entry transient")
    ap.add_argument("--hz", type=float, default=None,
                    help="override the sample rate. Default: DERIVED from "
                         "CFE_TIME.SecondsMET in the paired main log (AINOS3-92) — "
                         "the side-file has no clock, and a hardcoded rate "
                         "mis-states every duration it is used for.")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    side = args.side_file or newest("iforest_out_*.csv")
    if not side:
        raise SystemExit("no iforest_out_*.csv found")
    main_log = pair_main_log(side)

    with open(side, newline="") as fh:
        srows = list(csv.DictReader(fh))
    with open(main_log, newline="") as fh:
        mrows = list(csv.DictReader(fh))

    n = min(len(srows), len(mrows))
    if abs(len(srows) - len(mrows)) > 50:
        raise SystemExit(f"side-file and main log differ by "
                         f"{abs(len(srows)-len(mrows))} rows — refusing to join by index")

    # ⚠ AINOS3-92: derive the rate, never assume it. MET is only ~0.25 Hz-granular
    # and NON-monotonic (the OnAIR double buffer), so use max-min across the span,
    # not consecutive diffs and not last-first.
    hz = args.hz
    if hz is None:
        mets = []
        for r in mrows:
            v = r.get("CFE_TIME.SecondsMET", SENTINEL)
            if v not in (SENTINEL, ""):
                try:
                    mets.append(float(v))
                except ValueError:
                    pass
        span = (max(mets) - min(mets)) if len(mets) > 1 else 0.0
        if span >= 60.0:
            hz = len(mrows) / span
            if not (1.0 <= hz <= 20.0):
                print(f"⚠ derived rate {hz:.2f} Hz is out of the sane band; "
                      f"falling back to 5.5", file=sys.stderr)
                hz = 5.5
        else:
            print("⚠ MET span < 60s — cannot derive a rate; falling back to 5.5",
                  file=sys.stderr)
            hz = 5.5
    args.hz = hz

    skip = int(args.skip_min * 60 * args.hz)
    lo = max(args.start_frame + skip, 0)
    if args.end_frame is not None:
        n = min(n, args.end_frame + 1)

    # Two arms, same session / stack / model / window — differing ONLY in whether
    # the control loop was closed. This is the like-for-like control that
    # separates "controlled INERTIAL is clean" from "we evaluated an easier slice".
    arms = {"controlled": dict(n=0, alerts=0, raw=0, rates=[]),
            "uncontrolled": dict(n=0, alerts=0, raw=0, rates=[])}
    labelled_inertial = 0
    for i in range(lo, n):
        s, m = srows[i], mrows[i]
        if s.get("scenario") != "MODE_INERTIAL":
            continue
        labelled_inertial += 1
        qv = m.get("ADCS_GNC.qValid", SENTINEL)
        if qv == SENTINEL:
            continue
        arm = arms["controlled"] if qv == "1" else arms["uncontrolled"]
        arm["n"] += 1
        arm["alerts"] += int(s.get("alert", "0") == "1")
        arm["raw"] += int(s.get("is_anomaly", "0") == "1")
        w = vec_mag_deg(m.get("ADCS_GNC.wbn", SENTINEL))
        if w is not None:
            arm["rates"].append(w)

    counted = arms["controlled"]["n"]
    uncontrolled = arms["uncontrolled"]["n"]
    if not counted and not uncontrolled:
        print("no MODE_INERTIAL frames in the window at all", file=sys.stderr)
        return 1
    if not counted:
        # Expected for every session recorded before 2026-09-10: the star tracker
        # was never enabled, so the loop was never closed. Report the loop-open
        # arm — that IS the historical baseline this measurement compares to.
        u = arms["uncontrolled"]
        u_w = (sum(u["rates"]) / len(u["rates"])) if u["rates"] else float("nan")
        print(f"side-file : {os.path.basename(side)}")
        print(f"main log  : {os.path.basename(main_log)}")
        print(f"window    : frames {lo}..{n-1}")
        print()
        print(f"  ⚠ NO controlled INERTIAL frames — qValid=0 throughout.")
        print(f"    This session is loop-OPEN (free drift labelled INERTIAL).")
        print(f"    frames {u['n']:6d}  mean |w| {u_w:7.4f} deg/s")
        print(f"    operational FP {u['alerts']/u['n']:8.4%}   "
              f"raw FP {u['raw']/u['n']:8.4%}")
        if args.json:
            with open(args.json, "w") as fh:
                json.dump({"side_file": os.path.basename(side),
                           "controlled_frames": 0,
                           "loop_open_frames": u["n"],
                           "loop_open_operational_fp": u["alerts"] / u["n"],
                           "loop_open_raw_fp": u["raw"] / u["n"],
                           "loop_open_mean_body_rate_deg_s": u_w}, fh, indent=2)
            print(f"\nwrote {args.json}")
        return 0

    op_fp = arms["controlled"]["alerts"] / counted
    raw_fp = arms["controlled"]["raw"] / counted
    rates = arms["controlled"]["rates"]
    dur_min = counted / args.hz / 60.0

    print(f"side-file : {os.path.basename(side)}")
    print(f"main log  : {os.path.basename(main_log)}")
    print(f"window    : frames {lo}..{n-1}  (skipped {skip} transient frames)")
    print(f"rate      : {args.hz:.2f} Hz "
          f"({'derived from CFE_TIME.SecondsMET' if ap.get_default('hz') is None else 'given'})")
    print()
    print(f"  frames labelled MODE_INERTIAL      {labelled_inertial:7d}")
    print(f"    of which loop OPEN (qValid=0)    {uncontrolled:7d}  "
          f"({uncontrolled/max(labelled_inertial,1):.1%})  <- NOT nominal INERTIAL")
    print(f"    of which CONTROLLED (qValid=1)   {counted:7d}  "
          f"= {dur_min:.1f} min at {args.hz:.2f} Hz")
    if rates:
        print(f"  mean |w| over counted frames       {sum(rates)/len(rates):7.4f} deg/s")
    print()
    print(f"  operational FP (alert)   {op_fp:8.4%}   {'PASS' if op_fp < 0.01 else 'FAIL'} vs 1% target")
    print(f"  raw FP (is_anomaly)      {raw_fp:8.4%}")

    # The control arm
    u = arms["uncontrolled"]
    print()
    print("  like-for-like control — same session, same model, loop OPEN:")
    if u["n"]:
        u_op, u_raw = u["alerts"] / u["n"], u["raw"] / u["n"]
        u_w = (sum(u["rates"]) / len(u["rates"])) if u["rates"] else float("nan")
        print(f"    frames {u['n']:6d}   mean |w| {u_w:7.4f} deg/s")
        print(f"    operational FP {u_op:8.4%}   raw FP {u_raw:8.4%}")
        print(f"    -> closing the loop changes operational FP "
              f"{u_op:.4%} -> {op_fp:.4%}")
    else:
        print("    no loop-open INERTIAL frames in this window "
              "(nothing to compare against; report the controlled arm alone)")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({
                "side_file": os.path.basename(side),
                "main_log": os.path.basename(main_log),
                "window_start_frame": lo,
                "window_end_frame": n - 1,
                "frames_labelled_inertial": labelled_inertial,
                "frames_loop_open": uncontrolled,
                "frames_controlled": counted,
                "duration_min": dur_min,
                "mean_body_rate_deg_s": (sum(rates) / len(rates)) if rates else None,
                "operational_fp": op_fp,
                "raw_fp": raw_fp,
                "control_arm_loop_open": {
                    "frames": u["n"],
                    "operational_fp": (u["alerts"] / u["n"]) if u["n"] else None,
                    "raw_fp": (u["raw"] / u["n"]) if u["n"] else None,
                    "mean_body_rate_deg_s": (sum(u["rates"]) / len(u["rates"])) if u["rates"] else None,
                },
                "target": 0.01,
                "pass": op_fp < 0.01,
            }, fh, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
