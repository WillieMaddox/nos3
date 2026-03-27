"""
05 - ADCS Set Mode

Cycles through all four ADCS (Attitude Determination and Control System)
GN&C modes: PASSIVE -> BDOT -> SUNSAFE -> INERTIAL, reading HK telemetry
after each transition.

Modes:
  0 = PASSIVE       (no active control)
  1 = BDOT_MODE     (detumble using magnetometer)
  2 = SUNSAFE_MODE  (point solar arrays at sun)
  3 = INERTIAL_MODE (hold a commanded quaternion)
"""

from openc3.script import *  # type: ignore

MODES = {
    0: "PASSIVE",
    1: "BDOT_MODE",
    2: "SUNSAFE_MODE",
    3: "INERTIAL_MODE",
}

print("=== ADCS Mode Cycling ===\n")

for mode_val, mode_name in MODES.items():
    print(f"Setting ADCS to {mode_name} (mode={mode_val})...")
    cmd(f"GENERIC_ADCS_DEBUG GENERIC_ADCS_SET_MODE_CC with GNC_MODE {mode_val}")  # type: ignore
    wait(3)  # type: ignore

    # Request and read HK
    cmd("GENERIC_ADCS_DEBUG GENERIC_ADCS_REQ_HK")  # type: ignore
    wait(1)  # type: ignore

    cmd_count = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_HK_TLM CMD_COUNT")  # type: ignore
    err_count = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_HK_TLM CMD_ERR_COUNT")  # type: ignore
    print(f"  CMD_COUNT={cmd_count}, CMD_ERR_COUNT={err_count}")

    if err_count > 0:
        print(f"  WARNING: errors detected after setting {mode_name}!")

# Return to PASSIVE
print("\nReturning to PASSIVE mode...")
cmd("GENERIC_ADCS_DEBUG GENERIC_ADCS_SET_MODE_CC with GNC_MODE 0")  # type: ignore
wait(1)  # type: ignore

print("Done.")
