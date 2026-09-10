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
from cmd import (
    ADCS_HK_REQ_MID, ADCS_MODE_BDOT, ADCS_MODE_INERTIAL, ADCS_MODE_PASSIVE,
    ADCS_MODE_SUNSAFE, CSS_HK_REQ_MID, FSS_HK_REQ_MID, IMU_HK_REQ_MID,
    MAG_HK_REQ_MID, ST_HK_REQ_MID, TORQUER_HK_REQ_MID,
    quat_inertial_hold_target,
    Commander,
)

# Seconds to wait after enabling the star tracker before commanding INERTIAL.
# ST device telemetry publishes on the sim's own cadence; entering the mode
# before a valid sample lands means qValid is false at mode entry and the
# control law sits out its first frames. (AINOS3-86)
ST_SETTLE_S = 10.0

# ⚠ AINOS3-86: an INERTIAL hold entered from a TUMBLING state diverges instead of
# capturing, and this is not a tuning problem. While the star tracker is
# Earth-occluded `qValid` is false and `AC_inertial()` is skipped entirely, so
# torque arrives in short bursts whenever the boresight happens to clear the
# exclusion cone. Measured live 2026-09-10 at a ~6 % valid duty cycle:
# |w| 0.64 -> 1.40 -> 2.31 deg/s in 60 s. Burst control PUMPS energy in.
#
# So the rates must be damped FIRST, by a mode with no star-tracker dependency.
#
# ⚠⚠ USE SUNSAFE, NOT BDOT — this is the counter-intuitive part, and it was
# measured rather than reasoned. BDOT looks like the obvious choice (detumble IS
# its purpose, and it is magnetorquer-only so it runs while blinded) and it does
# NOT converge on this vehicle: over 4 minutes it limit-cycled between 1.16 and
# 2.57 deg/s with no downward trend.
#
# The cause is control-authority mismatch, not a defect. `AC_bdot` is textbook and
# correctly signed (`Mcmd = -Kb*bdot/|bvb|`, generic_adcs_adac.c:219-244; the
# observed Mcmd 38.04 matches Kb=200 exactly), but MaxMcmd is 1.42 so the command
# saturates 27x over, and the vehicle is 4 kg with I = [0.0067, 0.033, 0.033]
# kg m^2 (SC_NOS3.txt:30-31). Saturated bang-bang against that inertia overshoots
# every correction. Torquers were verified enabled and applying — BDOT was working
# as designed and was still the wrong tool.
#
# SUNSAFE uses the sun sensors and reaction wheels: finer authority, no star
# tracker either. Measured 1.66 -> 0.26 deg/s in 95 s. It is also what the FSW
# boots into, which is why the vehicle's natural resting rate is ~0.2 deg/s.
#
# The target is therefore ~0.35 deg/s (near the natural floor), NOT 0.05 — SUNSAFE
# settles around 0.2-0.3 deg/s and waiting for less than that never returns.
DETUMBLE_TARGET_DEG_S = 0.35
DETUMBLE_TIMEOUT_S = 600.0
from run_baseline import (
    SCENARIOS,
    auto_discover_fsw_host,
    now_utc_iso,
    precheck,
    write_manifest,
)


