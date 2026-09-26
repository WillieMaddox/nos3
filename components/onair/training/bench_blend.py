#!/usr/bin/env python3
"""Measure what the live blend costs per frame — AINOS3-126.

"Converting to a blended representation must not create a bottleneck" is a
claim that needs a number, and the number that matters is not microseconds in
isolation: it is the share of a frame the transform consumes. The OnAIR
recorder runs at a steady ~5-6 Hz, so the per-frame budget is ~170-200 ms.

Replays a real recorded CSV through the same `BlendEngine` and
`BlendedCsvWriter` the live adapter uses, and reports:

  * blend cost per frame (p50/p95/max)
  * blended-CSV write cost per frame
  * the RAW write cost for the same frames, as the baseline we already pay
  * the transform's share of a 5 Hz frame

⚠ `--as-objects` is the figure that matters. A CSV replay hands the engine
strings, where the LIVE path hands it ctypes-derived objects — 206 of 470
columns in a real frame are nested lists — and `str()` on those is most of the
per-frame cost. `--as-objects` parses the array cells back into Python lists so
the bench measures the real stringify leg instead of a cheap lower bound.

⚠ It still does not replace the live profiler: use `[SBN_ADAPTER] ProfileEvery`
for the in-situ figure. This tells you the shape before you spend a collection
run finding out.

Usage:
    python3 components/onair/training/bench_blend.py \\
        --csv data/onair/csv/csv_out_....csv --rows 5000 --as-objects
"""
from __future__ import annotations

import argparse
import ast
import csv
import os
import statistics
import sys
import tempfile
import time
from unittest.mock import MagicMock

# The adapter module imports the SBN client transitively; stub it so the bench
# runs on a dev box instead of only inside the FSW container.
sys.modules.setdefault('sbn_python_client', MagicMock())
sys.modules.setdefault('message_headers', MagicMock())
sys.modules.setdefault('sbn_client', MagicMock())
_FSW = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fsw')
sys.path.insert(0, os.path.abspath(_FSW))

from onair.data_handling.sbn_adapter_blended import (  # noqa: E402
    BlendEngine, BlendedCsvWriter, _stringify)


def _pct(xs, p):
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1))))]


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", required=True, help="a recorded csv_out_*.csv")
    p.add_argument("--rows", type=int, default=5000)
    p.add_argument("--hz", type=float, default=5.0, help="recorder frame rate the share is computed against")
    p.add_argument("--as-objects", action="store_true",
                   help="parse array cells back into Python lists, so the "
                        "stringify cost matches the live path")
    args = p.parse_args()

    with open(args.csv, newline="") as fh:
        rdr = csv.DictReader(fh)
        fields = list(rdr.fieldnames or [])
        rows = []
        for i, r in enumerate(rdr):
            if i >= args.rows:
                break
            rows.append([r[f] for f in fields])

    if not rows:
        sys.exit(f"no rows read from {args.csv}")

    n_arr = 0
    if args.as_objects:
        for row in rows:
            for j, v in enumerate(row):
                if v[:1] == "[":
                    try:
                        row[j] = ast.literal_eval(v)
                    except (ValueError, SyntaxError):
                        pass
        n_arr = sum(1 for v in rows[0] if isinstance(v, list))

    n = len(fields)
    print(f"{os.path.basename(args.csv)}: {len(rows)} frames x {n} columns"
          + (f" ({n_arr} array-valued, parsed back to objects)" if args.as_objects
             else " (strings as recorded — a LOWER BOUND, see --as-objects)"))

    with tempfile.TemporaryDirectory() as td:
        engine = BlendEngine(n)
        blend_w = BlendedCsvWriter(fields, td, "bench_blended_{pid}", set())
        raw_w = BlendedCsvWriter(fields, td, "bench_raw_{pid}", set())

        blend_us, bw_us, rw_us = [], [], []
        for i, frame in enumerate(rows):
            t0 = time.perf_counter()
            bs, _bo = engine.feed(frame, i % 2)
            t1 = time.perf_counter()
            blend_w.write(bs)
            t2 = time.perf_counter()
            raw_w.write([_stringify(v) for v in frame])
            t3 = time.perf_counter()
            blend_us.append((t1 - t0) * 1e6)
            bw_us.append((t2 - t1) * 1e6)
            rw_us.append((t3 - t2) * 1e6)
        blend_w.close()
        raw_w.close()

    budget_us = 1e6 / args.hz
    tot50 = _pct(blend_us, 50) + _pct(bw_us, 50)

    def line(name, xs):
        print(f"  {name:<22} p50 {_pct(xs, 50):8.1f}us   p95 {_pct(xs, 95):8.1f}us   "
              f"max {max(xs):8.1f}us   mean {statistics.mean(xs):8.1f}us")

    print()
    line("blend", blend_us)
    line("write blended CSV", bw_us)
    line("write raw CSV (base)", rw_us)
    print()
    print(f"  frame budget at {args.hz:g} Hz: {budget_us/1000:.0f} ms")
    print(f"  blend + blended write, p50: {tot50/1000:.3f} ms "
          f"= {tot50/budget_us*100:.3f}% of a frame")
    print(f"  sustained blend-only throughput: "
          f"{1e6/statistics.mean(blend_us):,.0f} frames/s "
          f"({1e6/statistics.mean(blend_us)/args.hz:,.0f}x the recorder rate)")
    # ⚠ In `tap` mode the frame is stringified twice — once by the blend, once
    # by csv_output for the raw file. `inline` mode pays it once. Worth stating
    # because tap is the verification mode, not the end state.
    print(f"  note: tap mode stringifies each frame TWICE (blend + csv_output); "
          f"inline mode pays it once")
    print()
    print(f"  engine stats: {engine.stats()}")


if __name__ == "__main__":
    main()
