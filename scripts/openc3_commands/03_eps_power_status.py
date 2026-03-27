"""
03 - EPS Power Status

Requests a housekeeping packet from the EPS (Electrical Power System)
and reads key power telemetry: battery voltage, temperatures, bus rails,
solar array, and all 8 switch states.
"""

from openc3.script import *  # type: ignore

print("=== EPS Power Status ===\n")

# Request fresh HK data
cmd("GENERIC_EPS_DEBUG GENERIC_EPS_REQ_HK")  # type: ignore
wait(2)  # type: ignore

# Battery
batt_v = tlm("GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM BATT_VOLTAGE")  # type: ignore
batt_t = tlm("GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM BATT_TEMPERATURE")  # type: ignore
print(f"Battery:       {batt_v} V,  {batt_t} C")

# Bus rails
bus_3v3 = tlm("GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM BUS_3P3V")  # type: ignore
bus_5v0 = tlm("GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM BUS_5P0V")  # type: ignore
bus_12v = tlm("GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM BUS_12V")  # type: ignore
print(f"Bus Rails:     3.3V={bus_3v3},  5.0V={bus_5v0},  12V={bus_12v}")

# Solar array
sa_v = tlm("GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM SA_VOLTAGE")  # type: ignore
sa_t = tlm("GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM SA_TEMPERATURE")  # type: ignore
print(f"Solar Array:   {sa_v} V,  {sa_t} C")

# EPS board temperature
eps_t = tlm("GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM EPS_TEMPERATURE")  # type: ignore
print(f"EPS Board:     {eps_t} C")

# Switch states
print("\nSwitch States:")
for i in range(8):
    state = tlm(f"GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM SWITCH_{i}_STATE")  # type: ignore
    voltage = tlm(f"GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM SW_{i}_VOLTAGE")  # type: ignore
    current = tlm(f"GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM SW_{i}_CURRENT")  # type: ignore
    print(f"  SW{i}: {state:3s}  V={voltage}  I={current}")

print("\nDone.")
