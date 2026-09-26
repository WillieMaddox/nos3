#!/usr/bin/env python3
"""Split a corpus batch into chunk files for `run_corpus_chunks.py`.

⚠ TECHNIQUE-MAJOR by default: one chunk per attack, holding that attack's run
in EVERY mode. A chunk is therefore the smallest unit that answers "does this
technique behave the same in SUNSAFE, INERTIAL, BDOT and PASSIVE?", and the
collection produces complete, comparable cells from the first hour instead of
after the first mode block finishes.

That ordering is a direct response to how the two previous collections failed.
`AINOS3-45` cycled modes against the detector's blind window and the defect was
only visible once 83 % of the corpus was already collected; the 2026-09-10 run
was mode-major, so a per-mode problem could hide until that mode came up. With
one technique across all modes per chunk, a mode-specific defect shows up in
the first chunk that exercises it.

⚠ Each entry still does a full `make stop` + `make launch-quiet`, so grouping
by technique costs nothing extra — the mode is established fresh by
`single_mode_hold_<MODE>` every run either way.

    python3 make_chunks.py --batch <dir>/batch_pass1.json --out-dir <dir>/chunks
    python3 make_chunks.py --batch ... --out-dir ... --by mode --max-per-chunk 8
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import re


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def chunk(entries, by="technique", max_per_chunk=0):
    """→ [(filename, [entry, ...]), ...] in execution order."""
    if by == "technique-instance":
        # ⚠ The right grouping once there is more than one instance.
        # `technique` alone puts ALL instances of one attack in a single chunk
        # (20 runs, ~3.5 h), which both blows the AC5 <=8 discipline and undoes
        # the instance-major ordering: you would collect DE-0003.01 five times
        # before ever seeing DE-0003.02, so a defect appearing at instance 3
        # stays hidden behind one technique. Grouping by (technique, instance)
        # keeps the pass-1 shape — one attack across all four modes, 4 runs —
        # and emits instance 1 of every technique before instance 2.
        order, groups = [], {}
        for e in entries:
            k = (e["_rep"], e["_technique"])
            if k not in groups:
                groups[k] = []
                order.append(k)
            groups[k].append(e)
        order.sort(key=lambda k: (k[0], [e["_technique"] for e in entries].index(k[1])))
        keyed = [(k, groups[k]) for k in order]
        label = lambda k, g: f"{_slug(k[1])}_i{k[0]}"      # noqa: E731
    elif by == "technique":
        # Stable technique order as it first appears in the batch, each with
        # its modes in the batch's own order.
        order, groups = [], {}
        for e in entries:
            t = e["_technique"]
            if t not in groups:
                groups[t] = []
                order.append(t)
            groups[t].append(e)
        keyed = [(t, groups[t]) for t in order]
        label = lambda t, g: _slug(t)                       # noqa: E731
    elif by == "mode":
        keyed = [(m, list(g)) for m, g in
                 itertools.groupby(entries, key=lambda e: e["_mode"])]
        label = lambda m, g: m.lower()                      # noqa: E731
    else:
        raise SystemExit(f"unknown --by {by!r}")

    out, n = [], 0
    for key, grp in keyed:
        # ⚠ A chunk never straddles its grouping key, so a pause or a re-run
        # always lands on a clean boundary.
        step = max_per_chunk or len(grp)
        for i in range(0, len(grp), step):
            n += 1
            out.append((f"chunk_{n:02d}_{label(key, grp)}.json", grp[i:i + step]))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--batch", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--by", default="technique-instance",
                   choices=("technique-instance", "technique", "mode"),
                   help="technique-instance (default): one chunk per attack per "
                        "instance, 4 runs, emitted instance-major. `technique` "
                        "collapses all instances into one chunk — only correct "
                        "for a single-instance collection.")
    p.add_argument("--max-per-chunk", type=int, default=0,
                   help="cap runs per chunk (0 = one chunk per group). The "
                        "AC5 discipline of <= 8 runs applies to mode-major "
                        "chunks; a technique chunk is 4 runs by construction.")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    entries = json.load(open(args.batch))
    chunks = chunk(entries, by=args.by, max_per_chunk=args.max_per_chunk)

    total = sum(len(g) for _, g in chunks)
    if total != len(entries):
        raise SystemExit(f"chunking lost entries: {total} != {len(entries)}")

    if not args.dry_run:
        os.makedirs(args.out_dir, exist_ok=True)
        for name, grp in chunks:
            with open(os.path.join(args.out_dir, name), "w") as fh:
                json.dump(grp, fh, indent=2)

    print(f"{len(chunks)} chunks, {total} runs, grouped by {args.by}"
          + ("  (dry run)" if args.dry_run else f" -> {args.out_dir}"))
    for name, grp in chunks[:6]:
        modes = ",".join(dict.fromkeys(e["_mode"] for e in grp))
        print(f"  {name:<34} {len(grp)} runs  [{modes}]")
    if len(chunks) > 6:
        print(f"  ... and {len(chunks) - 6} more")


if __name__ == "__main__":
    main()
