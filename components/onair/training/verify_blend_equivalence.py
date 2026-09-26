#!/usr/bin/env python3
"""Prove the live blend equals the offline blend — AINOS3-126 AC2.

    deinterleave_csv.py(raw)  ==  the adapter's native blend

This is the deliverable of AINOS3-126, not the adapter code. If the two ever
disagree, offline results stop predicting live behaviour and NOTHING in the
system would notice: the models would be fitted on one representation and
scoring another, and every offline A/B would be measuring a stream the
pipeline does not produce.

The proof is deterministic rather than statistical. Both sides consume the
identical recorded frame sequence — `sbn_adapter_blended` runs the transform on
the frames as they are emitted, and this script re-runs it on the raw file
written from those same frames — so the comparison is exact equality, not a
replay approximation or a tolerance.

⚠ Run it in ALL FOUR ADCS modes. The buffer mechanism is mode-agnostic, but
each mode exercises different fields at different rates, and the transform is
per-field.

Usage:
    # explicit pair
    python3 components/onair/training/verify_blend_equivalence.py \\
        --raw data/onair/csv/csv_out_....csv \\
        --blended data/onair/csv/csv_blended_....csv

    # a whole collection: --dir is the RAW dir; blended is looked for in the
    # sibling csv_blended/ (override with --blended-dir). Pairs by pid, since
    # both files are written by the same OnAIR process.
    python3 components/onair/training/verify_blend_equivalence.py \\
        --dir data/onair/csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deinterleave_csv import deinterleave  # noqa: E402

_PID_RE = re.compile(r'_pid(\d+)\.csv$')
_TS_RE = re.compile(r'csv_out_(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d+)_pid')


def _pid_of(path):
    m = _PID_RE.search(os.path.basename(path))
    return m.group(1) if m else None


def _ts_of(path):
    """Start timestamp from the filename, as a float epoch."""
    m = _TS_RE.search(os.path.basename(path))
    if not m:
        return None
    try:
        return dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H-%M-%S-%f").timestamp()
    except ValueError:
        return None


# ⚠ pid ALONE does not identify a run. OnAIR is always pid 11 inside its
# container, so every file in a corpus shares it (478 of them, measured
# 2026-09-20). The adapter and csv_output open their files milliseconds apart
# within the same process, so the real key is (pid, nearest start timestamp).
_PAIR_TOLERANCE_S = 2.0


def compare(raw_path: str, blended_path: str, max_report: int = 10,
            max_rows: int = 0) -> dict:
    """Blend `raw_path` offline and compare cell-for-cell against `blended_path`.

    ⚠ `max_rows` bounds how much is loaded. A session CSV is unbounded
    (`LinesPerFile = 0`), and at 470 columns a 100k-row file is several GB once
    parsed into dicts. The blend is a prefix-stable fold — row i depends only on
    rows 0..i — so checking a prefix is a valid proof about that prefix.
    """
    def _read(path):
        with open(path, newline="") as fh:
            rdr = csv.DictReader(fh)
            fields = list(rdr.fieldnames or [])
            if max_rows:
                rows = [r for _, r in zip(range(max_rows), rdr)]
            else:
                rows = list(rdr)
        return fields, rows

    raw_fields, raw_rows = _read(raw_path)
    blend_fields, blend_rows = _read(blended_path)

    result = {
        "raw": os.path.basename(raw_path),
        "blended": os.path.basename(blended_path),
        "raw_rows": len(raw_rows),
        "blended_rows": len(blend_rows),
        "ok": False,
        "diffs": [],
        "note": "",
    }

    if raw_fields != blend_fields:
        only_raw = [f for f in raw_fields if f not in set(blend_fields)]
        only_blend = [f for f in blend_fields if f not in set(raw_fields)]
        result["note"] = (f"HEADER MISMATCH: {len(raw_fields)} raw vs "
                          f"{len(blend_fields)} blended cols; "
                          f"only-raw={only_raw[:5]} only-blended={only_blend[:5]}")
        return result

    if not raw_rows:
        result["note"] = "raw file is empty"
        return result

    expected, _stats = deinterleave(raw_rows, raw_fields)

    # ⚠ A row-count difference of exactly 1 is EXPECTED and benign at the tail:
    # the adapter writes the blended row inside get_next(), while csv_output
    # writes the raw row later in the same loop iteration, so a process killed
    # mid-frame can leave the blended file one row ahead. Compare the common
    # prefix and say so, rather than failing a run over a torn tail.
    n = min(len(expected), len(blend_rows))
    if len(expected) != len(blend_rows):
        delta = len(blend_rows) - len(expected)
        if abs(delta) == 1:
            result["note"] = (f"row counts differ by {delta} (torn tail — the "
                              f"blended row is written before the raw one); "
                              f"compared the common {n} rows")
        else:
            result["note"] = (f"ROW COUNT MISMATCH: blended has "
                              f"{len(blend_rows)}, offline blend of raw has "
                              f"{len(expected)} (delta {delta}); compared {n}")
            return result

    diffs = 0
    for i in range(n):
        e, g = expected[i], blend_rows[i]
        for f in raw_fields:
            if e[f] != g[f]:
                diffs += 1
                if len(result["diffs"]) < max_report:
                    result["diffs"].append(
                        {"row": i, "column": f, "offline": e[f], "native": g[f]})
    result["compared_rows"] = n
    result["diff_cells"] = diffs
    result["ok"] = diffs == 0
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw")
    p.add_argument("--blended")
    p.add_argument("--dir", help="the RAW dir; blended is taken from --blended-dir "
                                 "or the sibling csv_blended/. Pairs by pid.")
    p.add_argument("--blended-dir", help="the BLENDED dir (default: "
                                         "<dir>/../csv_blended). Blended files "
                                         "keep the csv_out_* basename.")
    p.add_argument("--max-report", type=int, default=10)
    p.add_argument("--max-rows", type=int, default=0,
                   help="compare only the first N rows (0 = all). Session CSVs "
                        "are unbounded; the blend is a prefix-stable fold, so a "
                        "prefix check is a valid proof about that prefix.")
    args = p.parse_args()

    pairs = []
    if args.dir:
        # The blended stream lives in its own directory (AINOS3-126). Fall back
        # to --dir itself so a hand-assembled pair in one folder still works.
        bdirs = [args.blended_dir] if args.blended_dir else [
            os.path.join(os.path.dirname(args.dir.rstrip('/')) or '.', 'csv_blended'),
        ]
        # ⚠ Blended files keep the csv_out_* basename (the DIRECTORY carries
        # the meaning), so never glob the raw dir for them — that would pair a
        # file with itself and report a vacuous PASS.
        bfiles = []
        for d in bdirs:
            if os.path.abspath(d) == os.path.abspath(args.dir):
                continue
            bfiles = sorted(glob.glob(os.path.join(d, "csv_out_*.csv")))
            if bfiles:
                print(f"blended dir: {d}")
                break
        raws = {}
        for f in sorted(glob.glob(os.path.join(args.dir, "csv_out_*.csv"))):
            pid = _pid_of(f)
            if pid:
                raws.setdefault(pid, []).append(f)
        for b in bfiles:
            pid, bts = _pid_of(b), _ts_of(b)
            cand = raws.get(pid, [])
            if not cand:
                print(f"⚠ no raw file with pid {pid} for {os.path.basename(b)}")
                continue
            scored = [(abs(_ts_of(c) - bts), c) for c in cand
                      if _ts_of(c) is not None and bts is not None]
            scored.sort()
            if scored and scored[0][0] <= _PAIR_TOLERANCE_S:
                pairs.append((scored[0][1], b))
            else:
                near = f"{scored[0][0]:.1f}s" if scored else "n/a"
                print(f"⚠ no raw file within {_PAIR_TOLERANCE_S}s of "
                      f"{os.path.basename(b)} (nearest {near}); "
                      f"pass --raw/--blended explicitly")
        if not pairs:
            sys.exit(f"no raw/blended pairs found (raw={args.dir}, "
                     f"blended tried={bdirs})")
    else:
        if not (args.raw and args.blended):
            sys.exit("need --raw and --blended, or --dir")
        pairs = [(args.raw, args.blended)]

    failed = 0
    for raw, blended in pairs:
        r = compare(raw, blended, args.max_report, args.max_rows)
        tag = "PASS" if r["ok"] else "FAIL"
        if not r["ok"]:
            failed += 1
        print(f"[{tag}] {r['blended']}  ({r.get('compared_rows', 0)} rows"
              f"{', ' + str(r['diff_cells']) + ' differing cells' if r.get('diff_cells') else ''})")
        if r["note"]:
            print(f"       note: {r['note']}")
        for d in r["diffs"]:
            print(f"       row {d['row']} col {d['column']}: "
                  f"offline={d['offline']!r} native={d['native']!r}")

    print(f"\n{len(pairs) - failed}/{len(pairs)} pair(s) equivalent")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
