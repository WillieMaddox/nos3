"""
06 - ADCS Read Attitude Data

Requests the ADCS DI (Device Input) telemetry packet and reads
sensor data: magnetometer, fine sun sensor, and coarse sun sensors.
Also requests the AD (Attitude Determination) and GNC packets.

Useful for verifying that sensor data is flowing into the ADCS pipeline.
"""

from openc3.script import *  # type: ignore

print("=== ADCS Attitude & Sensor Data ===\n")

# Trigger fresh DI, AD, and GNC data
cmd("GENERIC_ADCS_DEBUG GENERIC_ADCS_SEND_DI_CC")  # type: ignore
wait(1)  # type: ignore
cmd("GENERIC_ADCS_DEBUG GENERIC_ADCS_SEND_AD_CC")  # type: ignore
wait(1)  # type: ignore
cmd("GENERIC_ADCS_DEBUG GENERIC_ADCS_SEND_GNC_CC")  # type: ignore
wait(1)  # type: ignore

# Read magnetometer data from DI packet
print("Magnetometer (body frame):")
bvb_x = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_DI BVB_X")  # type: ignore
bvb_y = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_DI BVB_Y")  # type: ignore
bvb_z = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_DI BVB_Z")  # type: ignore
print(f"  B_body = [{bvb_x}, {bvb_y}, {bvb_z}] T")

# Fine sun sensor
print("\nFine Sun Sensor (body frame):")
fss_valid = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_DI FSS_VALID")  # type: ignore
fss_x = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_DI FSS_SVB_X")  # type: ignore
fss_y = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_DI FSS_SVB_Y")  # type: ignore
fss_z = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_DI FSS_SVB_Z")  # type: ignore
print(f"  Valid={fss_valid}")
print(f"  Sun_body = [{fss_x}, {fss_y}, {fss_z}]")

# Coarse sun sensors (first 4)
print("\nCoarse Sun Sensors (percent on):")
for i in range(4):
    pct = tlm(f"GENERIC_ADCS_DEBUG GENERIC_ADCS_DI PERCENTON{i}")  # type: ignore
    print(f"  CSS{i}: {pct}%")

print("\nDone.")
