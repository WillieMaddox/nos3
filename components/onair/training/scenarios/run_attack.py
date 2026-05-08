"""Drive a nominal scenario interleaved with a single SPARTA attack injection.

Phase 2 iter-0 harness: collect labeled CSV data with both scenario windows and
attack windows, so per-scenario IFs can be evaluated against attack-active rows.

Sequence (default):
    [scenario_pre 90s] -> [attack subprocess ~30s] -> [scenario_post 90s]

Both pre/post run the same nominal scenario (default: nominal_ops). The attack
runs as a separate subprocess against the same FSW; the harness records its
exact start_utc/end_utc timestamps in the manifest under `attacks: [...]` so
the loader can later tag CSV rows as `__attack_window=True/False` and
`__attack_id=<technique>`.

Manifest schema additions vs run_baseline.py:
    {
      "attacks": [
        {
          "id": "EX-0013",
          "script": "ex_0013_flooding.py",
          "level": 2,
          "start_utc": "2026-05-07T...",
          "end_utc":   "2026-05-07T...",
          "during_scenario": "nominal_ops",
          "exit_code": 0,
          "extra_args": []
        }
      ],
      "scenarios": [...]   # same as baseline
    }

Usage (stack must be up):
    python3 components/onair/training/scenarios/run_attack.py --auto-discover \\
        --attack ex_0013_flooding --attack-level 2 --during nominal_ops

    # Dry-run just walks the timeline:
    python3 components/onair/training/scenarios/run_attack.py --dry-run
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
from cmd import Commander
from run_baseline import (
    SCENARIOS,
    auto_discover_fsw_host,
    now_utc_iso,
    precheck,
    write_manifest,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
ATTACK_SCRIPTS_ROOT = os.path.join(REPO_ROOT, "gsw", "attack_scripts", "sparta")

# Catalog of supported iter-0 attack scripts. Each entry maps a short ID to
# the SPARTA technique code, the script's relative path, and the standard CLI
# flags it accepts. Add entries here as new attacks are folded into the harness.
ATTACK_CATALOG: dict[str, dict] = {
    "ex_0013_flooding": {
        "id": "EX-0013",
        "tactic": "execution",
        "path": "execution/ex_0013_flooding.py",
        "expected_runtime_s": 25,  # rough — depends on level
    },
    "ex_0014_spoofing": {
        "id": "EX-0014",
        "tactic": "execution",
        "path": "execution/ex_0014_spoofing.py",
        "expected_runtime_s": 20,
    },
    "ex_0001_replay": {
        "id": "EX-0001",
        "tactic": "execution",
        "path": "execution/ex_0001_replay.py",
        "expected_runtime_s": 30,
    },
}


def find_scenario(name: str):
    for scn_name, base_duration, fn in SCENARIOS:
        if scn_name == name:
            return scn_name, base_duration, fn
    raise SystemExit(f"unknown scenario: {name}; valid={[s[0] for s in SCENARIOS]}")


def run_attack_subprocess(
    script_path: str, fsw_host: str, attack_level: int,
    during_scenario: str, technique_id: str,
    extra_args: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Fire the attack script as a subprocess; return a manifest record."""
    extra_args = list(extra_args or [])
    cmd = [
        sys.executable, script_path,
        "--fsw-host", fsw_host,
        "--attack-level", str(attack_level),
    ] + extra_args
    print(f"  [attack] launching: {' '.join(cmd)}")
    start = now_utc_iso()
    if dry_run:
        time.sleep(2)  # short stand-in for the subprocess
        end = now_utc_iso()
        return {
            "id": technique_id, "script": os.path.basename(script_path),
            "level": attack_level, "start_utc": start, "end_utc": end,
            "during_scenario": during_scenario, "exit_code": 0,
            "extra_args": extra_args, "dry_run": True,
        }
    proc = subprocess.run(cmd, capture_output=True, text=True)
    end = now_utc_iso()
    print(f"  [attack] done in {(dt.datetime.fromisoformat(end) - dt.datetime.fromisoformat(start)).total_seconds():.1f}s "
          f"(exit={proc.returncode})")
    if proc.returncode != 0:
        print(f"  [attack] STDERR tail:\n{proc.stderr[-500:]}")
    return {
        "id": technique_id, "script": os.path.basename(script_path),
        "level": attack_level, "start_utc": start, "end_utc": end,
        "during_scenario": during_scenario, "exit_code": proc.returncode,
        "extra_args": extra_args,
        "stdout_lines": len(proc.stdout.splitlines()),
        "stderr_lines": len(proc.stderr.splitlines()),
    }


