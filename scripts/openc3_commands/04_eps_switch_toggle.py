"""
04 - EPS Switch Toggle

Demonstrates toggling an EPS power switch ON and OFF.
Turns switch 0 ON, waits, reads telemetry, then turns it OFF.

Useful for testing power distribution commands and verifying
that the EPS app is responding to switch commands.
"""

from openc3.script import *  # type: ignore

SWITCH = 0

print(f"=== EPS Switch {SWITCH} Toggle Test ===\n")

# Read initial state
cmd("GENERIC_EPS_DEBUG GENERIC_EPS_REQ_HK")  # type: ignore
wait(1)  # type: ignore
initial = tlm(f"GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM SWITCH_{SWITCH}_STATE")  # type: ignore
print(f"Initial state: {initial}")

# Turn ON
print(f"Commanding switch {SWITCH} ON...")
cmd(f"GENERIC_EPS_DEBUG GENERIC_EPS_SWITCH_CC with SWITCH_NUMBER {SWITCH}, STATE 0xAA")  # type: ignore
wait(2)  # type: ignore

cmd("GENERIC_EPS_DEBUG GENERIC_EPS_REQ_HK")  # type: ignore
wait(1)  # type: ignore
state_on = tlm(f"GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM SWITCH_{SWITCH}_STATE")  # type: ignore
print(f"After ON cmd:  {state_on}")

# Turn OFF
print(f"Commanding switch {SWITCH} OFF...")
cmd(f"GENERIC_EPS_DEBUG GENERIC_EPS_SWITCH_CC with SWITCH_NUMBER {SWITCH}, STATE 0x00")  # type: ignore
wait(2)  # type: ignore

cmd("GENERIC_EPS_DEBUG GENERIC_EPS_REQ_HK")  # type: ignore
wait(1)  # type: ignore
state_off = tlm(f"GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM SWITCH_{SWITCH}_STATE")  # type: ignore
print(f"After OFF cmd: {state_off}")

print("\nDone.")
