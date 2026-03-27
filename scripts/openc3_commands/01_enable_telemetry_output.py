"""
01 - Enable Telemetry Output

Enables the TO (Telemetry Output) application to start forwarding
telemetry packets from the flight software to OpenC3/COSMOS.
This is typically the FIRST command you send after the stack comes up.

Usage:
  - Script Runner: drop in targets/NOS3/procedures/, rebuild plugin, run from UI
  - Standalone:    export OPENC3_API_HOSTNAME=127.0.0.1
                   export OPENC3_API_PORT=2900
                   export OPENC3_API_PASSWORD=openc3service
                   python 01_enable_telemetry_output.py
"""

from openc3.script import *  # type: ignore

print("=== Enabling Telemetry Output ===")

# Enable TO output — sends telemetry to the OpenC3 DEBUG interface
cmd("CFS_DEBUG TO_ENABLE_OUTPUT with DEST_IP '127.0.0.1', DEST_PORT 5011")
wait(2)  # type: ignore

# Verify telemetry is flowing by checking a known component HK packet
cmd_count = tlm("CFS_DEBUG CFE_ES_HKPACKET CMDCOUNTER")  # type: ignore
print(f"CFE_ES command count: {cmd_count}")

print("Telemetry output ENABLED.")

print("Done.")
