#!/usr/bin/env python3
"""Per-column unique-value counts across one or more blended csv_out files.

For each input CSV, count the number of DISTINCT values in every column,
ignoring the missing-data placeholder "[0]" (and empty cells). Emit one row
per input file into an output CSV whose columns are:

    file, technique, mode, <schema columns...>, rows, real_seconds, sim_seconds

`technique`/`mode` come from the corpus run record whose raw csv pairs with the
blended csv (nearest timestamp, same pid) — supply the record source(s) with
--map (a results json, a corpus_manifest.json, or a directory holding them).

A column that is entirely "[0]"/empty in a file scores 0. Columns whose count
is 1 in EVERY processed file (constant everywhere) are dropped from the output
and their names written to a sidecar JSON with the same stem as --out.

Usage:
    python3 column_cardinality.py --dir data/onair/csv_blended \
        --map data/onair/corpus/rebuild_2026-09-21 --out card.csv
    python3 column_cardinality.py a.csv b.csv --out card.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys

try:
    from tqdm import tqdm
except ImportError:                                  # graceful no-op fallback
    def tqdm(it, **_):
        return it

MISSING = {"[0]", ""}
RECV_COL = "OnAIR.FrameRecvUTC"
SIM_COL = "OnAIR.SimTimeUTC"
_TS = re.compile(r"csv_out_(\d{4}-\d{2}-\d{2}T[\d-]+)_pid(\d+)\.csv$")


# Run-record fields surfaced into the output, in order, mapped from the
# _all_results.json record ("add the contents of _all_results.json").
RECORD_FIELDS = ["technique", "mode", "instance", "level", "pre_seconds",
                 "post_seconds", "exit_code", "wallclock_s", "during", "chain",
                 "attack_key", "manifest"]


def _ts(basename: str):
    """(datetime, pid) parsed from a csv_out_<ts>_pid<N>.csv name, or None."""
    m = _TS.search(basename)
    if not m:
        return None
    return dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H-%M-%S-%f"), m.group(2)


def _span_seconds(first, last):
    """(last - first) seconds from two ISO timestamps; "" if unparseable."""
    try:
        return round((dt.datetime.fromisoformat(last)
                      - dt.datetime.fromisoformat(first)).total_seconds(), 3)
    except (ValueError, TypeError):
        return ""


def _normalize(r: dict) -> dict:
    """A run record -> the RECORD_FIELDS surfaced in the output."""
    return {
        "technique": r.get("_technique") or r.get("technique") or "",
        "mode": r.get("_mode") or r.get("mode") or "",
        "instance": r.get("_rep") if r.get("_rep") is not None else r.get("instance", ""),
        "level": r.get("level", ""),
        "pre_seconds": r.get("pre_seconds", ""),
        "post_seconds": r.get("post_seconds", ""),
        "exit_code": r.get("exit_code", ""),
        "wallclock_s": r.get("wallclock_s", ""),
        "during": r.get("during", ""),
        "chain": r.get("chain", ""),
        "attack_key": r.get("key", ""),
        "manifest": r.get("manifest", ""),
    }


def build_record_index(results_paths):
    """(timestamp-to-the-second, pid) -> normalized record.

    The blended csv and the raw csv named in each _all_results.json record share
    their timestamp to the SECOND and their pid (they are opened microseconds
    apart at run start), so this is a deterministic join — no nearest-timestamp
    tolerance. `results_paths` may be _all_results.json files or directories
    (a directory is searched recursively for _all_results.json).
    """
    files = []
    for p in results_paths:
        if os.path.isdir(p):
            files += glob.glob(os.path.join(p, "**", "_all_results.json"), recursive=True)
        else:
            files.append(p)
    index: dict[tuple, dict] = {}
    for f in files:
        try:
            data = json.load(open(f))
        except (OSError, json.JSONDecodeError):
            continue
        records = data.get("runs", data) if isinstance(data, dict) else data
        for r in records or []:
            if not isinstance(r, dict) or not r.get("csv"):
                continue
            parsed = _ts(os.path.basename(r["csv"]))
            if parsed:
                index[(parsed[0].replace(microsecond=0), parsed[1])] = _normalize(r)
    return index


def lookup(basename: str, index) -> dict:
    """The record for a blended csv, joined on (second, pid); {} if none.

    Exact on the truncated second; falls back to +/-1s on the same pid to cover
    a rare second-boundary crossing between the raw and blended open times.
    """
    parsed = _ts(basename)
    if not parsed:
        return {}
    t, pid = parsed
    sec = t.replace(microsecond=0)
    for cand in (sec, sec - dt.timedelta(seconds=1), sec + dt.timedelta(seconds=1)):
        rec = index.get((cand, pid))
        if rec:
            return rec
    return {}


def count_unique(path: str):
    """(header, {column: n_unique}, n_rows, extras) for one CSV, streamed."""
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        header = rd.fieldnames or []
        seen: dict[str, set] = {c: set() for c in header}
        n = 0
        recv0 = recvN = sim0 = simN = None
        for row in rd:
            n += 1
            rv, sv = row.get(RECV_COL), row.get(SIM_COL)
            if rv not in MISSING:
                recv0 = recv0 if recv0 is not None else rv
                recvN = rv
            if sv not in MISSING:
                sim0 = sim0 if sim0 is not None else sv
                simN = sv
            for c in header:
                if row.get(c) not in MISSING:
                    seen[c].add(row.get(c))
    extras = {"real_seconds": _span_seconds(recv0, recvN),
              "sim_seconds": _span_seconds(sim0, simN)}
    return header, {c: len(seen[c]) for c in header}, n, extras


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csvs", nargs="*", help="one or more csv_out blended CSVs")
    p.add_argument("--dir", default=None,
                   help="process every csv_out_*.csv in this directory")
    p.add_argument("--results", nargs="*", default=[],
                   help="_all_results.json file(s) or directory(ies) holding them; "
                        "the run record (technique, mode, level, instance, "
                        "windows, exit_code, wallclock, manifest, ...) is joined "
                        "in on (timestamp-to-the-second, pid)")
    p.add_argument("--out", required=True, help="output CSV (one row per input)")
    a = p.parse_args()

    paths = list(a.csvs)
    if a.dir:
        paths += sorted(glob.glob(os.path.join(a.dir, "csv_out_*.csv")))
    if not paths:
        raise SystemExit("no inputs: pass files, or --dir with csv_out_*.csv in it")

    index = build_record_index(a.results) if a.results else {}
    if a.results and not index:
        print("⚠ --results produced no records; run fields will be blank",
              file=sys.stderr)

    canonical: list[str] | None = None
    rows: list[dict] = []
    unmapped = 0
    for path in tqdm(paths, desc="csv", unit="file"):
        if not os.path.exists(path):
            print(f"⚠ skipping missing file: {path}", file=sys.stderr)
            continue
        header, counts, n, extras = count_unique(path)
        if canonical is None:
            canonical = header
        elif header != canonical:
            print(f"⚠ header mismatch in {os.path.basename(path)} "
                  f"(aligned to first file's header)", file=sys.stderr)
        rec_fields = lookup(os.path.basename(path), index)
        if index and not rec_fields:
            unmapped += 1
        rec = {"file": os.path.basename(path),
               **{k: rec_fields.get(k, "") for k in RECORD_FIELDS},
               "rows": n, **counts, **extras}
        rows.append(rec)

    if not rows:
        raise SystemExit("no readable input files")
    if unmapped:
        print(f"⚠ {unmapped}/{len(rows)} file(s) had no record match "
              f"in --results (fields left blank)", file=sys.stderr)

    schema = canonical or []
    # Drop schema columns whose count is 1 in EVERY row (constant everywhere).
    dropped = [c for c in schema if all(r.get(c) == 1 for r in rows)]
    kept = [c for c in schema if c not in set(dropped)]

    out_cols = ["file"] + RECORD_FIELDS + kept + ["rows", "real_seconds", "sim_seconds"]
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out_cols, extrasaction="ignore")
        w.writeheader()
        for rec in rows:
            w.writerow(rec)

    sidecar = os.path.splitext(a.out)[0] + ".json"
    json.dump({"dropped_all_ones": dropped, "count": len(dropped)},
              open(sidecar, "w"), indent=2)
    print(f"wrote {a.out}: {len(rows)} row(s) x {len(out_cols)} cols "
          f"({len(dropped)} constant columns dropped -> {sidecar})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
