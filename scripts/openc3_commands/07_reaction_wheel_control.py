"""
07 - Reaction Wheel Control

Enables reaction wheels, commands a small torque to wheel 0,
reads back data, then disables the wheel.

Wheel numbers: 0, 1, 2
Torque units: 10^-4 Newton-meters (INT16)
"""

from openc3.script import *  # type: ignore

WHEEL = 0
TEST_TORQUE = 100  # 0.01 N-m

print(f"=== Reaction Wheel {WHEEL} Control Test ===\n")

# Enable wheel
print(f"Enabling wheel {WHEEL}...")
cmd(f"GENERIC_REACTION_WHEEL_DEBUG GENERIC_RW_ENABLE_CC with WHEEL_NUMBER {WHEEL}")  # type: ignore
wait(2)  # type: ignore

# Command a small torque
print(f"Commanding torque = {TEST_TORQUE} (10^-4 N-m)...")
cmd(f"GENERIC_REACTION_WHEEL_DEBUG GENERIC_RW_SET_TORQUE_CC with WHEEL_NUMBER {WHEEL}, TORQUE {TEST_TORQUE}")  # type: ignore
wait(3)  # type: ignore

# Read back data
cmd("GENERIC_REACTION_WHEEL_DEBUG GENERIC_RW_REQ_DATA_CC")  # type: ignore
wait(1)  # type: ignore

cmd_count = tlm("GENERIC_REACTION_WHEEL_DEBUG GENRW_HK_TLM_T ERROR_COUNT")  # type: ignore
err_count = tlm("GENERIC_REACTION_WHEEL_DEBUG GENRW_HK_TLM_T ERROR_COUNT")  # type: ignore
print(f"CMD_COUNT={cmd_count}, CMD_ERR_COUNT={err_count}")

# Zero torque and disable
print(f"Zeroing torque and disabling wheel {WHEEL}...")
cmd(f"GENERIC_REACTION_WHEEL_DEBUG GENERIC_RW_SET_TORQUE_CC with WHEEL_NUMBER {WHEEL}, TORQUE 0")  # type: ignore
wait(1)  # type: ignore
cmd(f"GENERIC_REACTION_WHEEL_DEBUG GENERIC_RW_DISABLE_CC with WHEEL_NUMBER {WHEEL}")  # type: ignore
wait(1)  # type: ignore

print("Done.")
