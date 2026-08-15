#!/usr/bin/env python3
"""Single-mode ADCS soak for v5 detector evaluation.

Holds the FSW in one ADCS mode for the configured duration so the OnAIR plugin
collects a steady-state per-mode side file. Output for the chosen window is the
matching `iforest_out_*.csv` in `data/onair/csv/` — every flag during the soak
is a false positive (nominal flight).

Required pre-step for BDOT and PASSIVE (per project_fsw_autonomy_mode_lock.md):
    make stop && make launch-quiet
    # wait ~60s for OnAIR to peer SBN and start a new csv_out_*.csv

Then:
    python3 components/onair/training/scenarios/soak_mode.py \
        --auto-discover --mode BDOT --duration-min 60

After BDOT completes, INERTIAL can be commanded directly without relaunch:
    python3 components/onair/training/scenarios/soak_mode.py \
        --auto-discover --mode INERTIAL --duration-min 60

Per-mode evaluation (after both soaks):
    python3 - <<'PY'
    import pandas as pd, glob
    f = sorted(glob.glob("data/onair/csv/iforest_out_*.csv"))[-1]
    df = pd.read_csv(f)
    print(df.groupby("scenario").agg(
        frames=("frame_idx","size"),
        fp_rate=("is_anomaly","mean"),
        alert_rate=("alert","mean"),
    ))
    PY
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmd import (
    ADCS_HK_REQ_MID, ADCS_MODE_BDOT, ADCS_MODE_INERTIAL, ADCS_MODE_PASSIVE,
    ADCS_MODE_SUNSAFE, CSS_HK_REQ_MID, FSS_HK_REQ_MID, IMU_HK_REQ_MID,
    MAG_HK_REQ_MID, ST_HK_REQ_MID, TORQUER_HK_REQ_MID, Commander,
)


MODE_TABLE = {
    "PASSIVE": ADCS_MODE_PASSIVE,
    "BDOT": ADCS_MODE_BDOT,
    "SUNSAFE": ADCS_MODE_SUNSAFE,
    "INERTIAL": ADCS_MODE_INERTIAL,
}

# HK polls cycle through these to match the cadence used by scenario_nominal_ops
# / scenario_mode_dwell in run_baseline.py — keeps the side file's covariate
# distribution close to the training corpus's "operational" baseline.
HK_TARGETS = [
    (ADCS_HK_REQ_MID, "ADCS"),
    (IMU_HK_REQ_MID, "IMU"),
    (CSS_HK_REQ_MID, "CSS"),
    (FSS_HK_REQ_MID, "FSS"),
    (MAG_HK_REQ_MID, "MAG"),
    (ST_HK_REQ_MID, "ST"),
    (TORQUER_HK_REQ_MID, "TORQUER"),
]

# Re-issue the mode command every N seconds.
#
# ⚠ This was added to override "autonomous FSW transitions (eclipse → SUNSAFE,
# high-rate → BDOT)". **No such logic exists.** `generic_adcs_app.c` assigns
# `GNCPacket.Payload.Mode` in exactly ONE place — the SET_MODE command handler
# — and nothing else in the FSW writes it. The belief traces to an "idle mode
# lock" that our own notes later refuted as a CSV-parsing artifact
# (`awk -F','` misaligning quoted array columns), but the tooling built around
# it was never revisited.
#
# The re-commanding is therefore probably vestigial, and it is not free: 60 s
# mode dwells against the detector's 250-frame (~45 s) post-switch blind window
# put 83 % of the attack corpus inside a suppression window. Pass
# `--recmd-interval 0` to disable and test stickiness directly.
RECMD_INTERVAL_S = 30

# HK poll cadence; 8s × 7 targets ≈ 56s per full cycle.
HK_INTERVAL_S = 8.0


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


def precheck() -> dict:
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


def soak(c: Commander, mode_name: str, duration_s: int,
         recmd_interval_s: int = RECMD_INTERVAL_S) -> dict:
    mode_code = MODE_TABLE[mode_name]
    recmd_note = (f"re-cmd every {recmd_interval_s}s" if recmd_interval_s > 0
                  else "NO re-command (stickiness test)")
    print(f"  [soak] entering {mode_name} for {duration_s}s "
          f"(~{duration_s/60:.0f} min), {recmd_note}")
    c.adcs_set_mode(mode_code)

    t0 = time.monotonic()
    end = t0 + duration_s
    next_recmd = (t0 + recmd_interval_s) if recmd_interval_s > 0 else float("inf")
    hk_idx = 0
    last_progress = t0

    while time.monotonic() < end:
        mid, name = HK_TARGETS[hk_idx % len(HK_TARGETS)]
        c.req_hk(mid, name)
        hk_idx += 1
        now = time.monotonic()
        if now >= next_recmd:
            c.adcs_set_mode(mode_code)
            next_recmd = now + recmd_interval_s
        # Per-minute progress line so a 60-min soak isn't silent.
        if now - last_progress >= 60:
            elapsed_min = (now - t0) / 60
            remain_min = (end - now) / 60
            print(f"  [soak] {mode_name}  +{elapsed_min:5.1f} min "
                  f"({remain_min:5.1f} min remaining)  cmds={len(c.log)}")
            last_progress = now
        sleep_for = max(0.0, HK_INTERVAL_S - 0.2)
        time.sleep(sleep_for if not c.dry_run else 0)

    return {
        "mode": mode_name,
        "duration_s": time.monotonic() - t0,
        "n_commands": len(c.log),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", required=True, choices=sorted(MODE_TABLE.keys()),
                   help="ADCS mode to hold for the soak")
    p.add_argument("--duration-min", type=float, default=60.0,
                   help="Soak duration in minutes (default 60)")
    p.add_argument("--fsw-host", default=None,
                   help="FSW container IP (or use --auto-discover)")
    p.add_argument("--auto-discover", action="store_true",
                   help="Look up sc01-nos-fsw IP via 'docker inspect'")
    p.add_argument("--dry-run", action="store_true",
                   help="Walk the loop without sending UDP packets")
    p.add_argument("--recmd-interval", type=int, default=RECMD_INTERVAL_S,
                   help="Seconds between re-issuing SET_MODE. 0 = command once "
                        "and never again — the stickiness test (see the note on "
                        "RECMD_INTERVAL_S; the FSW has no autonomous mode logic, "
                        "so a mode should hold indefinitely on its own).")
    p.add_argument("--out-dir", default="data/onair/scenarios",
                   help="Where to write the soak manifest JSON")
    args = p.parse_args()

    if args.auto_discover:
        args.fsw_host = auto_discover_fsw_host()
        print(f"discovered FSW IP: {args.fsw_host}")
    if not args.fsw_host and not args.dry_run:
        p.error("must pass --fsw-host or --auto-discover (or --dry-run)")

    if not args.dry_run:
        info = precheck()
        print(f"precheck OK: {info}")

    duration_s = int(args.duration_min * 60)
    c = Commander(fsw_host=args.fsw_host or "127.0.0.1", dry_run=args.dry_run)
    session_id = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")

    manifest = {
        "session_id": session_id,
        "kind": "soak",
        "fsw_host": args.fsw_host,
        "dry_run": args.dry_run,
        "mode": args.mode,
        "duration_min": args.duration_min,
        "started_utc": now_utc_iso(),
    }

    try:
        result = soak(c, args.mode, duration_s, args.recmd_interval)
        manifest["result"] = result
    except KeyboardInterrupt:
        print("\ninterrupted — writing partial manifest")
        manifest["aborted"] = True

    manifest["ended_utc"] = now_utc_iso()
    manifest["n_commands_total"] = len(c.log)
    manifest["commands"] = c.log

    os.makedirs(args.out_dir, exist_ok=True)
    suffix = "_dryrun" if args.dry_run else ""
    path = os.path.join(
        args.out_dir,
        f"manifest_soak_{args.mode}_{session_id}{suffix}.json",
    )
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nmanifest -> {path}")
    print(f"commands sent: {len(c.log)}")


if __name__ == "__main__":
    main()
