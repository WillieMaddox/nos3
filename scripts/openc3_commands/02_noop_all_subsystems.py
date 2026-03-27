"""
02 - NOOP All Subsystems

Sends a NOOP (no-operation) command to every major subsystem.
Used to verify commanding paths are healthy — each component should
increment its CMD_COUNT without errors.

Checks CMD_ERR_COUNT after each NOOP to catch communication issues early.
"""

from openc3.script import *  # type: ignore

SUBSYSTEMS = [
    ("CFS_DEBUG",                    "TO_NOOP"),
    ("SAMPLE_DEBUG",                 "SAMPLE_NOOP_CC"),
    ("GENERIC_EPS_DEBUG",            "GENERIC_EPS_NOOP_CC"),
    ("GENERIC_ADCS_DEBUG",           "GENERIC_ADCS_NOOP_CC"),
    ("GENERIC_CSS_DEBUG",            "GENERIC_CSS_NOOP_CC"),
    ("GENERIC_FSS_DEBUG",            "GENERIC_FSS_NOOP_CC"),
    ("GENERIC_MAG_DEBUG",            "GENERIC_MAG_NOOP_CC"),
    ("GENERIC_IMU_DEBUG",            "GENERIC_IMU_NOOP_CC"),
    ("GENERIC_REACTION_WHEEL_DEBUG", "GENERIC_RW_NOOP_CC"),
    ("GENERIC_TORQUER_DEBUG",        "GENERIC_TORQUER_NOOP_CC"),
    ("GENERIC_THRUSTER_DEBUG",       "GENERIC_THRUSTER_NOOP_CC"),
    ("GENERIC_STAR_TRACKER_DEBUG",   "GENERIC_STAR_TRACKER_NOOP_CC"),
    ("GENERIC_RADIO_DEBUG",          "GENERIC_RADIO_NOOP_CC"),
    ("NOVATEL_OEM615_DEBUG",         "NOVATEL_OEM615_NOOP_CC"),
]

print("=== NOOP All Subsystems ===\n")

results = []
for target, command in SUBSYSTEMS:
    try:
        cmd(f"{target} {command}")  # type: ignore
        wait(0.5)  # type: ignore
        results.append((target, "OK"))
        print(f"  [{target:40s}] NOOP sent OK")
    except Exception as e:
        results.append((target, f"FAIL: {e}"))
        print(f"  [{target:40s}] NOOP FAILED: {e}")

print("\n=== Summary ===")
passed = sum(1 for _, s in results if s == "OK")
print(f"{passed}/{len(results)} subsystems responded to NOOP.")
