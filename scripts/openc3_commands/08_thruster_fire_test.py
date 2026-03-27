"""
08 - Thruster Fire Test

Enables the thruster app, commands a brief low-percentage thrust
on thruster 0, then disables.

Thruster numbers: 0-3
Percentage: 0-100
"""

from openc3.script import *  # type: ignore

THRUSTER = 0
PERCENT = 10  # 10% thrust

print(f"=== Thruster {THRUSTER} Fire Test ===\n")

# Enable thruster app
print("Enabling thruster subsystem...")
cmd("GENERIC_THRUSTER_DEBUG GENERIC_THRUSTER_ENABLE_CC")  # type: ignore
wait(2)  # type: ignore

# Command percentage thrust
print(f"Commanding thruster {THRUSTER} at {PERCENT}%...")
cmd(f"GENERIC_THRUSTER_DEBUG GENERIC_THRUSTER_PERCENTAGE_CC with THRUSTER_NUMBER {THRUSTER}, PERCENTAGE {PERCENT}")  # type: ignore
wait(3)  # type: ignore

# Read HK
cmd("GENERIC_THRUSTER_DEBUG GENERIC_THRUSTER_REQ_HK")  # type: ignore
wait(1)  # type: ignore

cmd_count = tlm("GENERIC_THRUSTER_DEBUG GENERIC_THRUSTER_HK_TLM CMD_COUNT")  # type: ignore
err_count = tlm("GENERIC_THRUSTER_DEBUG GENERIC_THRUSTER_HK_TLM CMD_ERR_COUNT")  # type: ignore
print(f"CMD_COUNT={cmd_count}, CMD_ERR_COUNT={err_count}")

# Zero thrust and disable
print("Zeroing thrust and disabling...")
cmd(f"GENERIC_THRUSTER_DEBUG GENERIC_THRUSTER_PERCENTAGE_CC with THRUSTER_NUMBER {THRUSTER}, PERCENTAGE 0")  # type: ignore
wait(1)  # type: ignore
cmd("GENERIC_THRUSTER_DEBUG GENERIC_THRUSTER_DISABLE_CC")  # type: ignore
wait(1)  # type: ignore

print("Done.")
