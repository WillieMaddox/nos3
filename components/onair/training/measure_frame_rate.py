#!/usr/bin/env python3
"""Measure OnAIR's frame rate against the live SBN message rate (AINOS3-95 stage 0).

Answers the question that gates any new subscription: **if we subscribe more MIDs,
does the frame rate move?** The answer depends on which side is the bottleneck:

* **arrival-bound** — frames track messages, so more MIDs means more frames, and
  every per-frame-rate threshold (rule-gate R2, the staleness gate's advance
  interval) shifts upward.
* **compute-bound** — the OnAIR loop is already saturated, so more MIDs do NOT
  raise the frame rate. The risk inverts: added columns make each frame more
  expensive, so the rate can *fall*.

Measured 2026-08-25 on the deployed stack: 20.26 msg/s in, 5.49 frames/s out —
**compute-bound**, with ~73 % of messages overwritten in the write buffer before
being read. `onair/src/run_scripts/sim.py` has no rate limiter, which confirms the
ceiling is processing cost rather than configuration.

Two independent sources, deliberately not derived from each other:

* **frame rate** — row growth in the live CSV over a wall-clock window.
* **message rate** — `Message Header: StreamID: 0x...` lines in the OnAIR
  container log, one per received message, giving an exact per-MID breakdown.

Silent MIDs (subscribed, zero traffic in the window) are reported separately:
those are dead subscriptions, and they are easy to mistake for inert fields.

Run:
    python3 components/onair/training/measure_frame_rate.py --seconds 120
    python3 components/onair/training/measure_frame_rate.py --project 0x0942,0x0944
"""
from __future__ import annotations

import argparse
import collections
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCHEMA = os.path.join(ROOT, "components/onair/nos3_security_tlm.json")
CSV_GLOB = os.path.join(ROOT, "data/onair/csv/csv_out_*.csv")
CONTAINER = "sc01-onair"

_TS = re.compile(r"(\.\d{6})\d*Z")
_LINE = re.compile(r"^(\S+)\s.*StreamID: (0x[0-9a-fA-F]+)")


def newest_csv():
    files = glob.glob(CSV_GLOB)
    if not files:
        sys.exit(f"no CSV matching {CSV_GLOB} — is OnAIR running?")
    return max(files, key=os.path.getmtime)


def rows(path):
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def frame_rate(path, seconds, step=10):
    """Row growth over a wall-clock window; returns (rate, per-interval rates)."""
    marks = []
    deadline = time.time() + seconds
    while True:
        marks.append((time.time(), rows(path)))
        if time.time() >= deadline:
            break
        time.sleep(min(step, max(0.0, deadline - time.time())))
    (t0, n0), (t1, n1) = marks[0], marks[-1]
    per = [(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(marks, marks[1:])
           if b[0] > a[0]]
    return (n1 - n0) / (t1 - t0), per


def message_rates(seconds):
    """Per-MID arrival counts from the OnAIR container log."""
    try:
        out = subprocess.run(
            ["docker", "logs", CONTAINER, "-t", "--since", f"{int(seconds)}s"],
            capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        sys.exit(f"could not read `docker logs {CONTAINER}`: {e}")
    stamps, counts = [], collections.Counter()
    for line in (out.stdout + out.stderr).splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        stamps.append(datetime.datetime.fromisoformat(
            _TS.sub(r"\1+00:00", m.group(1))))
        counts[int(m.group(2), 16)] += 1
    if len(stamps) < 2:
        sys.exit(f"no StreamID lines in {CONTAINER}'s log — is it logging?")
    return (stamps[-1] - stamps[0]).total_seconds(), counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=int, default=120, help="measurement window")
    ap.add_argument("--project", default="",
                    help="comma-separated MIDs to project, e.g. 0x0942,0x0944")
    ap.add_argument("--json", help="write the measurement here")
    args = ap.parse_args(argv)

    channels = json.load(open(SCHEMA))["channels"]
    name = {int(k, 16): v[0] for k, v in channels.items()}

    csv_path = newest_csv()
    print(f"CSV  : {os.path.basename(csv_path)}")
    print(f"window: {args.seconds}s\n")
    fr, per = frame_rate(csv_path, args.seconds)
    span, counts = message_rates(args.seconds)
    total = sum(counts.values())
    mr = total / span

    print(f"frames  {fr:6.2f} /s   (min {min(per):.2f} max {max(per):.2f})")
    print(f"messages{mr:6.2f} /s   ({total} over {span:.1f}s, {len(counts)} MIDs)")
    ratio = fr / mr if mr else 0
    print(f"ratio   {ratio:6.1%}   -> "
          + ("ARRIVAL-BOUND: more MIDs will RAISE the frame rate"
             if ratio > 0.9 else
             f"COMPUTE-BOUND: {1-ratio:.0%} of messages are overwritten before "
             "being read.\n          More MIDs will NOT raise the frame rate; more "
             "COLUMNS can lower it."))

    print("\nper-MID arrivals")
    for mid, n in counts.most_common():
        print(f"  0x{mid:04X} {name.get(mid,'(unsubscribed)'):14s} {n:5d}  {n/span:6.2f} /s")

    silent = sorted(set(int(k, 16) for k in channels) - set(counts))
    if silent:
        print(f"\n⚠ {len(silent)} SUBSCRIBED BUT SILENT — dead subscriptions, easily "
              f"mistaken for inert fields:")
        for m in silent:
            print(f"  0x{m:04X} {name[m]}")

    if args.project:
        want = [int(x, 16) for x in args.project.replace(" ", "").split(",")]
        # A MID published on a known send path arrives at that path's rate; the
        # ADCS AD/AC packets are siblings of DI/GNC/DO in generic_adcs_app.c.
        adcs = [counts[m] / span for m in (0x0941, 0x0943, 0x0945) if counts.get(m)]
        est = sum(adcs) / len(adcs) if adcs else 1.0
        add = est * len(want)
        print(f"\nprojection: +{len(want)} MID(s) at ~{est:.2f} /s each "
              f"(ADCS send-path rate) = +{add:.2f} msg/s")
        print(f"  arrivals {mr:.2f} -> {mr+add:.2f} /s  (+{add/mr:.1%})")
        print(f"  frames   {fr:.2f} /s expected UNCHANGED while compute-bound; "
              f"re-measure after the columns land")

    if args.json:
        json.dump({"frame_rate": fr, "message_rate": mr, "ratio": ratio,
                   "span_s": span, "per_mid": {f"0x{m:04X}": n for m, n in counts.items()},
                   "silent": [f"0x{m:04X}" for m in silent]},
                  open(args.json, "w"), indent=1)
        print(f"\n-> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