def scenario_all_modes_dwell(c: Commander, duration_s: int) -> None:
    """Cycle ADCS through all 4 modes deterministically.

    Holds each of INERTIAL, SUNSAFE, BDOT, PASSIVE for ``duration_s // 4``
    seconds, re-issuing `adcs_set_mode` every 30s within each phase to
    defeat FSW autonomous demotion (esp. INERTIAL → SUNSAFE when star
    tracker quality dips). Issues HK polls every ~8s to maintain command
    cadence parity with ``scenario_nominal_ops`` so the IF's nominal
    distribution looks similar.

    Created for attack-corpus mode balance: with this as the pre+post
    scenario, every attack's corruption window samples rows across all
    four ADCS modes, not just whatever mode the FSW happens to default
    to (SUNSAFE for run_attack.py's idle context).
    """
    modes = [
        ("INERTIAL", ADCS_MODE_INERTIAL),
        ("SUNSAFE",  ADCS_MODE_SUNSAFE),
        ("BDOT",     ADCS_MODE_BDOT),
        ("PASSIVE",  ADCS_MODE_PASSIVE),
    ]
    hk_targets = [
        (ADCS_HK_REQ_MID, "ADCS"),
        (IMU_HK_REQ_MID, "IMU"),
        (CSS_HK_REQ_MID, "CSS"),
        (FSS_HK_REQ_MID, "FSS"),
        (MAG_HK_REQ_MID, "MAG"),
        (ST_HK_REQ_MID, "ST"),
        (TORQUER_HK_REQ_MID, "TORQUER"),
    ]
    per_mode = max(60, duration_s // len(modes))
    hk_idx = 0

    for label, mode_const in modes:
        print(f"  [all_modes_dwell] entering {label} for {per_mode}s")
        c.adcs_set_mode(mode_const)
        t_end = time.monotonic() + per_mode
        next_recmd = time.monotonic() + 30
        while time.monotonic() < t_end:
            mid, name = hk_targets[hk_idx % len(hk_targets)]
            c.req_hk(mid, name)
            hk_idx += 1
            if time.monotonic() >= next_recmd:
                c.adcs_set_mode(mode_const)
                next_recmd = time.monotonic() + 30
            sleep_left = max(0.0, 8.0 - 0.2)
            time.sleep(sleep_left if not c.dry_run else 0)


def _detumble_before_inertial(c: Commander) -> None:
    """Damp body rates in SUNSAFE before attempting an INERTIAL hold (AINOS3-86).

    ⚠ This step is not optional and it is not tuning. Entering INERTIAL from a
    tumbling state DIVERGES: while the star tracker is Earth-occluded `qValid`
    is false and `AC_inertial()` is skipped, so torque lands in bursts whenever
    the boresight happens to clear the exclusion cone, and burst control pumps
    energy in. Measured live 2026-09-10 at ~6 % valid duty: |w| went
    0.64 -> 1.40 -> 2.31 deg/s in 60 s.

    ⚠ SUNSAFE, not BDOT. BDOT is the obvious choice and does not converge here --
    it limit-cycles at 1.2-2.6 deg/s because its saturated bang-bang command is
    far too coarse for a 4 kg vehicle. SUNSAFE damps via the wheels and has no
    star-tracker dependency either. See the DETUMBLE_* block above.

    Best-effort: if the live CSV cannot be found we still run BDOT for a fixed
    spell rather than skipping the step, because skipping it is what produces a
    silently-uncontrolled run.
    """
    print(f"  [single_mode_hold] INERTIAL: damping rates in SUNSAFE to "
          f"|w| < {DETUMBLE_TARGET_DEG_S} deg/s before the hold")
    c.adcs_set_mode(ADCS_MODE_SUNSAFE)
    if c.dry_run:
        return

    try:
        from inertial_capture import body_rate_deg_s, newest_csv, DEFAULT_CSV_GLOB
    except Exception as exc:                       # pragma: no cover - import guard
        print(f"  [single_mode_hold] ⚠ cannot import the rate check ({exc}); "
              f"running BDOT open-loop for {DETUMBLE_TIMEOUT_S:.0f}s")
        time.sleep(DETUMBLE_TIMEOUT_S)
        return

    path = newest_csv(DEFAULT_CSV_GLOB)
    if not path:
        print(f"  [single_mode_hold] ⚠ no live CSV found; running BDOT open-loop "
              f"for {DETUMBLE_TIMEOUT_S:.0f}s")
        time.sleep(DETUMBLE_TIMEOUT_S)
        return

    deadline = time.monotonic() + DETUMBLE_TIMEOUT_S
    while time.monotonic() < deadline:
        time.sleep(30)
        try:
            w = body_rate_deg_s(path)
        except Exception:
            continue
        if w is None:
            continue
        print(f"  [single_mode_hold] detumble: |w| = {w:.4f} deg/s")
        if w < DETUMBLE_TARGET_DEG_S:
            print("  [single_mode_hold] detumbled")
            return
    print(f"  [single_mode_hold] ⚠ rate damping TIMED OUT after "
          f"{DETUMBLE_TIMEOUT_S:.0f}s — the INERTIAL slice of this run is suspect; "
          f"verify with inertial_capture.py before letting its data count")


def make_scenario_single_mode_hold(mode_label: str, configure_inertial: bool = True):
    """Hold ONE ADCS mode for the whole bracket. Returns a scenario callable.

    Why this exists (AINOS3-77 follow-on, 2026-08-15)
    -------------------------------------------------
    `all_modes_dwell` cycles all four modes every ``duration_s // 4`` seconds —
    60 s at the default 240 s bracket. The deployed detector suppresses alerts
    for **250 frames (~45 s) after every mode switch**
    (`ModeSwitchWarmupFrames`), so the blind window eats roughly three quarters
    of each dwell. Measured on the frozen corpus: **83.2 % of all attack frames
    sit inside a post-switch suppression window**, and 100 % sit within 600
    frames of a switch. The collection design and the detector design were set
    independently and are close to incompatible, so per-mode detection was never
    actually measurable under deployed conditions — in any mode.

    This scenario holds a single mode for the entire pre/post bracket, so
    everything after the first ~45 s is eligible to alert. Pair it with a
    pre-window long enough to clear the warmup (>= 180 s recommended).

    Also does NOT re-issue the mode command. The FSW has no autonomous mode
    logic — `generic_adcs_app.c` writes `Payload.Mode` in exactly one place, the
    SET_MODE handler — and this was demonstrated directly: one command, 17,670
    consecutive frames, zero drift. Not re-commanding additionally keeps the run
    from tripping the R14 flap rule, which 60 s cycling would fire continuously.

    INERTIAL needs configuring before it is held (AINOS3-86, 2026-09-10)
    -------------------------------------------------------------------
    Commanding `SET_MODE INERTIAL` is NOT sufficient to put the vehicle into a
    controlled inertial hold, and every INERTIAL run collected before this change
    was uncontrolled tumble wearing the INERTIAL label:

        ST.DeviceEnabled = 0  ->  ADCS_DI.Payload.St.valid = 0
                              ->  ADCS_GNC.qValid = 0
                              ->  `if (GNC->qValid)` is false
                              ->  AC_inertial() NEVER EXECUTES

    (`generic_adcs_adac.c:338`.) The star tracker boots disabled and no tooling
    ever enabled it, so `qValid` is 0 across all 1.75 M rows ever collected. The
    published 33.6 % INERTIAL nominal false-alarm rate is the detector correctly
    flagging free drift — a plant misconfiguration, not a detector defect.

    So for INERTIAL this scenario now, in order:

      1. enables the star tracker (`ST_FC_ENABLE`), then waits for it to publish;
      2. commands the ORBIT-NORMAL target attitude
         (`GENERIC_ADCS_INERTIAL_QUATERNION_CC`, from
         `cmd.quat_inertial_hold_target`);
      3. only then commands `SET_MODE INERTIAL`.

    ⚠ Step 2 must be the orbit normal, not identity, and that is the part that
    took two sprints to find. Enabling the star tracker is NOT sufficient on its
    own: 42 clears `ST->Valid` whenever the boresight falls within
    (Earth-limb + 10 deg) = **80.4 deg of nadir** (`42sensors.c:304-342`). At any
    FIXED inertial attitude the nadir direction sweeps a full circle in the body
    frame once per ~92 min orbit, so the star tracker is blinded for ~40 % of
    every orbit in one unbroken ~35-minute stretch -- and `qValid` gates
    `AC_inertial()`, so for that stretch the control law does not run and the
    "INERTIAL hold" is free drift wearing the INERTIAL label.

    Identity is an arbitrary attitude with no relationship to the orbit, so it
    inherits that duty cycle. The orbit normal is perpendicular to nadir BY
    CONSTRUCTION, so boresight-to-nadir is pinned at 90 deg -- a permanent
    9.6 deg margin, every orbit. See `cmd.orbit_normal_from_config`.

    ⚠ There is a bootstrap: the controller cannot slew while blinded, because
    the control law is exactly what `qValid` gates. Starting inside a blind
    stretch the vehicle must WAIT (up to ~35 min) for the orbit to carry the
    boresight out of the Earth cone; only then does it capture and hold, after
    which it stays valid indefinitely. Callers must therefore verify capture --
    `ST.DeviceEnabled = 1` is NOT evidence the loop closed. Use
    `inertial_capture.py`.

    Proven live 2026-09-10: damp -> command -> wait -> capture, ending at
    boresight 0.4-0.6 deg off the orbit normal, boresight-to-nadir 89.4-89.9 deg
    against the 80.5 deg threshold, qValid 100 %, held. Because the hold is
    stable once captured, a BATCH of runs on one stack pays the wait only once --
    do the setup at the start of a batch, not per run.

    ⚠ Pass ``configure_inertial=False`` to reproduce the OLD condition. That is
    not a legacy escape hatch to leave lying around — it is the control arm of
    the A/B this change has to be judged by, since the "before" corpus was
    collected under exactly that condition.

    ⚠ Known and NOT fixed here: with the ST enabled `qValid` still latches in
    only ~56 of 80 frames, so the control law runs intermittently (AINOS3-91),
    and `Ki = [0,0,0]` leaves `sumtherr` winding up inert. Both are separate
    tickets. This change establishes *closed-loop at all*, which is the
    precondition for measuring anything else.
    """
    mode_const = {
        "INERTIAL": ADCS_MODE_INERTIAL, "SUNSAFE": ADCS_MODE_SUNSAFE,
        "BDOT": ADCS_MODE_BDOT, "PASSIVE": ADCS_MODE_PASSIVE,
    }[mode_label]

    def _scenario(c: Commander, duration_s: int) -> None:
        hk_targets = [
            (ADCS_HK_REQ_MID, "ADCS"), (IMU_HK_REQ_MID, "IMU"),
            (CSS_HK_REQ_MID, "CSS"), (FSS_HK_REQ_MID, "FSS"),
            (MAG_HK_REQ_MID, "MAG"), (ST_HK_REQ_MID, "ST"),
            (TORQUER_HK_REQ_MID, "TORQUER"),
        ]
        if mode_label == "INERTIAL" and configure_inertial:
            _detumble_before_inertial(c)
            print("  [single_mode_hold] INERTIAL: enabling star tracker "
                  "(qValid gates AC_inertial)")
            c.st_enable(True)
            # Let the ST publish at least one valid sample before the control
            # law is switched on, so qValid is already true at mode entry
            # rather than latching some frames later.
            time.sleep(ST_SETTLE_S if not c.dry_run else 0)
            q_target = quat_inertial_hold_target()
            print(f"  [single_mode_hold] INERTIAL: commanding ORBIT-NORMAL target "
                  f"attitude {tuple(round(x, 6) for x in q_target)} "
                  f"(keeps the ST 90 deg off nadir all orbit)")
            c.adcs_set_inertial_quaternion(q_target)
            time.sleep(1.0 if not c.dry_run else 0)
        elif mode_label == "INERTIAL":
            print("  [single_mode_hold] INERTIAL: ⚠ CONTROL ARM — star tracker "
                  "left disabled, no target attitude (reproduces the "
                  "uncontrolled-drift condition of the pre-2026-09-10 corpus)")

        print(f"  [single_mode_hold] holding {mode_label} for {duration_s}s "
              f"(commanded once, no re-command)")
        c.adcs_set_mode(mode_const)
        t_end = time.monotonic() + duration_s
        hk_idx = 0
        while time.monotonic() < t_end:
            mid, name = hk_targets[hk_idx % len(hk_targets)]
            c.req_hk(mid, name)
            hk_idx += 1
            time.sleep(max(0.0, 8.0 - 0.2) if not c.dry_run else 0)

    return _scenario


# Local extension to run_baseline's SCENARIOS that includes the attack-
# specific all_modes_dwell scenario. find_scenario uses this so the
# --during arg can name it without polluting run_baseline.py's nominal
# corpus definition.
LOCAL_SCENARIOS = list(SCENARIOS) + [
    ("all_modes_dwell", 240, scenario_all_modes_dwell),
] + [
    # single_mode_hold_<MODE>: one mode, held throughout, commanded once.
    (f"single_mode_hold_{m}", 300, make_scenario_single_mode_hold(m))
    for m in ("INERTIAL", "SUNSAFE", "BDOT", "PASSIVE")
] + [
    # The AINOS3-86 A/B control arm: INERTIAL held the way the pre-2026-09-10
    # corpus held it — star tracker disabled, no target attitude, so the control
    # law never runs. Named rather than flagged so a run's scenario field records
    # which arm it was, and a manifest can never be ambiguous about it.
    ("single_mode_hold_INERTIAL_uncontrolled", 300,
     make_scenario_single_mode_hold("INERTIAL", configure_inertial=False)),
]

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
ATTACK_SCRIPTS_ROOT = os.path.join(REPO_ROOT, "gsw", "attack_scripts", "sparta")
# Log hygiene (NOS3-322 change A): route each attack's detection log into
# <repo>/logs/attack_runs/ instead of the CWD (which cluttered the repo root).
# Persistent (outside fsw/build, survives rebuilds), git-ignored, NAS-backed.
ATTACK_LOG_DIR = os.path.join(REPO_ROOT, "logs", "attack_runs")

# Catalog of supported iter-0 attack scripts. Each entry maps a short ID to
# the SPARTA technique code, the script's relative path, the standard CLI
# flags it accepts, and a `corruption_dwell_s` — the number of seconds after
# the attack subprocess exits during which the spacecraft state remains in
# detector-distinguishable corruption. The detection signal for state-change
# attacks lives in this dwell, not in the brief cmd-injection phase.
# Defaults are empirical (see project_phase2_attack_classification + the
# Phase 2 iter-1 manifests). 0 = drain class (no residual, or undetectable).
# Add entries here as new attacks are folded into the harness.
ATTACK_CATALOG: dict[str, dict] = {
    "ex_0013_flooding": {
        "id": "EX-0013",
        "tactic": "execution",
        "path": "execution/ex_0013_flooding.py",
        "expected_runtime_s": 25,  # rough — depends on level
        "corruption_dwell_s": 90,  # flood residual visible 60-90s post-attack
    },
    # EX-0001 replay: split into .01 (command packets) and .02 markdown-only.
    "ex_0001_01_command_packets": {
        "id": "EX-0001.01",
        "tactic": "execution",
        "path": "execution/ex_0001_replay/ex_0001_01_command_packets.py",
        "expected_runtime_s": 8,
        "corruption_dwell_s": 0,  # replay leaves no state residual
    },
    # EX-0008 time-sync: split into .01 ATS and .02 RTS.
    # Both require a malicious ATS/RTS table to be pre-loaded — typically via
    # EX-0012.04. Without the prerequisite, SC_START_ATS / SC_START_RTS are
    # rejected at the SC app boundary and the declared footprint
    # (AtsNumber/AtpState/RtsNumber transitions) is unreachable. The harness
    # supports --chain to auto-run the requires-attack at level 2 (no cleanup)
    # before the main attack.
    "ex_0008_01_absolute_time_sequences": {
        "id": "EX-0008.01",
        "tactic": "execution",
        "path": "execution/ex_0008_time_synchronized_execution/ex_0008_01_absolute_time_sequences.py",
        "expected_runtime_s": 10,
        "corruption_dwell_s": 300,
        "requires": ["ex_0012_04_app_subscriber_tables"],
    },
    "ex_0008_02_relative_time_sequences": {
        "id": "EX-0008.02",
        "tactic": "execution",
        "path": "execution/ex_0008_time_synchronized_execution/ex_0008_02_relative_time_sequences.py",
        "expected_runtime_s": 10,
        "corruption_dwell_s": 300,
        "requires": ["ex_0012_04_app_subscriber_tables"],
    },
    # EX-0009 code flaws: .01 FSW implementable; .02 OS and .03 COTS markdown-only.
    "ex_0009_01_flight_software": {
        "id": "EX-0009.01",
        "tactic": "execution",
        "path": "execution/ex_0009_exploit_code_flaws/ex_0009_01_flight_software.py",
        "expected_runtime_s": 15,
        "corruption_dwell_s": 0,  # error counters increment, no state corruption
    },
    # EX-0014 spoofing: .01 time, .03 sensor, .04 PNT implementable; .02 and .05 md-only.
    "ex_0014_01_time_spoof": {
        "id": "EX-0014.01",
        "tactic": "execution",
        "path": "execution/ex_0014_spoofing/ex_0014_01_time_spoof.py",
        "expected_runtime_s": 10,
        "corruption_dwell_s": 600,  # same as EX-0012.12 — clock jam persists
    },
    "ex_0014_03_sensor_data": {
        "id": "EX-0014.03",
        "tactic": "execution",
        "path": "execution/ex_0014_spoofing/ex_0014_03_sensor_data.py",
        "expected_runtime_s": 10,
        "corruption_dwell_s": 300,
    },
    "ex_0014_04_pnt_spoofing": {
        "id": "EX-0014.04",
        "tactic": "execution",
        "path": "execution/ex_0014_spoofing/ex_0014_04_pnt_spoofing.py",
        "expected_runtime_s": 8,
        "corruption_dwell_s": 300,
    },
    # EX-0012 split into per-sub-technique scripts (see entries below).
    # Legacy ex_0012_modify_on_board_values.py was deleted; existing
    # attack manifests that reference it remain as historical records.
    "ex_0012_09_eps_subsystem": {
        "id": "EX-0012.09",
        "tactic": "execution",
        "path": "execution/ex_0012_modify_on_board_values/ex_0012_09_eps_subsystem.py",
        "expected_runtime_s": 12,
        # Level 4 (full cleanup) → dwell 0; level 2 (no restore) → 300+
        # The harness defaults to the conservative value; override via
        # --corruption-dwell-s when invoking at attack-level 4.
        "corruption_dwell_s": 300,
    },
    "ex_0012_07_propulsion_subsystem": {
        "id": "EX-0012.07",
        "tactic": "execution",
        "path": "execution/ex_0012_modify_on_board_values/ex_0012_07_propulsion_subsystem.py",
        "expected_runtime_s": 12,
        "corruption_dwell_s": 300,
    },
    "ex_0012_08_adcs_subsystem": {
        "id": "EX-0012.08",
        "tactic": "execution",
        "path": "execution/ex_0012_modify_on_board_values/ex_0012_08_adcs_subsystem.py",
        "expected_runtime_s": 10,
        # FSW autonomy may revert mode within ~60s; dwell-window labeling
        # should capture the period during which the commanded mode is
        # actually reported in `ADCS_GNC.Mode`.
        "corruption_dwell_s": 60,
    },
    "ex_0012_12_system_clock": {
        "id": "EX-0012.12",
        "tactic": "execution",
        "path": "execution/ex_0012_modify_on_board_values/ex_0012_12_system_clock.py",
        "expected_runtime_s": 10,
        # Clock jam persists indefinitely; downstream scheduler effects
        # (mistimed SC/SCH activities) can manifest hours later.
        "corruption_dwell_s": 600,
    },
    "ex_0012_03_memory_write": {
        "id": "EX-0012.03",
        "tactic": "execution",
        "path": "execution/ex_0012_modify_on_board_values/ex_0012_03_memory_write.py",
        "expected_runtime_s": 10,
        # Tables are not restorable from script alone; full corruption
        # persists until a known-good file is re-uploaded.
        "corruption_dwell_s": 600,
    },
    "ex_0012_04_app_subscriber_tables": {
        "id": "EX-0012.04",
        "tactic": "execution",
        "path": "execution/ex_0012_modify_on_board_values/ex_0012_04_app_subscriber_tables.py",
        "expected_runtime_s": 10,
        # RTS/ATS payloads may fire at any future trigger time; dwell
        # bound is generous to cover next scheduled trigger.
        "corruption_dwell_s": 600,
    },
    "ex_0012_05_scheduling_algorithm": {
        "id": "EX-0012.05",
        "tactic": "execution",
        "path": "execution/ex_0012_modify_on_board_values/ex_0012_05_scheduling_algorithm.py",
        "expected_runtime_s": 10,
        # Schedule corruption persists until table is reloaded; downstream
        # app-counter freeze is a continuous absence signal.
        "corruption_dwell_s": 600,
        # Cadence-shift on SCH counters is a rate change, not a step transition.
        # 90s post-window doesn't expose enough samples for a rate diff to clear
        # the noise floor; 300s is the minimum for the absence-of-delta signal
        # to be visible. See [[project_attack_footprint_validation_wave2_2026-05-15]].
        "recommended_post_seconds_s": 300,
    },
    # IMP-0001..0006 REMOVED 2026-08-28. SPARTA v4.0 deprecates the entire v3 Impact
    # family (verified: 6 of 270 attack-patterns, zero IOB indicators, no successor
    # mapping in the bundle — v4 replaced an EFFECT taxonomy with a MECHANISM one).
    # Decision was remove, not remap; see AINOS3-96's 2026-08-28 log entry and the
    # label-set-freeze ticket. Historical batch configs that still name these keys
    # (batch_permode_pilot.json, batch_ainos3_30_weakclass.json) now fail loudly with
    # "unknown attack" rather than running — the intended behaviour for the record of
    # a completed study.
    # DE-0003 obfuscate on-board values (12 sub-techniques). Like EX-0012 these
    # modify on-board state, but the intent is evasion (hide adversary activity)
    # rather than direct effect. Many have only level 1 (recon-only) — those
    # exercise the command path but produce no state delta.
    "de_0003_01_vehicle_command_counter": {
        "id": "DE-0003.01", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_01_vehicle_command_counter.py",
        "expected_runtime_s": 8, "corruption_dwell_s": 60,
    },
    "de_0003_02_rejected_command_counter": {
        "id": "DE-0003.02", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_02_rejected_command_counter.py",
        "expected_runtime_s": 8, "corruption_dwell_s": 60,
    },
    "de_0003_03_command_receiver_mode": {
        "id": "DE-0003.03", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_03_command_receiver_mode.py",
        # Target CI_DEBUG (MID 0x18E0). CI HK NOT subscribed by OnAIR.
        # Level-1 cmd-injection bar via subprocess exit_code only.
        "expected_runtime_s": 8, "corruption_dwell_s": 60,
    },
    "de_0003_04_command_receiver_rssi": {
        "id": "DE-0003.04", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_04_command_receiver_rssi.py",
        "expected_runtime_s": 8, "corruption_dwell_s": 0,  # level-1-only, recon-only
    },
    "de_0003_05_command_receiver_lock_modes": {
        "id": "DE-0003.05", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_05_command_receiver_lock_modes.py",
        "expected_runtime_s": 8, "corruption_dwell_s": 0,
    },
    "de_0003_06_telemetry_downlink_modes": {
        "id": "DE-0003.06", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_06_telemetry_downlink_modes.py",
        # CFE_EVS DISABLE_EVENT_TYPE (subscribed) + TO_DEBUG (not
        # subscribed). EVS-side cmd observable via CFE_EVS_HK; TO-side
        # confirmable via subprocess exit_code only.
        "expected_runtime_s": 8, "corruption_dwell_s": 60,
    },
    "de_0003_07_cryptographic_modes": {
        "id": "DE-0003.07", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_07_cryptographic_modes.py",
        "expected_runtime_s": 8, "corruption_dwell_s": 0,
    },
    "de_0003_08_received_commands": {
        "id": "DE-0003.08", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_08_received_commands.py",
        "expected_runtime_s": 8, "corruption_dwell_s": 60,
    },
    "de_0003_09_system_clock_for_evasion": {
        "id": "DE-0003.09", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_09_system_clock_for_evasion.py",
        # 2026-05-28 (Track-2 offline-validator): script at level 2 sends a
        # CFE_TIME NOOP only, not SET_TIME — confirmed by inspection +
        # csv_out_2026-05-16T06-47-23 showing CFE_TIME.CommandCounter +1 with
        # SecondsSTCF/ClockStateFlags untouched. Reduced dwell from 600 s
        # (the EX-0012.12 SET_TIME comparison) to 60 s to match the
        # NOOP-only impl. Upgrade dwell back to 600 only if the script
        # is upgraded to actually issue SET_TIME.
        "expected_runtime_s": 8, "corruption_dwell_s": 60,
    },
    "de_0003_10_gps_ephemeris": {
        "id": "DE-0003.10", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_10_gps_ephemeris.py",
        "expected_runtime_s": 8, "corruption_dwell_s": 300,
    },
    "de_0003_11_watchdog_timer_for_evasion": {
        "id": "DE-0003.11", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_11_watchdog_timer_for_evasion.py",
        # Target HS app (MID 0x18AE). HS HK NOT subscribed by OnAIR.
        # Level-1 cmd-injection bar via subprocess exit_code only.
        "expected_runtime_s": 8, "corruption_dwell_s": 60,
    },
    "de_0003_12_poison_ai_ml_training": {
        "id": "DE-0003.12", "tactic": "defense_evasion",
        "path": "defense_evasion/de_0003_onboard_values_obfuscation/de_0003_12_poison_ai_ml_training.py",
        "expected_runtime_s": 8, "corruption_dwell_s": 0,
    },
}


def find_scenario(name: str):
    for scn_name, base_duration, fn in LOCAL_SCENARIOS:
        if scn_name == name:
            return scn_name, base_duration, fn
    raise SystemExit(f"unknown scenario: {name}; valid={[s[0] for s in LOCAL_SCENARIOS]}")


def _corruption_end(end_utc: str, dwell_s: int) -> str:
    """end_utc + dwell_s, ISO-formatted. dwell_s=0 ⇒ corruption_end == end."""
    return (dt.datetime.fromisoformat(end_utc) + dt.timedelta(seconds=dwell_s)).isoformat()


def run_attack_subprocess(
    script_path: str, fsw_host: str, attack_level: int,
    during_scenario: str, technique_id: str,
    corruption_dwell_s: int,
    extra_args: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Fire the attack script as a subprocess; return a manifest record."""
    extra_args = list(extra_args or [])
    # Route the detection log into logs/attack_runs/ (not the CWD) unless the
    # caller already passed --output. All 33 catalog scripts accept --output.
    if not dry_run and "--output" not in extra_args:
        os.makedirs(ATTACK_LOG_DIR, exist_ok=True)
        stem = os.path.splitext(os.path.basename(script_path))[0]
        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        extra_args += ["--output", os.path.join(ATTACK_LOG_DIR, f"{stem}_log_{ts}.csv")]
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
            "corruption_dwell_s": corruption_dwell_s,
            "corruption_end_utc": _corruption_end(end, corruption_dwell_s),
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
        "corruption_dwell_s": corruption_dwell_s,
        "corruption_end_utc": _corruption_end(end, corruption_dwell_s),
        "during_scenario": during_scenario, "exit_code": proc.returncode,
        "extra_args": extra_args,
        "stdout_lines": len(proc.stdout.splitlines()),
        "stderr_lines": len(proc.stderr.splitlines()),
    }


def run_attack_session(
    fsw_host: str, *, dry_run: bool, attack_key: str, attack_level: int,
    during: str, pre_s: int, post_s: int | None, attack_extra_args: list[str] | None,
    corruption_dwell_s: int | None = None,
    run_prereqs: bool = False,
) -> dict:
    if attack_key not in ATTACK_CATALOG:
        raise SystemExit(f"unknown attack: {attack_key}; valid={list(ATTACK_CATALOG)}")
    entry = ATTACK_CATALOG[attack_key]
    requires = entry.get("requires", [])
    if requires and not run_prereqs:
        msg = (
            f"\nERROR: {attack_key} requires the following prerequisite "
            f"attacks to be run first:\n"
        )
        for r in requires:
            msg += f"  - {r}\n"
        msg += (
            "The declared telemetry footprint will NOT manifest without them.\n"
            "Re-invoke with --chain to auto-run prerequisites at level 2 "
            "(setup, no cleanup) before the main attack, or manually fire "
            "the prerequisites against the same FSW first.\n"
        )
        raise SystemExit(msg)
    if corruption_dwell_s is None:
        corruption_dwell_s = entry.get("corruption_dwell_s", 0)
    # If caller passed post_s=None, honor the catalog's recommendation
    # (set per-attack when 240s isn't long enough to expose the signal),
    # else fall back to 240s — the all_modes_dwell mode-coverage floor.
    if post_s is None:
        post_s = entry.get("recommended_post_seconds_s", 240)
        if "recommended_post_seconds_s" in entry:
            print(f"  [catalog] using recommended post_seconds_s={post_s} for {attack_key}")
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

    # 2a. Prerequisite chain (each at level 2 = setup only, no cleanup).
    # These run BEFORE the main attack and inside the pre block window so the
    # main attack's labeled window stays isolated. Each prereq is logged to
    # the manifest as a separate attack record.
    for req_key in requires:
        if req_key not in ATTACK_CATALOG:
            raise SystemExit(f"chain references unknown prereq: {req_key}")
        req_entry = ATTACK_CATALOG[req_key]
        req_script = os.path.join(ATTACK_SCRIPTS_ROOT, req_entry["path"])
        print(f"\n──── chain prereq: {req_key} (level=2, setup) ────")
        req_rec = run_attack_subprocess(
            script_path=req_script,
            fsw_host=fsw_host,
            attack_level=2,
            during_scenario=scn_name,
            technique_id=req_entry["id"] + " [prereq]",
            corruption_dwell_s=req_entry.get("corruption_dwell_s", 0),
            extra_args=None,
            dry_run=dry_run,
        )
        manifest["attacks"].append(req_rec)

    # 2b. Main attack injection
    print(f"\n──── attack: {attack_key} (level={attack_level}) ────")
    rec = run_attack_subprocess(
        script_path=script_path,
        fsw_host=fsw_host,
        attack_level=attack_level,
        during_scenario=scn_name,
        technique_id=entry["id"],
        corruption_dwell_s=corruption_dwell_s,
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
    p.add_argument("--during", default="all_modes_dwell",
                   choices=[s[0] for s in LOCAL_SCENARIOS],
                   help="Which nominal scenario brackets the attack window. "
                        "Default 'all_modes_dwell' cycles INERTIAL → SUNSAFE → "
                        "BDOT → PASSIVE deterministically with 30s re-cmd "
                        "intervals — required for per-ADCS-mode IF training "
                        "since FSW autonomous behaviour leaves run_attack idle "
                        "in SUNSAFE otherwise (see 2026-05-15 routing audit). "
                        "Switch to nominal_ops/quiescent/etc. only when "
                        "deliberately holding mode constant.")
    p.add_argument("--pre-seconds", type=int, default=240,
                   help="Pre-attack scenario duration. Default 240s = 4 modes × "
                        "60s per all_modes_dwell phase. Shorter values truncate "
                        "the mode-coverage cycle.")
    p.add_argument("--post-seconds", type=int, default=None,
                   help="Post-attack scenario duration. If omitted, uses the "
                        "attack catalog's recommended_post_seconds_s, else 240s "
                        "(matches the all_modes_dwell mode-coverage requirement). "
                        "Pass explicitly to override.")
    p.add_argument("--corruption-dwell-s", type=int, default=None,
                   help="Override the catalog's corruption_dwell_s for this "
                        "attack. Detection signal for state-change attacks "
                        "lives in attack_end + dwell, not in the brief "
                        "subprocess window itself. Pass 0 to disable, or a "
                        "positive integer to extend the corruption window.")
    p.add_argument("--attack-extra-args", nargs=argparse.REMAINDER, default=[],
                   help="Trailing args passed verbatim to the attack script "
                        "(e.g. -- --duration 3.0 --rate-low 5)")
    p.add_argument("--chain", action="store_true",
                   help="If the chosen attack declares 'requires' in the "
                        "catalog, automatically run each prerequisite at "
                        "level 2 (setup, no cleanup) before the main attack. "
                        "Without --chain, an attack with unmet prereqs aborts "
                        "with a clear error.")
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
        corruption_dwell_s=args.corruption_dwell_s,
        run_prereqs=args.chain,
    )

    path = write_manifest(manifest, args.out_dir)
    n_scn = len(manifest["scenarios"])
    n_atk = len(manifest["attacks"])
    n_cmds = sum(s["n_commands"] for s in manifest["scenarios"])
    print(f"\nmanifest -> {path}")
    print(f"  scenario blocks: {n_scn}, attacks: {n_atk}, total nominal commands: {n_cmds}")


if __name__ == "__main__":
    main()
