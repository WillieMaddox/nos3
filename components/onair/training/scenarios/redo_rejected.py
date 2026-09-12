#!/usr/bin/env python3
"""Strip gate-REJECTED runs from chunk results so the driver re-collects them.

WHY (AINOS3-100): run_corpus_chunks treats "a result row exists" as done, which
is right for a crash-resume but wrong for a run that COMPLETED and then failed
the corpus manifest's quality gate. INERTIAL capture is stochastic — the tumble
state at mode entry decides whether the boresight sweeps out of the Earth cone in
time — so a rejected run is worth simply retrying, and without this it never is.

⚠ Only removes runs the manifest actually rejected, and never one already
superseded by a later successful collection of the same cell. Retry is the ONLY
remedy applied here: the 90 % capture threshold is not negotiable and is not
touched, because lowering a bar to fit a result is how this project got a
`ROBUST` tier that its own data never supported.

    python3 redo_rejected.py --base data/onair/corpus/<name> [--mode INERTIAL]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--mode", default=None, help="limit to one ADCS mode")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    man = os.path.join(args.base, "corpus_manifest.json")
    if not os.path.exists(man):
        raise SystemExit(f"no corpus manifest at {man} — build it first")
    with open(man) as fh:
        m = json.load(fh)

    drop = {(r["technique"], r["mode"], r["instance"])
            for r in m.get("rejected_runs", [])
            if not r.get("superseded_by_successful_run")
            and (args.mode is None or r["mode"] == args.mode)}
    if not drop:
        print("nothing to redo")
        return 0
    print(f"{len(drop)} rejected run(s) to re-collect:")
    for k in sorted(drop):
        print(f"    {k[0]}/{k[1]}/inst{k[2]}")

    removed = 0
    for f in sorted(glob.glob(os.path.join(args.base, "results", "*_results.json"))):
        if "remainder" in f or "_all_" in f:
            continue
        with open(f) as fh:
            rows = json.load(fh)
        keep = [r for r in rows
                if (r.get("_technique"), r.get("_mode"), r.get("_rep")) not in drop]
        if len(keep) != len(rows):
            removed += len(rows) - len(keep)
            if not args.dry_run:
                with open(f, "w") as fh:
                    json.dump(keep, fh, indent=2)
            print(f"  {os.path.basename(f)}: {len(rows)} -> {len(keep)}")
    print(f"\n{'would remove' if args.dry_run else 'removed'} {removed} row(s); "
          f"re-run the driver to collect them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
