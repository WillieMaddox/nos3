"""
Runner script: executes each of the 10 command scripts via the OpenC3 JSON-RPC API.
Runs outside Docker, talks to localhost:2900.
"""

import json
import time
import requests

BASE = "http://localhost:2900"
TOKEN = "openc3service"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": TOKEN,
}
SCOPE = "DEFAULT"

def rpc(method, params=None, id_=1):
    body = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": id_,
        "keyword_params": {"scope": SCOPE},
    }
    resp = requests.post(f"{BASE}/openc3-api/api", headers=HEADERS, json=body)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data.get("result")


def run_script(filename):
    """Start a script in Script Runner and wait for it to complete."""
    # Start the script
    resp = requests.post(
        f"{BASE}/script-api/scripts/MISSION/procedures/openc3_commands/{filename}/run",
        headers=HEADERS,
        json={"scope": SCOPE, "environment": []},
    )
    if resp.status_code != 200:
        print(f"  Failed to start: HTTP {resp.status_code} - {resp.text[:200]}")
        return False

    data = resp.json()
    script_id = data.get("id")
    if not script_id:
        print(f"  No script ID returned: {data}")
        return False

    print(f"  Started as script ID {script_id}")

    # Poll for completion
    for _ in range(120):  # up to 2 minutes
        time.sleep(2)
        status_resp = requests.get(
            f"{BASE}/script-api/running-script/{script_id}",
            headers=HEADERS,
            params={"scope": SCOPE},
        )
        if status_resp.status_code != 200:
            # Script may have finished and been cleaned up
            print(f"  Script {script_id} finished (status endpoint returned {status_resp.status_code})")
            break

        status_data = status_resp.json()
        state = status_data.get("state", "unknown")

        if state in ("stopped", "completed", "error", "paused"):
            print(f"  Final state: {state}")
            if state == "error":
                print(f"  Error details: {status_data.get('line', '?')}: {status_data.get('output', '')}")
                return False
            if state == "paused":
                print(f"  Script paused — check Script Runner UI")
                return False
            return True

    print(f"  Timed out waiting for script {script_id}")
    return False


SCRIPTS = [
    "01_enable_telemetry_output.py",
    "02_noop_all_subsystems.py",
    "03_eps_power_status.py",
    "04_eps_switch_toggle.py",
    "05_adcs_set_mode.py",
    "06_adcs_read_attitude.py",
    "07_reaction_wheel_control.py",
    "08_thruster_fire_test.py",
    "09_sample_app_config.py",
    "10_full_health_check.py",
]

if __name__ == "__main__":
    print("=" * 60)
    print("  Running all 10 OpenC3 command scripts")
    print("=" * 60)

    results = {}
    for script in SCRIPTS:
        print(f"\n--- {script} ---")
        ok = run_script(script)
        results[script] = "PASS" if ok else "FAIL"

    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    for script, result in results.items():
        print(f"  [{result:4s}] {script}")

    failed = sum(1 for v in results.values() if v == "FAIL")
    print(f"\n  {len(SCRIPTS) - failed}/{len(SCRIPTS)} passed")
