#!/usr/bin/env python3
"""Verify that an INERTIAL hold actually closed its control loop.

WHY THIS EXISTS (AINOS3-86)
---------------------------
`ST.DeviceEnabled = 1` is **not** evidence that INERTIAL is under closed-loop
control, and treating it as such is what made two sprints of INERTIAL results
describe uncontrolled drift:

    ST.DeviceEnabled = 1        the command was accepted
    ST_DEV…IsValid   = 0        42 says the boresight is Earth-occulted
    ADCS_DI.St.valid = 0
    ADCS_GNC.qValid  = 0        <-- gates AC_inertial()
    AC_inertial()               never executes; Tcmd frozen; free drift

A run in that state looks configured and produces a full CSV. Nothing in its own
output says the mode was never held. So every INERTIAL collection must assert
capture against telemetry before its data is allowed to count.

WHAT CAPTURE MEANS
------------------
1. `ADCS_GNC.qValid == 1` sustained (not a boundary flicker at the edge of an
   exclusion window), and
2. the controller is actually producing varying torque -- `ADCS_AC.Inertial.*`
   are identically zero whenever the law is skipped, so "is it non-constant"
   separates a running controller from a skipped one.

⚠ Read the ACTIVELY GROWING csv, past OnAIR's ~30-60 s startup warmup, and parse
with `csv.DictReader` by header name -- never `awk -F','`, which misaligns on the
quoted array columns this file is full of.

USAGE
-----
    # block until captured (default), for use before a measurement window
    python3 inertial_capture.py --wait --timeout-min 45

    # just report the current state and exit
    python3 inertial_capture.py
"""
import argparse
import csv
import glob
import math
import os
import sys
import time

SENTINEL = "[0]"
QVALID = "ADCS_GNC.qValid"
STVALID = "ST_DEV.Generic_star_tracker.IsValid"
STEN = "ST.DeviceEnabled"
CTRL = ["ADCS_AC.Inertial.therr", "ADCS_AC.Inertial.qErr",
        "ADCS_AC.Inertial.werr", "ADCS_AC.Inertial.Tcmd"]
WBN = "ADCS_GNC.wbn"
MODE = "ADCS_GNC.Mode"
MODE_INERTIAL = "3"

DEFAULT_CSV_GLOB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..", "data", "onair", "csv", "csv_out_*.csv")


def newest_csv(pattern):
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _vec_mag_deg(text):
    """|w| in deg/s from a bracketed array column. None if unparseable."""
    import ast
    try:
        v = ast.literal_eval(text)
        return math.sqrt(sum(float(c) ** 2 for c in v)) * 180.0 / math.pi
    except Exception:
        return None


def body_rate_deg_s(path, tail_frames=200):
    """Mean |w| over the last `tail_frames` frames, deg/s.

    Used to gate the detumble step: an INERTIAL hold entered from a tumbling
    state DIVERGES rather than captures (measured 2026-09-10: 0.64 -> 2.31 deg/s
    in 60 s), because while the star tracker is blinded the control law is
    skipped entirely, so torque arrives in bursts that pump energy in.
    """
    with open(path, newline="") as fh:
        rows = [r for r in csv.DictReader(fh)][-tail_frames:]
    vals = [_vec_mag_deg(r[WBN]) for r in rows if r.get(WBN, SENTINEL) != SENTINEL]
    vals = [v for v in vals if v is not None]
    return (sum(vals) / len(vals)) if vals else None


def sample(path, tail_frames=400):
    """Summarise the last `tail_frames` complete rows of a live CSV."""
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        rows = [r for r in rd]
    rows = rows[-tail_frames:]
    if not rows:
        return None

    def live(col):
        return [r.get(col, SENTINEL) for r in rows if r.get(col, SENTINEL) != SENTINEL]

    qv = live(QVALID)
    stv = live(STVALID)
    sten = live(STEN)
    mode = live(MODE)
    ctrl_moving = {}
    for c in CTRL:
        vals = live(c)
        ctrl_moving[c] = len(set(vals)) > 1 if vals else False

    return {
        "frames": len(rows),
        "mode_inertial_frac": (mode.count(MODE_INERTIAL) / len(mode)) if mode else 0.0,
        "qvalid_frac": (qv.count("1") / len(qv)) if qv else 0.0,
        "stvalid_frac": (stv.count("1") / len(stv)) if stv else 0.0,
        "st_enabled": ("1" in sten),
        "ctrl_moving": ctrl_moving,
        "ctrl_any_moving": any(ctrl_moving.values()),
    }


