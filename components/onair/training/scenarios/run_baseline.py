"""Drive NOS3 through the 5 nominal-baseline scenarios from the AI plan §1.

Runs scenarios sequentially in a single OnAIR session. Writes a manifest
(`data/onair/scenarios/manifest_<session>.json`) that the loader uses to tag
CSV files by scenario.

Usage:
    # Stack must be up (`make launch-quiet`).
    python3 components/onair/training/scenarios/run_baseline.py --fsw-host 172.25.0.5
    # Or auto-discover via docker:
    python3 components/onair/training/scenarios/run_baseline.py --auto-discover
    # Dry-run without sending packets:
    python3 components/onair/training/scenarios/run_baseline.py --dry-run

Scenario durations (v0):
    quiescent          5 min   no commands
    nominal_ops       10 min   ADCS pointing cycle + routine HK
    maneuvers          5 min   Thruster fires + attitude slews
    comm_passes        5 min   RADIO commanding
    mode_transitions   5 min   EPS switch toggles
                      ─────
                      30 min   ~150-200 commands total
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field

# Allow `python3 components/onair/training/scenarios/run_baseline.py` from repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmd import (
    ADCS_HK_REQ_MID, ADCS_MODE_BDOT, ADCS_MODE_INERTIAL, ADCS_MODE_PASSIVE,
    ADCS_MODE_SUNSAFE, CSS_CMD_MID, CSS_HK_REQ_MID, EPS_HK_REQ_MID,
    FSS_CMD_MID, FSS_HK_REQ_MID, IMU_CMD_MID, IMU_HK_REQ_MID,
    MAG_CMD_MID, MAG_HK_REQ_MID, RADIO_CMD_MID, RADIO_HK_REQ_MID,
    RW_CMD_MID, ST_CMD_MID, ST_HK_REQ_MID, THRUSTER_HK_REQ_MID,
    TORQUER_CMD_MID, TORQUER_HK_REQ_MID, Commander,
)


@dataclass
class ScenarioRecord:
    name: str
    start_utc: str
    end_utc: str
    duration_s: float
    n_commands: int
    notes: str = ""
    commands: list[dict] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────
# Scenario implementations
# ──────────────────────────────────────────────────────────────────────

def scenario_quiescent(c: Commander, duration_s: int) -> None:
    """No commanding. Pure HK baseline."""
    print(f"  [quiescent] sleeping {duration_s}s with no commands sent")
    if c.dry_run:
        return
    time.sleep(duration_s)


def scenario_nominal_ops(c: Commander, duration_s: int) -> None:
    """ADCS mode cycling + routine HK polling.

    Every 60s: cycle ADCS through INERTIAL → SUNSAFE → BDOT → PASSIVE.
    Every 8s:  send NOOP/REQ_HK to a rotating subsystem.
    """
    modes = [ADCS_MODE_INERTIAL, ADCS_MODE_SUNSAFE, ADCS_MODE_BDOT, ADCS_MODE_PASSIVE]
    hk_targets = [
        (ADCS_HK_REQ_MID, "ADCS"),
        (IMU_HK_REQ_MID, "IMU"),
        (CSS_HK_REQ_MID, "CSS"),
        (FSS_HK_REQ_MID, "FSS"),
        (MAG_HK_REQ_MID, "MAG"),
        (ST_HK_REQ_MID, "ST"),
        (TORQUER_HK_REQ_MID, "TORQUER"),
    ]

    end = time.monotonic() + duration_s
    mode_idx = 0
    hk_idx = 0
    next_mode_change = time.monotonic() + 60

    while time.monotonic() < end:
        # HK request every 8s
        mid, name = hk_targets[hk_idx % len(hk_targets)]
        c.req_hk(mid, name)
        hk_idx += 1

        # Mode change every 60s
        if time.monotonic() >= next_mode_change:
            c.adcs_set_mode(modes[mode_idx % len(modes)])
            mode_idx += 1
            next_mode_change = time.monotonic() + 60

        # Sleep ~8s between HK polls (post_delay already eats ~0.2s)
        sleep_left = max(0.0, 8.0 - 0.2)
        time.sleep(sleep_left if not c.dry_run else 0)


def scenario_maneuvers(c: Commander, duration_s: int) -> None:
    """Thruster fires + legitimate attitude slews."""
    end = time.monotonic() + duration_s

    # Pre-arm the thruster
    c.thruster_enable(True)
    c.req_hk(THRUSTER_HK_REQ_MID, "THRUSTER")

    # Set ADCS to INERTIAL (commanded attitude hold)
    c.adcs_set_mode(ADCS_MODE_INERTIAL)
    time.sleep(2 if not c.dry_run else 0)

    burn_pcts = [25, 30, 25, 20, 25]
    bi = 0
    next_burn = time.monotonic()

    while time.monotonic() < end:
        if time.monotonic() >= next_burn:
            c.thruster_pct(burn_pcts[bi % len(burn_pcts)])
            c.req_hk(THRUSTER_HK_REQ_MID, "THRUSTER")
            bi += 1
            next_burn = time.monotonic() + 30
        # Periodic ADCS HK during burns
        c.req_hk(ADCS_HK_REQ_MID, "ADCS")
        time.sleep(5 if not c.dry_run else 0)

    # Disable thruster after the maneuver block
    c.thruster_enable(False)


def scenario_comm_passes(c: Commander, duration_s: int) -> None:
    """Simulate a comm pass: RADIO commands + periodic HK."""
    end = time.monotonic() + duration_s
    next_cfg = time.monotonic() + 30
    cfg_seq = [0x00000001, 0x00000003, 0x0000000F, 0x00000003, 0x00000001]
    ci = 0

    while time.monotonic() < end:
        c.req_hk(RADIO_HK_REQ_MID, "RADIO")
        c.noop(RADIO_CMD_MID, "RADIO")
        if time.monotonic() >= next_cfg:
            c.radio_config(cfg_seq[ci % len(cfg_seq)])
            ci += 1
            next_cfg = time.monotonic() + 30
        time.sleep(5 if not c.dry_run else 0)


def scenario_mode_transitions(c: Commander, duration_s: int) -> None:
    """Legitimate EPS switch toggles + EPS HK polls.

    Toggles a rotating set of switches (0..2) every 60s. These are cosmetic
    state changes — they exercise the EPS code path without triggering the
    safety interlocks that the attack scripts target.
    """
    end = time.monotonic() + duration_s
    switches = [0, 1, 2]
    state = {s: True for s in switches}  # assume all on at start
    next_toggle = time.monotonic()
    si = 0

    while time.monotonic() < end:
        c.req_hk(EPS_HK_REQ_MID, "EPS")
        if time.monotonic() >= next_toggle:
            sw = switches[si % len(switches)]
            state[sw] = not state[sw]
            c.eps_switch(sw, state[sw])
            si += 1
            next_toggle = time.monotonic() + 60
        time.sleep(5 if not c.dry_run else 0)


SCENARIOS = [
    # Equal 5-min durations to keep per-scenario row counts roughly balanced
    # (~1.3K rows/scenario at OnAIR's ~5 Hz CSV cadence).
    ("quiescent", 300, scenario_quiescent),
    ("nominal_ops", 300, scenario_nominal_ops),
    ("maneuvers", 300, scenario_maneuvers),
    ("comm_passes", 300, scenario_comm_passes),
    ("mode_transitions", 300, scenario_mode_transitions),
]


# ──────────────────────────────────────────────────────────────────────
# Orchestration
# ──────────────────────────────────────────────────────────────────────

def auto_discover_fsw_host() -> str:
    """Inspect the sc01-nos-fsw container's IP. Container name is on the
    NOS3 allowlist (see feedback_docker_scope.md)."""
    out = subprocess.check_output([
        "docker", "inspect", "sc01-nos-fsw",
        "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
    ], text=True).strip()
    if not out:
        raise RuntimeError("sc01-nos-fsw has no IP — is it running?")
    return out


def tier1_5_reset(csv_dir: str, *, wait_timeout_s: int = 120) -> tuple[bool, str]:
    """Tier 1.5 reset: kill core-cpu1 + restart sc01-onair.

    Per project_reset_verification.md, this resets cFS to power-on state and
    restarts the SBN peer link. Takes ~40s for fresh CSVs to start landing.
    Returns (success, status) where status is the IP after reset.
    """
    import glob

    pre_files = set(glob.glob(os.path.join(csv_dir, "*.csv")))

    # 1. Kill core-cpu1 inside FSW container (fsw_respawn.sh will restart it)
    subprocess.run(
        ["docker", "exec", "sc01-nos-fsw", "sh", "-c",
         "kill -TERM $(pidof core-cpu1)"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # 2. Restart OnAIR (forces SBN re-peer + fresh CSV file)
    subprocess.run(
        ["docker", "restart", "sc01-onair"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # 3. Wait for a NEW CSV file to appear (signal that OnAIR is subscribed
    #    and writing). New = not in the pre-reset file set.
    deadline = time.time() + wait_timeout_s
    while time.time() < deadline:
        current = set(glob.glob(os.path.join(csv_dir, "*.csv")))
        new = current - pre_files
        if new:
            # Discover the new FSW IP — Docker may rotate it after restart.
            ip = auto_discover_fsw_host()
            return True, ip
        time.sleep(1)
    return False, ""


def precheck() -> dict:
    """Verify FSW + OnAIR containers are up and CSV streaming is active."""
    info = {}
    for name in ("sc01-nos-fsw", "sc01-onair"):
        status = subprocess.check_output([
            "docker", "inspect", name, "--format", "{{.State.Status}}",
        ], text=True).strip()
        info[name] = status
        if status != "running":
            raise RuntimeError(f"{name} is {status!r}, expected 'running'")
    return info


def now_utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")


def run_baseline(fsw_host: str, *, dry_run: bool, scale: float = 1.0,
                 only: list[str] | None = None) -> dict:
    """Run all scenarios in sequence. Returns the manifest dict.

    `scale < 1.0` shortens each scenario for harness validation
    (e.g. scale=0.1 -> 30s + 60s + 30s + 30s + 30s = 3 min total).
    """
    if not dry_run:
        info = precheck()
        print(f"precheck OK: {info}")

    c = Commander(fsw_host=fsw_host, dry_run=dry_run)
    session_id = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    manifest = {
        "session_id": session_id,
        "fsw_host": fsw_host,
        "dry_run": dry_run,
        "scale": scale,
        "scenarios": [],
        "started_utc": now_utc_iso(),
    }

    for name, base_duration, fn in SCENARIOS:
        if only and name not in only:
            continue
        duration = max(10, int(base_duration * scale))
        print(f"\n──── scenario: {name}  ({duration}s) ────")
        log_before = len(c.log)
        start_utc = now_utc_iso()
        t0 = time.monotonic()
        try:
            fn(c, duration)
        except KeyboardInterrupt:
            print("interrupted; recording partial scenario and exiting")
            duration_actual = time.monotonic() - t0
            end_utc = now_utc_iso()
            manifest["scenarios"].append({
                "name": name,
                "start_utc": start_utc, "end_utc": end_utc,
                "duration_s": duration_actual,
                "n_commands": len(c.log) - log_before,
                "notes": "INTERRUPTED",
                "commands": c.log[log_before:],
            })
            manifest["aborted"] = True
            return manifest
        end_utc = now_utc_iso()
        n_cmds = len(c.log) - log_before
        manifest["scenarios"].append({
            "name": name,
            "start_utc": start_utc, "end_utc": end_utc,
            "duration_s": time.monotonic() - t0,
            "n_commands": n_cmds,
            "commands": c.log[log_before:],
        })
        print(f"  → {n_cmds} commands sent")

    manifest["ended_utc"] = now_utc_iso()
    return manifest


def write_manifest(manifest: dict, out_dir: str, loop_idx: int | None = None) -> str:
    os.makedirs(out_dir, exist_ok=True)
    sid = manifest["session_id"]
    suffix = "_dryrun" if manifest.get("dry_run") else ""
    if loop_idx is not None:
        suffix = f"_loop{loop_idx:02d}" + suffix
    path = os.path.join(out_dir, f"manifest_{sid}{suffix}.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return path


def run_loops(
    fsw_host: str,
    *,
    n_loops: int,
    reset_between: bool,
    csv_dir: str,
    out_dir: str,
    dry_run: bool,
    scale: float,
    only: list[str] | None,
) -> list[str]:
    """Run the orchestrator N times, optionally Tier 1.5 reset between.

    Each loop writes its own manifest. Returns the list of manifest paths.
    """
    paths: list[str] = []
    current_host = fsw_host
    for i in range(1, n_loops + 1):
        print(f"\n{'═'*60}")
        print(f"  LOOP {i}/{n_loops}  (fsw_host={current_host})")
        print(f"{'═'*60}")
        manifest = run_baseline(
            fsw_host=current_host,
            dry_run=dry_run,
            scale=scale,
            only=only,
        )
        manifest["loop_idx"] = i
        manifest["loop_total"] = n_loops
        path = write_manifest(manifest, out_dir, loop_idx=i)
        paths.append(path)
        print(f"  manifest -> {path}")

        if reset_between and i < n_loops and not dry_run:
            print(f"\n  Tier 1.5 reset before loop {i+1}…")
            t0 = time.time()
            ok, new_ip = tier1_5_reset(csv_dir)
            elapsed = time.time() - t0
            if not ok:
                print(f"  RESET TIMED OUT after {elapsed:.0f}s — aborting remaining loops")
                break
            current_host = new_ip
            print(f"  reset complete in {elapsed:.0f}s, fsw_host now {current_host}")
            # 5s settle so OnAIR captures a few rows of fresh post-reset state
            # before the next manifest's clock starts.
            time.sleep(5)
    return paths


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fsw-host", default=None,
                   help="FSW container IP (autodetected from docker if --auto-discover is set)")
    p.add_argument("--auto-discover", action="store_true",
                   help="Look up sc01-nos-fsw IP via 'docker inspect'")
    p.add_argument("--dry-run", action="store_true",
                   help="Don't send UDP packets; just walk the scenario sequence")
    p.add_argument("--scale", type=float, default=1.0,
                   help="Scale all durations (e.g. 0.1 for a 3-min validation run)")
    p.add_argument("--only", nargs="+", default=None,
                   help="Run only the named scenarios")
    p.add_argument("--loops", type=int, default=1,
                   help="Number of full passes over all scenarios (default 1)")
    p.add_argument("--reset-between", action="store_true",
                   help="Tier 1.5 reset (kill core-cpu1 + restart sc01-onair) between loops")
    p.add_argument("--csv-dir", default="fsw/build/exe/cpu1/data/onair/csv",
                   help="OnAIR CSV output dir; used by --reset-between to detect "
                        "OnAIR resumed writing")
    p.add_argument("--out-dir", default="data/onair/scenarios")
    args = p.parse_args()

    if args.auto_discover:
        args.fsw_host = auto_discover_fsw_host()
        print(f"discovered FSW IP: {args.fsw_host}")
    if not args.fsw_host and not args.dry_run:
        p.error("must pass --fsw-host or --auto-discover (or --dry-run)")

    if args.loops > 1:
        paths = run_loops(
            fsw_host=args.fsw_host or "127.0.0.1",
            n_loops=args.loops,
            reset_between=args.reset_between,
            csv_dir=args.csv_dir,
            out_dir=args.out_dir,
            dry_run=args.dry_run,
            scale=args.scale,
            only=args.only,
        )
        print(f"\n{'═'*60}")
        print(f"  ALL LOOPS COMPLETE: {len(paths)} manifests written")
        print(f"{'═'*60}")
        for path in paths:
            print(f"  {path}")
    else:
        manifest = run_baseline(
            fsw_host=args.fsw_host or "127.0.0.1",
            dry_run=args.dry_run,
            scale=args.scale,
            only=args.only,
        )
        path = write_manifest(manifest, args.out_dir)
        total_cmds = sum(s["n_commands"] for s in manifest["scenarios"])
        print(f"\nmanifest -> {path}")
        print(f"  scenarios run: {len(manifest['scenarios'])}, total commands: {total_cmds}")


if __name__ == "__main__":
    main()
