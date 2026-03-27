"""
09 - Sample App Enable/Disable/Configure

Exercises the Sample application's full command set:
NOOP, enable, configure, request HK, request data, disable.

Useful as a template for testing any simple cFS app lifecycle.
"""

from openc3.script import *  # type: ignore

print("=== Sample App Lifecycle Test ===\n")

# NOOP
print("Sending NOOP...")
cmd("SAMPLE_DEBUG SAMPLE_NOOP_CC")  # type: ignore
wait(1)  # type: ignore

# Enable
print("Enabling Sample app...")
cmd("SAMPLE_DEBUG SAMPLE_ENABLE_CC")  # type: ignore
wait(1)  # type: ignore

# Configure with a test value
config_val = 42
print(f"Configuring device (DEVICE_CONFIG={config_val})...")
cmd(f"SAMPLE_DEBUG SAMPLE_CONFIG_CC with DEVICE_CONFIG {config_val}")  # type: ignore
wait(1)  # type: ignore

# Request HK and data
print("Requesting HK...")
cmd("SAMPLE_DEBUG SAMPLE_REQ_HK")  # type: ignore
wait(1)  # type: ignore

cmd_count = tlm("SAMPLE_DEBUG SAMPLE_HK_TLM CMD_COUNT")  # type: ignore
err_count = tlm("SAMPLE_DEBUG SAMPLE_HK_TLM CMD_ERR_COUNT")  # type: ignore
dev_count = tlm("SAMPLE_DEBUG SAMPLE_HK_TLM DEVICE_COUNT")  # type: ignore
print(f"  CMD_COUNT={cmd_count}, CMD_ERR_COUNT={err_count}, DEVICE_COUNT={dev_count}")

print("Requesting data packet...")
cmd("SAMPLE_DEBUG SAMPLE_REQ_DATA")  # type: ignore
wait(1)  # type: ignore

# Disable
print("Disabling Sample app...")
cmd("SAMPLE_DEBUG SAMPLE_DISABLE_CC")  # type: ignore
wait(1)  # type: ignore

# Reset counters
print("Resetting counters...")
cmd("SAMPLE_DEBUG SAMPLE_RST_COUNTERS_CC")  # type: ignore
wait(1)  # type: ignore

print("Done.")