def run_attack_session(
    fsw_host: str, *, dry_run: bool, attack_key: str, attack_level: int,
    during: str, pre_s: int, post_s: int, attack_extra_args: list[str] | None,
) -> dict:
    if attack_key not in ATTACK_CATALOG:
        raise SystemExit(f"unknown attack: {attack_key}; valid={list(ATTACK_CATALOG)}")
    entry = ATTACK_CATALOG[attack_key]
    script_path = os.path.join(ATTACK_SCRIPTS_ROOT, entry["path"])
    if not os.path.exists(script_path):
        raise SystemExit(f"attack script not found at {script_path}")

    scn_name, _, scn_fn = find_scenario(during)

    if not dry_run:
        info = precheck()
        print(f"precheck OK: {info}")

    c = Commander(fsw_host=fsw_host, dry_run=dry_run)
    session_id = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    manifest = {
        "session_id": session_id,
        "fsw_host": fsw_host,
        "dry_run": dry_run,
        "attack_session": True,
        "scenarios": [],
        "attacks": [],
        "started_utc": now_utc_iso(),
    }

    def _run_block(label: str, dur: int) -> None:
        print(f"\n──── scenario block: {label}  ({dur}s) ────")
        log_before = len(c.log)
        start_utc = now_utc_iso()
        t0 = time.monotonic()
        scn_fn(c, dur)
        manifest["scenarios"].append({
            "name": scn_name,
            "label": label,
            "start_utc": start_utc,
            "end_utc": now_utc_iso(),
            "duration_s": time.monotonic() - t0,
            "n_commands": len(c.log) - log_before,
            "commands": c.log[log_before:],
        })

    # 1. Pre-attack scenario
    _run_block(f"{scn_name}_pre", pre_s)

    # 2. Attack injection
    print(f"\n──── attack: {attack_key} (level={attack_level}) ────")
    rec = run_attack_subprocess(
        script_path=script_path,
        fsw_host=fsw_host,
        attack_level=attack_level,
        during_scenario=scn_name,
        technique_id=entry["id"],
        extra_args=attack_extra_args,
        dry_run=dry_run,
    )
    manifest["attacks"].append(rec)

    # 3. Post-attack scenario (recovery / steady-state observation)
    _run_block(f"{scn_name}_post", post_s)

    manifest["ended_utc"] = now_utc_iso()
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fsw-host", default=None)
    p.add_argument("--auto-discover", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--attack", default="ex_0013_flooding",
                   choices=list(ATTACK_CATALOG),
                   help="Which SPARTA attack script to inject")
    p.add_argument("--attack-level", type=int, default=2,
                   help="Attack-level argument passed through to the script")
    p.add_argument("--during", default="nominal_ops",
                   choices=[s[0] for s in SCENARIOS],
                   help="Which nominal scenario brackets the attack window. "
                        "Match this to a scenario whose IF models the feature "
                        "space the attack disturbs (e.g. ex_0013 flooding bumps "
                        "command counters → use nominal_ops/maneuvers/comm_passes "
                        "where counter activity is in-distribution; quiescent's "
                        "IF won't see counter floods because it was trained on "
                        "near-zero-counter state).")
    p.add_argument("--pre-seconds", type=int, default=90,
                   help="Pre-attack scenario duration")
    p.add_argument("--post-seconds", type=int, default=180,
                   help="Post-attack scenario duration. Default 180s (vs prior "
                        "90s) because flood-class attacks leave FSW residual "
                        "that takes 60-120s to dissipate; the longer window "
                        "lets us see the full recovery curve.")
    p.add_argument("--attack-extra-args", nargs=argparse.REMAINDER, default=[],
                   help="Trailing args passed verbatim to the attack script "
                        "(e.g. -- --duration 3.0 --rate-low 5)")
    p.add_argument("--out-dir", default="data/onair/scenarios")
    args = p.parse_args()

    if args.auto_discover:
        args.fsw_host = auto_discover_fsw_host()
        print(f"discovered FSW IP: {args.fsw_host}")
    if not args.fsw_host and not args.dry_run:
        p.error("must pass --fsw-host or --auto-discover (or --dry-run)")

    manifest = run_attack_session(
        fsw_host=args.fsw_host or "127.0.0.1",
        dry_run=args.dry_run,
        attack_key=args.attack,
        attack_level=args.attack_level,
        during=args.during,
        pre_s=args.pre_seconds,
        post_s=args.post_seconds,
        attack_extra_args=args.attack_extra_args,
    )

    path = write_manifest(manifest, args.out_dir)
    n_scn = len(manifest["scenarios"])
    n_atk = len(manifest["attacks"])
    n_cmds = sum(s["n_commands"] for s in manifest["scenarios"])
    print(f"\nmanifest -> {path}")
    print(f"  scenario blocks: {n_scn}, attacks: {n_atk}, total nominal commands: {n_cmds}")


if __name__ == "__main__":
    main()
