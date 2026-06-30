#!/usr/bin/env python3
"""Idle mode-lock re-test — settle the "FSW gets stuck in PASSIVE after long
idle" question that drove the fresh-launch ritual in run_attack / run_baseline.

Background. The 2026-05-16 observation ("14,145 rows all MODE_PASSIVE despite
38x BDOT + 38x SUNSAFE commands") was the basis for believing a long-idle FSW
silently rejects upward mode transitions. On 2026-06-29 a live test on a FRESH
stack showed SET_MODE works fine (Mode telemetry cycled BDOT->SUNSAFE->
INERTIAL->PASSIVE, CommandErrorCount=0) AND that the original "all PASSIVE"
reading is reproducible as a *CSV-parsing artifact*: `awk -F','` / `cut -d,`
misalign OnAIR's quoted array columns (250 fields/row) and collapse Mode to a
wrong-but-constant column. A real parser (csv.DictReader, by header name)
shows all four modes.

What this script settles. The fresh-stack case is proven. The one case NOT
yet reproduced is a genuinely long-idle FSW (>>1 hr in PASSIVE). Run this
AFTER the stack has idled for several hours to confirm the lock is fully a
measurement artifact (expected: PASS) vs. a real FSW behaviour (FAIL).

It parses telemetry CORRECTLY (csv.DictReader, column-by-name) so its own
verdict can't be the very artifact it is testing for.

Usage (after the stack has idled a few hours):
    python3 components/onair/training/scenarios/idle_mode_lock_retest.py
    # options:
    #   --fsw-host 172.26.0.5        (default: docker inspect sc01-nos-fsw)
    #   --csv-dir  data/onair/csv    (default; picks newest csv_out_*.csv)
    #   --dwell 20                   (seconds per mode, re-cmd every 5s)

Verdict:
    PASS  -> Mode telemetry visited >=3 distinct commanded modes => no lock,
             the original observation was the parsing artifact. Retire the
             fresh-launch ritual.
    FAIL  -> Mode stayed pinned (<=1 commanded mode reached) despite cmds with
             CommandErrorCount flat => a REAL idle lock exists; keep the ritual
             and investigate the command path (SBN routing / pipe depth).
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import subprocess
import sys
import time

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from cmd import (  # noqa: E402
    Commander, ADCS_MODE_PASSIVE, ADCS_MODE_BDOT,
    ADCS_MODE_SUNSAFE, ADCS_MODE_INERTIAL,
)

MODE_COL = "ADCS_GNC.Mode"
CMDCNT_COL = "ADCS_HK.CommandCount"
ERRCNT_COL = "ADCS_HK.CommandErrorCount"
MODE_NAME = {"0": "PASSIVE", "1": "BDOT", "2": "SUNSAFE", "3": "INERTIAL"}

SEQUENCE = [
    ("BDOT", ADCS_MODE_BDOT),
    ("SUNSAFE", ADCS_MODE_SUNSAFE),
    ("INERTIAL", ADCS_MODE_INERTIAL),
    ("PASSIVE", ADCS_MODE_PASSIVE),
]


def discover_fsw_host() -> str:
    out = subprocess.check_output(
        ["docker", "inspect", "sc01-nos-fsw",
         "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"],
        text=True).strip()
    if not out:
        raise RuntimeError("sc01-nos-fsw has no IP — is the stack running?")
    return out


def newest_csv(csv_dir: str) -> str:
    files = glob.glob(os.path.join(csv_dir, "csv_out_*.csv"))
    if not files:
        raise FileNotFoundError(f"no csv_out_*.csv under {csv_dir}")
    return max(files, key=os.path.getmtime)


def read_last(csv_path: str) -> dict | None:
    """Last data row, parsed correctly (handles quoted array columns)."""
    last = None
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            last = row
    return last


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fsw-host", default=None)
    ap.add_argument("--csv-dir", default="data/onair/csv")
    ap.add_argument("--dwell", type=int, default=20, help="seconds per mode")
    args = ap.parse_args()

    host = args.fsw_host or discover_fsw_host()
    csv_path = newest_csv(args.csv_dir)
    print(f"FSW host : {host}")
    print(f"CSV      : {csv_path}")

    base = read_last(csv_path)
    if base is None:
        print("FAIL: CSV has no data rows (is OnAIR logging?)")
        return 2
    base_mode = base.get(MODE_COL)
    base_err = base.get(ERRCNT_COL)
    print(f"baseline : Mode={base_mode} ({MODE_NAME.get(base_mode, '?')}) "
          f"CmdErrCount={base_err}\n")

    c = Commander(fsw_host=host)
    seen_modes = set()
    timeline = []
    for label, const in SEQUENCE:
        print(f"[{time.strftime('%H:%M:%S')}] commanding {label} (={const}) for {args.dwell}s")
        t_end = time.monotonic() + args.dwell
        while time.monotonic() < t_end:
            c.adcs_set_mode(const)
            time.sleep(5)
        row = read_last(csv_path)
        m = row.get(MODE_COL) if row else None
        err = row.get(ERRCNT_COL) if row else None
        cnt = row.get(CMDCNT_COL) if row else None
        if m in MODE_NAME:
            seen_modes.add(m)
        timeline.append((label, m))
        print(f"    -> observed Mode={m} ({MODE_NAME.get(m, '?')}) "
              f"CmdCount={cnt} CmdErrCount={err}")

    distinct = len(seen_modes)
    err_grew = str(base_err) != str(err) and base_err not in (None, "[0]")
    print("\n--- verdict ---")
    print(f"commanded sequence : {[s for s, _ in SEQUENCE]}")
    print(f"observed Mode/phase : {timeline}")
    print(f"distinct commanded modes reached : {distinct} "
          f"({sorted(MODE_NAME[m] for m in seen_modes)})")
    if distinct >= 3:
        print("PASS — Mode telemetry tracked the commands. No idle lock; the "
              "original 'stuck in PASSIVE' was the CSV-parsing artifact. "
              "Safe to retire the fresh-launch ritual.")
        return 0
    print(f"FAIL — Mode reached only {distinct} commanded mode(s) despite "
          f"commands (CmdErrCount grew={err_grew}). A REAL idle lock may exist; "
          f"keep the fresh-launch ritual and trace the SET_MODE command path "
          f"(SBN routing / ADCS pipe depth).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
