#!/usr/bin/env python3
"""Rebuild a single coherent telemetry stream from OnAIR's interleaved double buffer.

THE PROBLEM
-----------
`sbn_adapter.DataSource` keeps two buffers. The listener thread writes each
arriving message into the *write* buffer, `currentData[(read_index + 1) % 2]`,
and every frame `get_next()` flips `read_index` and returns the other one. The
two are never reconciled — its own comment says so:

    "The double buffer does not clear between switching. If fresh data doesn't
     come in, stale data is returned (delayed by 1 frame)"

So each buffer is an independent, partially-stale snapshot and the CSV is two
interleaved sub-streams. Measured on the rebuild corpus: 49 of 454 non-constant
columns alternate on >50% of steady-state rows, and lag-1 deltas carry 4-6x the
noise of same-buffer (lag-2) deltas.

WHY NOT JUST TAKE THE LATEST VALUE
----------------------------------
The obvious fix — keep one "latest value" dict and overwrite per frame — is
WRONG here, and the reason is the whole point of this script. Buffer B's copy of
a field is not news just because B was read last; it is usually a STALE value
that B has been holding since the last message that happened to land in B. Let
it overwrite A's fresh update and the output flickers exactly as before.

A field is only news when it changed **relative to its own buffer's previous
frame**. So:

    for each frame, belonging to buffer b:
        for each field where frame[field] != ref[b][field]:
            blended[field] = frame[field]       # a genuine update from b
        ref[b] = frame                          # before the next frame arrives
        emit blended                            # carries every other field forward

Each output row is then composed of the most recent *genuine* value from both
sub-streams, and a field that neither buffer updated simply persists.

⚠ Subsampling by parity is NOT an alternative. Measured on SUNSAFE instance 1,
restricted to fields that are discrete in each run's own baseline, 55.6 % of the
novel values an attack produces appear in ONE parity only — including values that
persist for 47 frames. Keeping one sub-stream would throw away over half the
footprint evidence.

Usage:
    # one file, for inspection
    python3 components/onair/training/deinterleave_csv.py \\
        --in data/onair/csv/csv_out_....csv --out /tmp/blended.csv --report

    # whole directory
    python3 components/onair/training/deinterleave_csv.py \\
        --in-dir data/onair/csv --out-dir data/onair/csv_blended
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import sys

SENTINEL = "[0]"      # OnAIR's "this MID has never been received in this buffer"

# ⚠ The sentinel is WRITTEN, never blanked. Two behaviours are wanted at once and
# they are easy to confuse:
#
#   * `[0]` must never OVERWRITE good telemetry. Buffer B's un-received copy of a
#     field is not news; adopting it would undo A's real value. That is what this
#     script suppresses, and it is on by default.
#   * a field no buffer has ever received must still READ `[0]`, not "". Four
#     tools key on the literal sentinel and two of them fail SILENTLY on a blank:
#       - build_corpus_manifest.py:177  "" scores 1 (uncontrolled) not 0 (no data),
#         deflating controlled_fraction — the AINOS3-100 INERTIAL capture gate
#       - analyze_inertial_fp.py:195    "" is not skipped, so it lands in the
#         UNCONTROLLED arm — the AINOS3-86 0.00 % FP figure
#       - schema_audit.py:178 / audit_dead_columns.py:52  blanks are not counted,
#         so the 100 %-sentinel dead-column check finds nothing and AINOS3-108's
#         --require-no-new-silent regression gate passes everything
#     The ML path is blank-safe either way (features.py and both plugins treat
#     "", "[0]" and "nan" identically), so this is about the GATES, not the models.
#
# Initialising every field to the sentinel and refusing to adopt it gives both.


def assign_buffer(row: dict, refs: list[dict | None], strict_index: int) -> int:
    """Which buffer did this frame come from?

    Default is strict alternation, which is what the adapter does. This function
    also supports content-based assignment: a frame belongs to the buffer whose
    reference it resembles most, because a buffer retains its own previous state
    and therefore differs from it in only the handful of fields that got new
    messages. Used by `--detect` and, always, as a consistency CHECK — if the
    stream ever stops alternating strictly, a silent mis-assignment would corrupt
    every row after it.
    """
    if refs[0] is None or refs[1] is None:
        return strict_index
    d0 = sum(1 for k, v in row.items() if refs[0].get(k) != v)
    d1 = sum(1 for k, v in row.items() if refs[1].get(k) != v)
    if d0 == d1:
        return strict_index
    return 0 if d0 < d1 else 1


def deinterleave(rows: list[dict], fields: list[str], *, detect: bool = False, skip_sentinel: bool = True):
    """→ (blended rows, stats). See the module docstring for the rule."""
    refs: list[dict | None] = [None, None]
    # Seeded with the sentinel, not "": a field neither buffer ever delivers must
    # read [0] in the output, because the corpus gates gate on that literal.
    blended: dict = {f: SENTINEL for f in fields}
    out, updates = [], [0, 0]
    disagree = 0
    first_seen = [False, False]

    for i, row in enumerate(rows):
        strict = i % 2
        b = assign_buffer(row, refs, strict) if detect else strict
        if assign_buffer(row, refs, strict) != strict:
            disagree += 1

        ref = refs[b]
        if ref is None:
            # First frame from this buffer: nothing to diff against, so every
            # field it carries is adopted. This is what seeds the output.
            for f in fields:
                v = row.get(f, "")
                if skip_sentinel and v == SENTINEL:
                    continue
                blended[f] = v
            first_seen[b] = True
        else:
            for f in fields:
                v = row.get(f, "")
                if v != ref.get(f, ""):
                    if skip_sentinel and v == SENTINEL:
                        continue
                    blended[f] = v
                    updates[b] += 1
        refs[b] = dict(row)
        out.append(dict(blended))

    return out, {"rows": len(rows), "updates_buf0": updates[0], "updates_buf1": updates[1], "parity_disagreements": disagree}


def convert(src: str, dst: str, *, detect: bool, skip_sentinel: bool = True):
    with open(src, newline="") as fh:
        rdr = csv.DictReader(fh)
        fields = list(rdr.fieldnames or [])
        rows = list(rdr)
    if not rows:
        return {"rows": 0, "skipped": "empty"}
    out, stats = deinterleave(rows, fields, detect=detect, skip_sentinel=skip_sentinel)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(out)
    return stats


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="src")
    p.add_argument("--out", dest="dst")
    p.add_argument("--in-dir")
    p.add_argument("--out-dir")
    p.add_argument("--detect", action="store_true", help="assign each frame to a buffer by nearest reference instead of assuming strict alternation")
    p.add_argument("--keep-sentinel", action="store_true",
                   help=f"adopt {SENTINEL} as if it were a value, letting an "
                        f"un-received field overwrite good telemetry. Off by "
                        f"default; the sentinel is still WRITTEN for fields no "
                        f"buffer ever delivered.")
    p.add_argument("--schema-from", default="",
                   help="reference CSV whose header defines the schema; files "
                        "with a different header are skipped. Blend one "
                        "recording generation at a time.")
    p.add_argument("--pattern", default="csv_out_*.csv",
                   help="which files in --in-dir are double-buffered telemetry "
                        "(default csv_out_*.csv; plugin side-files must NOT be "
                        "converted)")
    p.add_argument("--resume", action="store_true", default=True,
                   help="skip files already present in --out-dir (default on)")
    p.add_argument("--no-resume", dest="resume", action="store_false")
    p.add_argument("--report", action="store_true", help="print per-column before/after for a few columns")
    p.add_argument("--report-cols", default="ADCS_GNC.svb,ADCS_GNC.wbn")
    p.add_argument("--report-rows", type=int, default=12)
    args = p.parse_args()

    if args.in_dir:
        if not args.out_dir:
            sys.exit("--in-dir requires --out-dir")
        # ⚠ Only `csv_out_*` is double-buffered TELEMETRY. data/onair/csv also
        # holds plugin side-files — attack_class_*, iforest_out_*, rule_gate_*,
        # incident_*, consistency_*, staleness_* — which are written per frame by
        # the plugins and have no two-buffer structure. De-interleaving those is
        # meaningless and corrupts them. Caught by the parity check: side-files
        # score 3-7 % disagreement against 0.0-0.1 % for real telemetry.
        files = sorted(glob.glob(os.path.join(args.in_dir, args.pattern)))
        os.makedirs(args.out_dir, exist_ok=True)

        # ⚠ One recording generation at a time. data/onair/csv holds 11 distinct
        # MID lists (250 … 479 columns); blending across them would produce an
        # output directory that loader's schema guard then has to re-split, and
        # any whole-directory load would outer-join them into fabricated zeros.
        if args.schema_from:
            with open(args.schema_from, newline="") as fh:
                ref = next(csv.reader(fh), [])
            keep = []
            off = 0
            for f in files:
                with open(f, newline="") as fh:
                    if next(csv.reader(fh), []) == ref:
                        keep.append(f)
                    else:
                        off += 1
            print(f"schema filter ({len(ref)} cols from "
                  f"{os.path.basename(args.schema_from)}): kept {len(keep)}, "
                  f"skipped {off} off-schema", flush=True)
            files = keep
        # Resumable: this machine reaps long jobs (AINOS3-100), and a 44 GB
        # conversion will be interrupted. An output file is only counted as done
        # once it is fully written, so a torn file is redone rather than kept.
        todo = []
        for f in files:
            dst = os.path.join(args.out_dir, os.path.basename(f))
            if args.resume and os.path.exists(dst) and os.path.getsize(dst) > 0:
                continue
            todo.append((f, dst))
        print(f"{len(files)} file(s) in {args.in_dir}; "
              f"{len(files) - len(todo)} already converted; {len(todo)} to do",
              flush=True)
        tot = rows = disagree = 0
        for n, (f, dst) in enumerate(todo, 1):
            tmp = dst + ".part"
            st = convert(f, tmp, detect=args.detect,
                         skip_sentinel=not args.keep_sentinel)
            os.replace(tmp, dst)            # atomic: no half-file looks done
            rows += st.get("rows", 0)
            disagree += st.get("parity_disagreements", 0)
            tot += 1
            if n % 25 == 0 or n == len(todo):
                print(f"  [{n}/{len(todo)}] {rows} rows, "
                      f"{disagree} parity disagreements", flush=True)
        print(f"done — {tot} files, {rows} rows, {disagree} parity disagreements")
        return

    if not (args.src and args.dst):
        sys.exit("need --in/--out or --in-dir/--out-dir")
    st = convert(args.src, args.dst, detect=args.detect, skip_sentinel=not args.keep_sentinel)
    print(f"{args.src} -> {args.dst}")
    print(f"  {st}")

    if args.report:
        orig = list(csv.DictReader(open(args.src)))
        new = list(csv.DictReader(open(args.dst)))
        for c in [x for x in args.report_cols.split(",") if x]:
            if c not in orig[0]:
                print(f"\n{c}: not in this file")
                continue
            print(f"\n--- {c}  (row : ORIGINAL -> BLENDED)")
            for i in range(min(args.report_rows, len(orig))):
                mark = "" if orig[i][c] == new[i][c] else "   <-- filled"
                print(f"  {i:>3} {orig[i][c][:46]:<48} -> {new[i][c][:46]}{mark}")


if __name__ == "__main__":
    main()
