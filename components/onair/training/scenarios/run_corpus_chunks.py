#!/usr/bin/env python3
"""Drive the AINOS3-100 chunk files in order, resumably.

⚠ AC5 discipline: each chunk is <= 8 runs, `run_attack_batch.py` does a full
`make stop` + `make launch-quiet` between every run, and nothing here uses
`nohup &` — the driver stays a tracked foreground child so a hang is visible
rather than silently detached.

Resumable by design: a chunk whose results file already exists is SKIPPED, so
re-invoking after an interruption continues where it stopped instead of
recollecting. Delete a chunk's results file to force it to re-run.

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
        if os.path.exists(out):
            log(f"SKIP {name} (results exist)")
            continue
        if args.max_chunks is not None and ran >= args.max_chunks:
            log(f"stopping: --max-chunks {args.max_chunks} reached")
            break
        n = len(json.load(open(c)))
        log(f"=== {name}: {n} runs ===")
        logf = os.path.join(resdir, f"{name}.log")
        with open(logf, "wb") as fh:
            rc = subprocess.run(
                [sys.executable, "-u", BATCH, "--input", c, "--out", out],
                cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).returncode
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
