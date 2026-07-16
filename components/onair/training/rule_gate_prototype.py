#!/usr/bin/env python3
"""Parallel rule-gate prototype — catch the state-change attacks the v5 IF misses.

The Section-A validation (2026-07-16) found the deployed IF is a *dynamics*
detector: it flags anomalies in the GNC/attitude physics it's trained on, but is
structurally blind to attacks whose footprint is a **discrete flag flip or a
counter/rate spike** that doesn't disturb the physics (DE-0010 EVS flood,
EX-0002 GPS disable, EX-0014.03 IMU disable — all is_anomaly=0). Because the
classifier is IF-gated, those are undetected end-to-end despite loud, subscribed
signals.

This is a lightweight rule/threshold layer meant to run ALONGSIDE the IF (an OR
of the two gates feeds the classifier / incident aggregator). Offline prototype:
score a recorded CSV and show it fires on the validated attacks at ~0 nominal FP.

Rules (each is a per-frame boolean; an alert = any rule fires):
  R1 device-disable : any `*.DeviceEnabled` drops below its session baseline
                      (a normally-on sensor/subsystem was disabled).
  R2 evs-flood      : per-frame delta of CFE_EVS_HK.MessageSendCounter exceeds a
                      threshold set above the nominal background rate.
  R3 sb-errors      : per-frame delta of CFE_SB.MsgSendErrorCounter > 0.
  R4 cmd-errors     : per-frame delta of any `*.CommandError*` counter exceeds a
                      threshold (an attack driving rejected commands).

Usage:
    python3 rule_gate_prototype.py --csv data/onair/csv/csv_out_<...>.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load(csv_path):
    rows = list(csv.DictReader(open(csv_path)))
    return rows, (list(rows[0].keys()) if rows else [])


def rule_gate(rows, cols, *, evs_thresh=None, cmderr_thresh=3, baseline_n=40):
    """Return per-frame rule flags + episode summary.

    Thresholds: evs_thresh auto-set to max(nominal-window delta)+margin if None.
    """
    enable_cols = [c for c in cols if c.endswith(".DeviceEnabled")]
    cmderr_cols = [c for c in cols if re.search(r"CommandError(Count|Counter)$", c)]
    evs_col = "CFE_EVS_HK.MessageSendCounter"
    sb_col = "CFE_SB.MsgSendErrorCounter"

    # Session baseline for enable flags: the max value seen in the first N frames
    # (a device that is 1 early and later 0 = a disable; devices that boot 0 are
    # ignored, so we don't false-alarm on sun/star sensors that start invalid).
    base_enable = {}
    for c in enable_cols:
        vals = [_num(rows[i].get(c)) for i in range(min(baseline_n, len(rows)))]
        vals = [v for v in vals if v is not None]
        base_enable[c] = max(vals) if vals else 0.0

    # Auto EVS threshold: max per-frame delta over the baseline window * 2, min 15.
    if evs_thresh is None:
        base_deltas = []
        prev = None
        for i in range(min(baseline_n, len(rows))):
            v = _num(rows[i].get(evs_col))
            if v is not None and prev is not None:
                base_deltas.append(v - prev)
            if v is not None:
                prev = v
        evs_thresh = max(15.0, (max(base_deltas) if base_deltas else 0) * 2 + 5)

    flags = []  # per frame: set of rule ids that fired
    prev = {evs_col: None, sb_col: None}
    prev_cmderr = {c: None for c in cmderr_cols}
    for r in rows:
        fired = set()
        # R1 device-disable
        for c in enable_cols:
            v = _num(r.get(c))
            if v is not None and v < base_enable.get(c, 0):
                fired.add(f"R1:{c.split('.')[0]}-disabled")
        # R2 evs-flood
        v = _num(r.get(evs_col))
        if v is not None and prev[evs_col] is not None and (v - prev[evs_col]) > evs_thresh:
            fired.add("R2:evs-flood")
        if v is not None:
            prev[evs_col] = v
        # R3 sb-errors
        v = _num(r.get(sb_col))
        if v is not None and prev[sb_col] is not None and (v - prev[sb_col]) > 0:
            fired.add("R3:sb-errors")
        if v is not None:
            prev[sb_col] = v
        # R4 cmd-errors
        for c in cmderr_cols:
            v = _num(r.get(c))
            if v is not None and prev_cmderr[c] is not None and (v - prev_cmderr[c]) > cmderr_thresh:
                fired.add(f"R4:{c.split('.')[0]}-cmderr")
            if v is not None:
                prev_cmderr[c] = v
        flags.append(fired)

    # collapse contiguous alert frames into episodes
    episodes = []
    i = 0
    n = len(flags)
    while i < n:
        if flags[i]:
            j = i
            rules = set()
            while j < n and flags[j]:
                rules |= flags[j]
                j += 1
            episodes.append((i, j - 1, j - i, rules))
            i = j
        else:
            i += 1
    return {
        "evs_thresh": evs_thresh,
        "enable_cols": enable_cols,
        "cmderr_cols": cmderr_cols,
        "n_frames": n,
        "n_alert_frames": sum(1 for f in flags if f),
        "episodes": episodes,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", default=None, help="CSV to score (default: newest csv_out_*)")
    args = p.parse_args()
    path = args.csv or max(glob.glob("data/onair/csv/csv_out_*.csv"), key=os.path.getmtime)
    rows, cols = load(path)
    res = rule_gate(rows, cols)
    print(f"CSV: {os.path.basename(path)}  ({res['n_frames']} frames)")
    print(f"enable flags watched: {len(res['enable_cols'])}  cmd-err counters: {len(res['cmderr_cols'])}")
    print(f"EVS-flood threshold (auto): >{res['evs_thresh']:.0f} events/frame")
    print(f"alert frames: {res['n_alert_frames']}/{res['n_frames']} "
          f"({100*res['n_alert_frames']/max(1,res['n_frames']):.2f}%)")
    print(f"\n{len(res['episodes'])} alert episodes:")
    for start, end, length, rules in res["episodes"]:
        print(f"  frames {start:>6}-{end:<6} ({length:>4}f)  rules: {', '.join(sorted(rules))}")


if __name__ == "__main__":
    main()
