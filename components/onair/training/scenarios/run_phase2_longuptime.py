"""Phase 2 long-uptime baseline orchestrator.

Drives the FSW through a fresh launch + 4 baseline samples at FSW uptime
T+30min, T+2h, T+4h, T+6h (matches the v3 multi-uptime corpus methodology;
see project_iforest_v3_multiuptime). No Tier 1.5 resets — FSW uptime grows
monotonically across the ~6.5 hour run so the corpus captures genuine
long-uptime state (clock drift, heap fragmentation, table churn) rather
than 4 repetitions of T+0.

Expects COSMOS to already be up. After Phase 1 it stays attached to
nos3-sc01 across `make stop` + `make launch-quiet`, so no explicit
`openc3.sh start` / `make start-gsw` is needed. From a cold start:
    cd ~/.nos3/cosmos && ./openc3.sh start    # bring up COSMOS
    make start-gsw                            # connect to sc01 net
    python3 components/onair/training/scenarios/run_phase2_longuptime.py

Once Phase 1 has finished, just launch this script — it handles `make stop`
+ `make launch-quiet` itself.

Usage:
    python3 components/onair/training/scenarios/run_phase2_longuptime.py
    python3 ... --sample-mins 30 120 240 360     # default v3 schedule
    python3 ... --sample-mins 5 15 25 35         # smoke test (no real uptime)
    python3 ... --no-restart                     # FSW already freshly launched

The script writes one baseline manifest per sample to
data/onair/scenarios/manifest_<ts>.json, and tags each subprocess log
under /tmp/phase2_*.log so a mid-run failure can be diagnosed without
losing the earlier samples.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
RUN_BASELINE = REPO_ROOT / "components/onair/training/scenarios/run_baseline.py"
CSV_DIR = REPO_ROOT / "data/onair/csv"
MANIFEST_DIR = REPO_ROOT / "data/onair/scenarios"

# v3 multi-uptime sample plan. The label "T+Xmin" is the wall time when
# the corresponding run_baseline.py invocation STARTS, measured from
# FSW launch. Each run is ~25 min (5 v3 scenarios × 5 min), so finishes
# at T+(X+25)min.
DEFAULT_SAMPLE_MINS = [30, 120, 240, 360]

# Strict v3 scenario set — no mode_dwell (that was v4).
SCENARIOS = ["quiescent", "nominal_ops", "maneuvers", "comm_passes", "mode_transitions"]


def log(msg: str) -> None:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def fsw_running() -> bool:
    """Both sc01-nos-fsw and sc01-onair are docker-status `running`."""
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
    """Wait until a csv_out_*.csv not in `pre` appears. Signals OnAIR has
    re-peered with SBN and started logging."""
    deadline = time.time() + deadline_s
    while time.time() < deadline:
        cur = set(CSV_DIR.glob("csv_out_*.csv"))
        new = cur - pre
        if new:
            return next(iter(new))
        time.sleep(2)
    raise RuntimeError(f"No fresh CSV in {CSV_DIR} within {deadline_s}s")


def fresh_launch() -> None:
    """Tear down Phase 1's containers and bring up a fresh FSW.

    COSMOS is not touched — it stays attached to nos3-sc01 across the
    `make stop` and is re-aliased by launch_sat_quiet.sh idempotently.
    """
    log("`make stop` (clear Phase 1 containers)")
    subprocess.run(["make", "stop"], check=True, cwd=str(REPO_ROOT),
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    pre_csvs = set(CSV_DIR.glob("csv_out_*.csv"))
    launch_log = open("/tmp/phase2_launch_quiet.log", "wb")
    log("`make launch-quiet` (background; log: /tmp/phase2_launch_quiet.log)")
    subprocess.Popen(["make", "launch-quiet"], cwd=str(REPO_ROOT),
                     stdout=launch_log, stderr=subprocess.STDOUT,
                     start_new_session=True)

    log("waiting for sc01-nos-fsw + sc01-onair to be `running`…")
    wait_for_fsw()
    log("waiting for fresh OnAIR CSV…")
    new_csv = wait_for_fresh_csv(pre_csvs)
    log(f"fresh CSV: {new_csv.name}")


def run_sample(idx: int, target_min: int, total: int) -> int:
    """Invoke run_baseline.py for one sample. Returns the subprocess exit code."""
    sample_log = Path(f"/tmp/phase2_sample{idx:02d}_T+{target_min}min.log")
    log(f"sample {idx}/{total}: run_baseline.py → {sample_log}")
    with sample_log.open("wb") as f:
        ret = subprocess.run(
            ["python3", "-u", str(RUN_BASELINE),
             "--auto-discover", "--only", *SCENARIOS],
            cwd=str(REPO_ROOT), stdout=f, stderr=subprocess.STDOUT,
        )
    return ret.returncode


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--sample-mins", type=int, nargs="+", default=DEFAULT_SAMPLE_MINS,
                   help=("Run-start uptime in minutes for each sample "
                         "(default: %(default)s = T+30min, T+2h, T+4h, T+6h)."))
    p.add_argument("--no-restart", action="store_true",
                   help=("Skip `make stop` + `make launch-quiet`. Use only "
                         "when the FSW is already freshly launched (e.g. "
                         "recovering from a mid-script abort)."))
    args = p.parse_args()

    pre_manifests = set(MANIFEST_DIR.glob("manifest_*.json"))

    if args.no_restart:
        if not fsw_running():
            log("FATAL: --no-restart but FSW + OnAIR are not running")
            sys.exit(1)
        log("--no-restart: using existing FSW; T=0 is the current wall clock "
            "(not the actual FSW boot time)")
    else:
        fresh_launch()

    t0 = time.monotonic()
    launch_utc = dt.datetime.now(dt.timezone.utc)
    log(f"FSW T=0 at {launch_utc.isoformat()}")
    log(f"sample plan (uptime minutes): {args.sample_mins}")
    total = len(args.sample_mins)

    last_min = -1
    for target_min in args.sample_mins:
        if target_min <= last_min:
            log(f"FATAL: --sample-mins must be strictly increasing; "
                f"saw {target_min} after {last_min}")
            sys.exit(2)
        last_min = target_min

    for i, target_min in enumerate(args.sample_mins, 1):
        target_s = target_min * 60
        elapsed = time.monotonic() - t0
        wait_s = target_s - elapsed
        if wait_s > 0:
            log(f"sample {i}/{total} (T+{target_min}min): "
                f"sleeping {wait_s/60:.1f}min")
            time.sleep(wait_s)
        else:
            log(f"sample {i}/{total} (T+{target_min}min): already past target by "
                f"{-wait_s/60:.1f}min — starting now")
        if not fsw_running():
            log(f"FATAL: FSW down before sample {i} — aborting")
            sys.exit(1)
        rc = run_sample(i, target_min, total)
        if rc != 0:
            log(f"sample {i} FAILED (exit {rc}); aborting remaining samples")
            sys.exit(rc)
        log(f"sample {i}/{total} done (uptime now "
            f"{(time.monotonic()-t0)/60:.1f}min)")

    new_manifests = sorted(set(MANIFEST_DIR.glob("manifest_*.json")) - pre_manifests)
    log(f"Phase 2 complete. {len(new_manifests)} new manifest(s):")
    for m in new_manifests:
        log(f"    {m}")


if __name__ == "__main__":
    main()
