#!/usr/bin/env python3
"""Concatenate per-chunk collection results into one batch-results file.

`build_corpus_manifest.py --batch-results` takes a SINGLE file, but
`run_corpus_chunks.py` writes one per chunk. This joins them.

⚠ Excludes `*_remainder_results.json`. A resumed chunk's missing runs are
written there and merged into the main file, but the remainder is only deleted
the NEXT time that chunk is processed — so a completed resume leaves it on
disk. Globbing `*_results.json` then counts those runs TWICE. Observed
2026-09-22: 77 runs for a 76-run collection, with EX-0014.03/SUNSAFE duplicated.

⚠ Also refuses to emit a duplicate `(technique, mode, rep)` cell. A corpus must
not contain the same cell twice — re-chunking after a partial run, or a
hand-edited results file, can produce one, and `build_corpus_manifest.py` would
inherit it.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def merge(base: str):
    files = sorted(f for f in glob.glob(os.path.join(base, "results", "*_results.json"))
                   if not f.endswith("_remainder_results.json"))
    rows, seen, dupes = [], {}, []
    for f in files:
        for r in json.load(open(f)):
            key = (r.get("_technique"), r.get("_mode"), r.get("_rep"))
            if key in seen:
                dupes.append((key, os.path.basename(seen[key]), os.path.basename(f)))
                continue
            seen[key] = f
            rows.append(r)
    return files, rows, dupes


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", required=True)
    p.add_argument("--out", default=None, help="default: <base>/_all_results.json")
    a = p.parse_args()
    base = a.base if os.path.isabs(a.base) else os.path.join(ROOT, a.base)
    out = a.out or os.path.join(base, "_all_results.json")

    files, rows, dupes = merge(base)
    print(f"{len(files)} chunk result file(s) -> {len(rows)} runs")
    skipped = sorted(os.path.basename(f) for f in
                     glob.glob(os.path.join(base, "results", "*_remainder_results.json")))
    if skipped:
        print(f"⚠ skipped {len(skipped)} remainder file(s): {skipped}")
    if dupes:
        print(f"⚠ REFUSED {len(dupes)} duplicate cell(s):")
        for key, first, second in dupes:
            print(f"     {key} in both {first} and {second}")
    by = collections.Counter(r["_mode"] for r in rows)
    print(f"by mode: {dict(by)}  | techniques: {len({r['_technique'] for r in rows})}")
    bad = [r for r in rows if r.get("exit_code") != 0]
    if bad:
        print(f"⚠ {len(bad)} run(s) with nonzero exit: "
              + ", ".join(f"{r['_technique']}/{r['_mode']}" for r in bad))
    with open(out, "w") as fh:
        json.dump(rows, fh, indent=2)
    print(f"wrote {out}")
    return 1 if dupes else 0


if __name__ == "__main__":
    sys.exit(main())
