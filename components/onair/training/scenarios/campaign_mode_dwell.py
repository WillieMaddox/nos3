"""Run a v4 multi-uptime mode_dwell campaign.

Brings the stack down with `make stop`, relaunches with `make launch-quiet`,
then runs four 15-minute mode_dwell baselines at the same uptime offsets the
v3 multi-uptime corpus used: T+30 min, T+2 h, T+4 h, T+6 h.

Single foreground process — kick off, walk away, check the log on return.
Each baseline shells out to `run_baseline.py --auto-discover --only mode_dwell`
so the existing manifest-writing path is reused exactly. The orchestrator
sleeps between baselines; the stack ages idle in between.

Total wall-clock: ~6 h 15 min.

Usage:
    /home/maddoxw/.virtualenvs/nos3/bin/python3 \
        components/onair/training/scenarios/campaign_mode_dwell.py \
        --log data/onair/scenarios/campaign_mode_dwell.log
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import time


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
RUN_BASELINE = os.path.join(REPO_ROOT, "components/onair/training/scenarios/run_baseline.py")
PYTHON = "/home/maddoxw/.virtualenvs/nos3/bin/python3"

# Uptime targets matched to v3 multi-uptime: T+30min, T+2h, T+4h, T+6h.
# Each entry is "seconds since make launch-quiet completed" at which to
# START the baseline. Each baseline takes ~15 min once started.
UPTIME_OFFSETS_S = [
    30 * 60,        # T+30min
    2 * 3600,       # T+2h
    4 * 3600,       # T+4h
    6 * 3600,       # T+6h
]


def _utc_now_str() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg: str, fh) -> None:
    line = f"[{_utc_now_str()}] {msg}"
    print(line, flush=True)
    fh.write(line + "\n")
    fh.flush()


def _run(cmd: list[str], fh, *, cwd: str | None = None, env: dict | None = None) -> int:
    _log(f"  $ {' '.join(cmd)}", fh)
    proc = subprocess.run(
        cmd, cwd=cwd or REPO_ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
    )
    for line in proc.stdout.splitlines():
        fh.write(f"    | {line}\n")
    fh.flush()
    return proc.returncode


def _container_started_at(name: str) -> dt.datetime | None:
    """Return the StartedAt time of a container, or None if not running."""
    try:
        out = subprocess.check_output(
            ["docker", "inspect", name, "--format", "{{.State.StartedAt}}"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        return dt.datetime.fromisoformat(out.replace("Z", "+00:00"))
    except (subprocess.CalledProcessError, ValueError):
        return None


def _sleep_until(target_utc: dt.datetime, label: str, fh) -> None:
    while True:
        now = dt.datetime.now(dt.timezone.utc)
        remaining = (target_utc - now).total_seconds()
        if remaining <= 0:
            return
        chunk = min(remaining, 600)  # log progress every 10 min max
        _log(f"  sleeping until {label} ({remaining/60:.1f} min remaining)", fh)
        time.sleep(chunk)


def run_campaign(log_path: str, dry_run: bool) -> int:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", buffering=1) as fh:
        _log("===== v4 mode_dwell campaign =====", fh)
        _log(f"  REPO_ROOT={REPO_ROOT}", fh)
        _log(f"  dry_run={dry_run}", fh)

        if dry_run:
            _log("DRY-RUN: would 'make stop' here", fh)
        else:
            _log("step 1/6: make stop", fh)
            rc = _run(["make", "stop"], fh)
            if rc != 0:
                _log(f"make stop returned {rc}; continuing (best-effort)", fh)

        if dry_run:
            _log("DRY-RUN: would 'make launch-quiet' here", fh)
            launch_utc = dt.datetime.now(dt.timezone.utc)
        else:
            _log("step 2/6: make launch-quiet", fh)
            rc = _run(["make", "launch-quiet"], fh)
            if rc != 0:
                _log(f"make launch-quiet FAILED (rc={rc}); aborting", fh)
                return 2
            launch_utc = _container_started_at("sc01-nos-fsw") or dt.datetime.now(dt.timezone.utc)
            _log(f"sc01-nos-fsw StartedAt={launch_utc.isoformat()}", fh)

        manifests: list[str] = []
        for i, offset_s in enumerate(UPTIME_OFFSETS_S, start=1):
            target_utc = launch_utc + dt.timedelta(seconds=offset_s)
            offset_label = f"T+{offset_s//60} min ({target_utc.isoformat()})"
            _log(f"step {2+i}/6: baseline {i}/4 at {offset_label}", fh)
            _sleep_until(target_utc, offset_label, fh)

            if dry_run:
                _log(f"DRY-RUN: would launch run_baseline.py at {_utc_now_str()}", fh)
                manifests.append(f"DRYRUN_baseline_{i}")
                continue

            rc = _run(
                [PYTHON, RUN_BASELINE, "--auto-discover", "--only", "mode_dwell"],
                fh,
            )
            if rc != 0:
                _log(f"baseline {i} FAILED (rc={rc}); aborting remaining", fh)
                return 3
            manifests.append(f"baseline_{i}_started_{target_utc.isoformat()}")

        _log("===== campaign complete =====", fh)
        for m in manifests:
            _log(f"  {m}", fh)
        return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--log", default="data/onair/scenarios/campaign_mode_dwell.log",
        help="Where to append campaign progress messages.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Walk the campaign timeline without actually stopping/relaunching/recording. "
             "Sleeps are real, so this still takes ~6 h.",
    )
    args = p.parse_args()
    return run_campaign(args.log, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
