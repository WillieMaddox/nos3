#!/usr/bin/env python3
"""Drive the AINOS3-100 chunk files in order, resumably.

⚠ AC5 discipline: each chunk is <= 8 runs, `run_attack_batch.py` does a full
`make stop` + `make launch-quiet` between every run, and nothing here uses
`nohup &` — the driver stays a tracked foreground child so a hang is visible
rather than silently detached.

Resumable by design: a chunk is SKIPPED only when its results file is COMPLETE —
one entry per run in the chunk. Delete a chunk's results file to force a re-run.

⚠ Completeness, not mere existence. `run_attack_batch.py` saves results
incrementally after every run so an abort preserves prior work, which means a
killed chunk leaves a SHORT results file behind. Treating that as "done" would
silently drop the uncollected runs — the same fail-quietly shape as the level and
chain defects. A partial chunk is instead re-run for its MISSING entries only.

    python3 run_corpus_chunks.py --base data/onair/corpus/rebuild_2026-09-10
    python3 run_corpus_chunks.py --base <dir> --only sunsafe --max-chunks 3
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
BATCH = os.path.join(HERE, "run_attack_batch.py")


def log(msg):
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%SZ}] {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--only", default=None, help="substring filter, e.g. 'sunsafe'")
    ap.add_argument("--max-chunks", type=int, default=None)
    args = ap.parse_args()

    base = args.base if os.path.isabs(args.base) else os.path.join(ROOT, args.base)
    chunks = sorted(glob.glob(os.path.join(base, "chunks", "chunk_*.json")))
    if args.only:
        chunks = [c for c in chunks if args.only in os.path.basename(c)]
    if not chunks:
        raise SystemExit(f"no chunks under {base}/chunks")
    resdir = os.path.join(base, "results")
    os.makedirs(resdir, exist_ok=True)

    ran = 0
    for c in chunks:
        name = os.path.splitext(os.path.basename(c))[0]
        out = os.path.join(resdir, f"{name}_results.json")
        entries = json.load(open(c))

        # ⚠ Fold any stranded remainder results back in FIRST.
        #
        # A resumed chunk runs its missing entries into <name>_remainder_results.json
        # and merges at chunk end. If the driver is killed mid-chunk — which the
        # low-memory guard does — those completed runs sit unmerged, and a resume
        # that reads only the main file re-runs them: ~10 minutes of stack time
        # each, and a duplicate cell if the merge later picks up both. Observed
        # for real on 2026-09-10 (EX-0008.02 and EX-0012.07 stranded). Merging
        # here makes a kill cost at most the single in-flight run.
        part = os.path.join(resdir, f"{name}_remainder_results.json")
        if os.path.exists(part):
            base = json.load(open(out)) if os.path.exists(out) else []
            have = {(r.get("_technique"), r.get("_mode"), r.get("_rep")) for r in base}
            try:
                extra = [r for r in json.load(open(part)) if (r.get("_technique"), r.get("_mode"), r.get("_rep")) not in have]
            except json.JSONDecodeError:
                extra = []
            if extra:
                with open(out, "w") as fh:
                    json.dump(base + extra, fh, indent=2)
                log(f"recovered {len(extra)} stranded run(s) into {os.path.basename(out)}")
            os.remove(part)

        done_keys, done_rows = set(), []
        if os.path.exists(out):
            try:
                done_rows = json.load(open(out))
            except json.JSONDecodeError:
                log(f"⚠ {name}: results file is corrupt — re-running the whole chunk")
                done_rows = []
            done_keys = {(r.get("_technique"), r.get("_mode"), r.get("_rep")) for r in done_rows}
        todo = [e for e in entries if (e.get("_technique"), e.get("_mode"), e.get("_rep")) not in done_keys]
        if not todo:
            log(f"SKIP {name} (complete: {len(done_rows)}/{len(entries)})")
            continue
        if done_rows:
            log(f"RESUME {name}: {len(done_rows)}/{len(entries)} already collected, {len(todo)} to go")
            # Run only the remainder, into a part file, then merge.
            c = os.path.join(resdir, f"{name}_remainder.json")
            with open(c, "w") as fh:
                json.dump(todo, fh, indent=1)
            out_part = os.path.join(resdir, f"{name}_remainder_results.json")
        else:
            out_part = out
        if args.max_chunks is not None and ran >= args.max_chunks:
            log(f"stopping: --max-chunks {args.max_chunks} reached")
            break
        log(f"=== {name}: {len(todo)} run(s) ===")
        logf = os.path.join(resdir, f"{name}.log")
        with open(logf, "ab") as fh:
            rc = subprocess.run([sys.executable, "-u", BATCH, "--input", c, "--out", out_part], cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).returncode
        if out_part != out:
            merged = done_rows + (json.load(open(out_part)) if os.path.exists(out_part) else [])
            with open(out, "w") as fh:
                json.dump(merged, fh, indent=2)
            log(f"  merged remainder into {os.path.basename(out)} ({len(merged)}/{len(entries)})")
        ok = 0
        if os.path.exists(out):
            rows = json.load(open(out))
            ok = sum(1 for r in rows if r.get("exit_code") == 0)
            log(f"  {name}: {ok}/{len(rows)} succeeded (driver rc={rc}) -> {out}")
        else:
            log(f"  ⚠ {name}: no results file written (rc={rc}); see {logf}")
        ran += 1
    log(f"driver done: ran {ran} chunk(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
