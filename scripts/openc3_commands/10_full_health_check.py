"""
10 - Full System Health Check

Comprehensive health check that:
  1. Enables telemetry output
  2. NOOPs every subsystem
  3. Reads EPS power status
  4. Reads ADCS mode/sensor data
  5. Reports a summary pass/fail

Intended as a post-startup smoke test for the entire NOS3 stack.
"""

from openc3.script import *  # type: ignore

errors = []

def check(label, func):
    """Run a check function; log and collect errors."""
    try:
        func()
        print(f"  [PASS] {label}")
    except Exception as e:
        errors.append((label, str(e)))
        print(f"  [FAIL] {label}: {e}")


print("=" * 60)
print("  NOS3 Full System Health Check")
print("=" * 60)

# --- Step 1: Enable TO ---
print("\n[1/5] Telemetry Output")
def enable_to():
    cmd("CFS_DEBUG TO_ENABLE_OUTPUT with DEST_IP '127.0.0.1', DEST_PORT 5011")  # type: ignore
    wait(2)  # type: ignore

check("TO Enable Output", enable_to)

# --- Step 2: NOOP all subsystems ---
print("\n[2/5] NOOP Commands")
NOOP_TARGETS = [
    ("CFS_DEBUG",                    "TO_NOOP"),
    ("SAMPLE_DEBUG",                 "SAMPLE_NOOP_CC"),
    ("GENERIC_EPS_DEBUG",            "GENERIC_EPS_NOOP_CC"),
    ("GENERIC_ADCS_DEBUG",           "GENERIC_ADCS_NOOP_CC"),
    ("GENERIC_REACTION_WHEEL_DEBUG", "GENERIC_RW_NOOP_CC"),
    ("GENERIC_THRUSTER_DEBUG",       "GENERIC_THRUSTER_NOOP_CC"),
    ("GENERIC_RADIO_DEBUG",          "GENERIC_RADIO_NOOP_CC"),
    ("GENERIC_MAG_DEBUG",            "GENERIC_MAG_NOOP_CC"),
    ("GENERIC_CSS_DEBUG",            "GENERIC_CSS_NOOP_CC"),
    ("GENERIC_FSS_DEBUG",            "GENERIC_FSS_NOOP_CC"),
    ("GENERIC_IMU_DEBUG",            "GENERIC_IMU_NOOP_CC"),
    ("GENERIC_TORQUER_DEBUG",        "GENERIC_TORQUER_NOOP_CC"),
    ("GENERIC_STAR_TRACKER_DEBUG",   "GENERIC_STAR_TRACKER_NOOP_CC"),
    ("NOVATEL_OEM615_DEBUG",         "NOVATEL_OEM615_NOOP_CC"),
]

for target, command in NOOP_TARGETS:
    def noop_fn(t=target, c=command):
        cmd(f"{t} {c}")  # type: ignore
        wait(0.3)  # type: ignore
    check(f"NOOP {target}", noop_fn)

# --- Step 3: EPS Power ---
print("\n[3/5] EPS Power Telemetry")
def eps_check():
    cmd("GENERIC_EPS_DEBUG GENERIC_EPS_REQ_HK")  # type: ignore
    wait(2)  # type: ignore
    batt = tlm("GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM BATT_VOLTAGE")  # type: ignore
    bus3 = tlm("GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM BUS_3P3V")  # type: ignore
    bus5 = tlm("GENERIC_EPS_DEBUG GENERIC_EPS_HK_TLM BUS_5P0V")  # type: ignore
    print(f"       Battery={batt}V, 3.3V={bus3}, 5.0V={bus5}")

check("EPS HK Read", eps_check)

# --- Step 4: ADCS Status ---
print("\n[4/5] ADCS Status")
def adcs_check():
    cmd("GENERIC_ADCS_DEBUG GENERIC_ADCS_REQ_HK")  # type: ignore
    wait(2)  # type: ignore
    cmd_cnt = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_HK_TLM CMD_COUNT")  # type: ignore
    err_cnt = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_HK_TLM CMD_ERR_COUNT")  # type: ignore
    print(f"       CMD_COUNT={cmd_cnt}, CMD_ERR_COUNT={err_cnt}")
    if err_cnt > 0:
        raise RuntimeError(f"ADCS has {err_cnt} command errors")

check("ADCS HK Read", adcs_check)

# --- Step 5: ADCS Sensor Data ---
print("\n[5/5] ADCS Sensor Data")
def adcs_sensor_check():
    cmd("GENERIC_ADCS_DEBUG GENERIC_ADCS_SEND_DI_CC")  # type: ignore
    wait(2)  # type: ignore
    bx = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_DI BVB_X")  # type: ignore
    by = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_DI BVB_Y")  # type: ignore
    bz = tlm("GENERIC_ADCS_DEBUG GENERIC_ADCS_DI BVB_Z")  # type: ignore
    print(f"       Mag_body=[{bx}, {by}, {bz}] T")

check("ADCS DI Sensor Read", adcs_sensor_check)

# --- Summary ---
print("\n" + "=" * 60)
if errors:
    print(f"  HEALTH CHECK COMPLETE: {len(errors)} FAILURE(S)")
    for label, err in errors:
        print(f"    - {label}: {err}")
else:
    print("  HEALTH CHECK COMPLETE: ALL PASSED")
print("=" * 60)
