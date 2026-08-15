"""Batch-run a list of SPARTA attacks with full stack restart between each.

Designed for the 2026-05-16 mode-balanced re-collection: same 32 attack
list as 2026-05-15 session-3, but each attack now goes through
run_attack.py with `--during all_modes_dwell --pre-seconds 240`. The
extra 6 min per attack (vs the v3 30s+180s windows) is required so the
corruption window spans all 4 ADCS modes, fixing the
project_attack_validation_cosmos_2026-05-15 routing audit's 99.9%
SUNSAFE finding.

Expects COSMOS to already be up. If it isn't:
    cd ~/.nos3/cosmos && ./openc3.sh start
    make start-gsw          # opens Firefox; script does not need this every run
    python3 components/onair/training/scenarios/run_attack_batch.py

Input JSON schema (one entry per attack):
    [
      {"key": "ex_0001_01_command_packets", "level": 2, "chain": false},
      {"key": "ex_0008_01_absolute_time_sequences", "level": 3, "chain": true},
      ...
    ]

Default input is the session-3 list at /tmp/batch_validate_all32_results.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
RUN_ATTACK = REPO_ROOT / "components/onair/training/scenarios/run_attack.py"
CSV_DIR = REPO_ROOT / "data/onair/csv"
MANIFEST_DIR = REPO_ROOT / "data/onair/scenarios"
DEFAULT_INPUT = Path("/tmp/batch_validate_all32_results.json")


def log(msg: str) -> None:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def fsw_running() -> bool:
    for name in ("sc01-nos-fsw", "sc01-onair"):
        r = subprocess.run(
            ["docker", "inspect", name, "--format", "{{.State.Status}}"],
            capture_output=True, text=True,
        )
        if r.returncode != 0 or r.stdout.strip() != "running":
            return False
    return True


def wait_for_fsw(deadline_s: int = 180) -> None:
    deadline = time.time() + deadline_s
    while time.time() < deadline:
        if fsw_running():
            return
        time.sleep(3)
    raise RuntimeError(f"FSW + OnAIR did not reach 'running' within {deadline_s}s")


def wait_for_fresh_csv(pre: set[Path], deadline_s: int = 120) -> Path:
    deadline = time.time() + deadline_s
    while time.time() < deadline:
        cur = set(CSV_DIR.glob("csv_out_*.csv"))
        new = cur - pre
        if new:
            return next(iter(new))
        time.sleep(2)
    raise RuntimeError(f"No fresh CSV in {CSV_DIR} within {deadline_s}s")


def stack_restart() -> Path:
    """make stop + make launch-quiet, wait for FSW + fresh CSV."""
    subprocess.run(["make", "stop"], check=True, cwd=str(REPO_ROOT),
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    pre_csvs = set(CSV_DIR.glob("csv_out_*.csv"))
    launch_log = open(f"/tmp/batch_attacks_launch.log", "wb")
    subprocess.Popen(["make", "launch-quiet"], cwd=str(REPO_ROOT),
                     stdout=launch_log, stderr=subprocess.STDOUT,
                     start_new_session=True)
    wait_for_fsw()
    return wait_for_fresh_csv(pre_csvs)


def run_one(entry: dict, idx: int, total: int) -> dict:
    key = entry["key"]
    level = int(entry["level"])
    chain = bool(entry.get("chain", False))
    sample_log = Path(f"/tmp/batch_attack_{idx:02d}_{key}.log")
    log(f"attack {idx}/{total}: {key} (level={level}, chain={chain}"
        f"{', during=' + str(entry['during']) if entry.get('during') else ''}) → {sample_log}")

    pre_manifests = set(MANIFEST_DIR.glob("manifest_*.json"))

    args = [
        "python3", "-u", str(RUN_ATTACK),
        "--auto-discover",
        "--attack", key,
        "--attack-level", str(level),
    ]
    # Optional per-entry overrides. `during` selects the bracketing scenario —
    # use single_mode_hold_<MODE> to keep one ADCS mode for the whole run, so
    # frames land OUTSIDE the detector's 250-frame post-mode-switch blind
    # window. With the default all_modes_dwell (60 s per mode) that window
    # swallows 83 % of attack frames, which is why per-mode detection has never
    # been measurable under deployed conditions.
    if entry.get("during"):
        args += ["--during", str(entry["during"])]
    if entry.get("pre_seconds"):
        args += ["--pre-seconds", str(entry["pre_seconds"])]
    if entry.get("post_seconds"):
        args += ["--post-seconds", str(entry["post_seconds"])]
    if chain:
        args.append("--chain")

    t0 = time.time()
    with sample_log.open("wb") as f:
        ret = subprocess.run(args, cwd=str(REPO_ROOT), stdout=f, stderr=subprocess.STDOUT)
    wallclock = time.time() - t0
    new_manifests = sorted(set(MANIFEST_DIR.glob("manifest_*.json")) - pre_manifests)
    manifest = new_manifests[-1].name if new_manifests else None
    return {
        "key": key,
        "level": level,
        "chain": chain,
        "during": entry.get("during"),
        "pre_seconds": entry.get("pre_seconds"),
        "post_seconds": entry.get("post_seconds"),
        "exit_code": ret.returncode,
        "wallclock_s": round(wallclock, 1),
        "manifest": manifest,
    }


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                   help=("JSON list of {key, level, chain} entries. Default: "
                         "/tmp/batch_validate_all32_results.json (the 2026-05-15 "
                         "session-3 list)."))
    p.add_argument("--out", type=Path,
                   default=Path("/tmp/batch_attack_modes_results.json"),
                   help="Output JSON path. Default /tmp/batch_attack_modes_results.json")
    p.add_argument("--start-at", type=int, default=1,
                   help="1-indexed entry to start at (resume after a failure).")
    p.add_argument("--stop-after", type=int, default=None,
                   help="Stop after this many entries (smoke test).")
    args = p.parse_args()

    with args.input.open() as f:
        entries = json.load(f)
    if args.stop_after:
        entries = entries[: args.stop_after]
    total = len(entries)
    log(f"loaded {total} attack entries from {args.input}")

    results: list[dict] = []
    if args.out.exists():
        # Resume support: keep prior entries up to start_at-1
        try:
            with args.out.open() as f:
                prior = json.load(f)
            if args.start_at > 1 and len(prior) >= args.start_at - 1:
                results = prior[: args.start_at - 1]
                log(f"resuming from entry {args.start_at}; kept {len(results)} prior results")
        except (OSError, json.JSONDecodeError):
            pass

    for i, entry in enumerate(entries, 1):
        if i < args.start_at:
            continue
        log(f"=== {i}/{total} {entry['key']} ===")
        log("make stop + make launch-quiet")
        try:
            csv = stack_restart()
        except RuntimeError as e:
            log(f"FATAL: stack restart failed: {e}")
            sys.exit(1)
        log(f"fresh CSV: {csv.name}")
        result = run_one(entry, i, total)
        results.append(result)
        # Save incrementally so a mid-run abort preserves prior results.
        with args.out.open("w") as f:
            json.dump(results, f, indent=2)
        log(f"  exit={result['exit_code']} wallclock={result['wallclock_s']}s "
            f"manifest={result['manifest']}")

    n_ok = sum(1 for r in results if r["exit_code"] == 0)
    log(f"DONE: {n_ok}/{len(results)} succeeded. Results → {args.out}")


if __name__ == "__main__":
    main()