def verdict(s, qvalid_min=0.90):
    """CAPTURED only if qValid is sustained AND the control law is producing output."""
    if s is None:
        return False, "no rows yet"
    if not s["st_enabled"]:
        return False, "star tracker is DISABLED — nothing will ever validate"
    if s["mode_inertial_frac"] < 0.5:
        return False, f"not in INERTIAL (mode 3 in {s['mode_inertial_frac']:.0%} of frames)"
    if s["qvalid_frac"] < qvalid_min:
        if s["qvalid_frac"] == 0.0:
            return False, ("qValid=0 — the star tracker is blinded (Earth exclusion); "
                           "the control law is NOT running")
        return False, (f"qValid only {s['qvalid_frac']:.0%} — intermittent, so the vehicle "
                       "is near an exclusion boundary rather than holding")
    if not s["ctrl_any_moving"]:
        return False, ("qValid=1 but every ADCS_AC.Inertial.* field is constant — "
                       "the control law is not producing output")
    return True, (f"CAPTURED — qValid {s['qvalid_frac']:.0%}, controller active")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=None, help="CSV to read (default: newest live one)")
    ap.add_argument("--wait", action="store_true", help="block until captured")
    ap.add_argument("--timeout-min", type=float, default=45.0,
                    help="give up after this long. The blind stretch is ~35 min, "
                         "so anything under 40 can fail on timing alone.")
    ap.add_argument("--poll-s", type=float, default=30.0)
    ap.add_argument("--tail-frames", type=int, default=400)
    ap.add_argument("--rate-only", action="store_true",
                    help="report mean |w| in deg/s and exit — the detumble gate")
    ap.add_argument("--rate-below", type=float, default=None,
                    help="with --wait: succeed once mean |w| drops below this (deg/s), "
                         "instead of waiting for INERTIAL capture")
    args = ap.parse_args()

    path = args.csv or newest_csv(DEFAULT_CSV_GLOB)
    if not path:
        print("no CSV found — is OnAIR running?", file=sys.stderr)
        return 2
    print(f"reading {os.path.basename(path)}")

    if args.rate_only or args.rate_below is not None:
        deadline = time.time() + args.timeout_min * 60
        while True:
            w = body_rate_deg_s(path)
            stamp = time.strftime("%H:%M:%S")
            print(f"  [{stamp}] |w| = {w:.4f} deg/s" if w is not None
                  else f"  [{stamp}] no body-rate samples yet")
            if args.rate_only:
                return 0
            if w is not None and w < args.rate_below:
                print(f"DETUMBLED (|w| < {args.rate_below} deg/s)")
                return 0
            if not args.wait or time.time() > deadline:
                print(f"NOT DETUMBLED — |w| = {w} deg/s", file=sys.stderr)
                return 1
            time.sleep(args.poll_s)

    deadline = time.time() + args.timeout_min * 60
    while True:
        s = sample(path, args.tail_frames)
        ok, why = verdict(s)
        stamp = time.strftime("%H:%M:%S")
        if s:
            print(f"  [{stamp}] qValid {s['qvalid_frac']:5.0%}  ST_DEV.IsValid "
                  f"{s['stvalid_frac']:5.0%}  ctrl_active={s['ctrl_any_moving']}  -> {why}")
        else:
            print(f"  [{stamp}] {why}")
        if ok:
            print("CAPTURED")
            return 0
        if not args.wait or time.time() > deadline:
            print(f"NOT CAPTURED — {why}", file=sys.stderr)
            return 1
        time.sleep(args.poll_s)


if __name__ == "__main__":
    sys.exit(main())
