#!/usr/bin/env bash
# nos3_onair.sh — NOS3 + OnAIR + Ollama + Elastic SIEM + Kibana demo harness
#
# Usage:
#   ./nos3_onair.sh [--mode MODE]
#
# Install-time modes (run once on a fresh laptop, in order):
#
#   setup    Install Docker, clone NOS3 + OnAIR, build, stage Python venvs.
#   demo     Switch ground system to OpenC3/COSMOS 5, rebuild, launch stack.
#   attack   Write + start advisory service (canned states + Ollama endpoint).
#   ollama   Validate Ollama, restart advisor with live LLM enabled.
#   siem     Start Elasticsearch + Kibana + Filebeat, launch CCSDS event poller.
#   kibana   Push data view, saved search, and dashboard to Kibana via API.
#   all      Runs setup -> demo -> attack -> ollama -> siem -> kibana. (default)
#
# Demo-day modes (stack already installed):
#
#   demoday  Ensure all services are up, set nominal, print talk track.
#   reset    Return advisory to nominal, stop advisor + NOS3 + SIEM stack.
#
# Env overrides:
#   OLLAMA_HOST=http://...  OLLAMA_MODEL=llama3   ./nos3_onair.sh --mode ollama
#   STACK_VERSION=9.3.2     BRIDGE_STATUS_URL=...  ./nos3_onair.sh --mode siem
#
# WSL2 note — do this once before running setup:
#   1) Enable systemd in /etc/wsl.conf:
#        [boot]
#        systemd=true
#      Then from PowerShell: wsl --shutdown
#   2) Set WSL2 memory in C:\Users\<you>\.wslconfig:
#        [wsl2]
#        memory=14GB
#      Then from PowerShell: wsl --shutdown
#   3) For Ollama GPU access: install Ollama natively on Windows.
#      WSL2 reaches it at http://localhost:11434 automatically.
#
# Requirements:
#   Ubuntu 22.04 or 24.04 inside WSL2.
#   30 GB free disk, 14 GB WSL2 memory allocation for full stack.

set -euo pipefail

# ─── user-adjustable settings ─────────────────────────────────────────────────
WORKDIR="${HOME}/demo"
NOS3_DIR="${WORKDIR}/nos3"
ONAIR_DIR="${WORKDIR}/OnAIR"
MISSION_XML="${NOS3_DIR}/cfg/nos3-mission.xml"
COSMOS_URL="http://localhost:2900"
COSMOS_WAIT_MAX=120
PYTHON_BIN="python3"

ADVISOR_DIR="${WORKDIR}/demo_advisor"
ADVISOR_PORT="8010"
ADVISOR_URL="http://localhost:${ADVISOR_PORT}"
ADVISOR_SCRIPT="${ADVISOR_DIR}/demo_advisor.py"
ADVISOR_LOG="${ADVISOR_DIR}/advisor.log"
STATE_JSON="${ADVISOR_DIR}/demo_state.json"

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma3}"

NOS3_LAUNCH_LOG="${WORKDIR}/nos3_launch.log"

SIEM_DIR="${WORKDIR}/siem"
STACK_VERSION="${STACK_VERSION:-9.3.2}"
BRIDGE_STATUS_URL="${BRIDGE_STATUS_URL:-http://localhost:8011/api/status}"
ES_URL="http://localhost:9200"
KIBANA_URL="http://localhost:5601"
EVENT_LOG="${SIEM_DIR}/logs/ccsds-events.ndjson"
POLLER_SCRIPT="${SIEM_DIR}/scripts/ccsds_event_poller.py"
POLLER_LOG="${SIEM_DIR}/poller.log"

# Fixed UUIDs — stable across re-runs so objects are updated, not duplicated
KIBANA_DATAVIEW_ID="ccsds-demo-dataview"
KIBANA_SEARCH_ID="ccsds-demo-savedsearch"
KIBANA_DASH_ID="ccsds-demo-dashboard"
# ──────────────────────────────────────────────────────────────────────────────

# ─── helpers ──────────────────────────────────────────────────────────────────
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }
die()   { echo "[ERROR] $*" >&2; exit 1; }
hr()    { echo "────────────────────────────────────────────────────────────"; }

LAUNCH_PID=""

_cleanup() {
  info "Signal received — shutting down."
  pkill -f "demo_advisor.py"       2>/dev/null || true
  pkill -f "ccsds_event_poller.py" 2>/dev/null || true
  [[ -n "${LAUNCH_PID}" ]] && kill "${LAUNCH_PID}" 2>/dev/null || true
  cd "${NOS3_DIR}" 2>/dev/null && make stop 2>/dev/null || true
  exit 130
}
trap '_cleanup' INT TERM

# ─── argument parsing ─────────────────────────────────────────────────────────
MODE="all"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)    MODE="$2"; shift 2 ;;
    --mode=*)  MODE="${1#--mode=}"; shift ;;
    -h|--help) grep '^# ' "$0" | sed 's/^# //'; exit 0 ;;
    *)         die "Unknown argument: $1. Use --help for usage." ;;
  esac
done

[[ "$MODE" =~ ^(setup|demo|attack|ollama|siem|kibana|all|demoday|reset)$ ]] \
  || die "Invalid mode '${MODE}'. Use --help for valid modes."

# ─── WSL2 detection ───────────────────────────────────────────────────────────
is_wsl2() { grep -qi 'microsoft' /proc/version 2>/dev/null; }

wsl2_windows_user() {
  # Returns the Windows username by reading the Windows environment via cmd.exe.
  # Falls back to empty string if not in WSL2 or cmd.exe unavailable.
  cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r\n' || true
}

# ─── shared helpers ───────────────────────────────────────────────────────────
docker_ready_check() {
  info "Waiting for Docker daemon (up to 60 s)"
  timeout 60 bash -c \
    'until docker info >/dev/null 2>&1; do sleep 2; done' \
    || die "Docker did not respond in 60 s. Start it manually and retry."
  info "Docker daemon ready."
}

poll_url() {
  # poll_url LABEL URL MAX_SECONDS
  local label="$1" url="$2" max="$3"
  info "Polling ${label} (up to ${max} s)"
  local elapsed=0
  while (( elapsed < max )); do
    curl -fsS "${url}" >/dev/null 2>&1 && { info "${label}: UP"; return 0; }
    sleep 5; elapsed=$(( elapsed + 5 ))
    info "  ...${elapsed}s"
  done
  warn "${label} did not respond within ${max} s."
  return 1
}

cosmos_ready_check() { poll_url "OpenC3/COSMOS" "${COSMOS_URL}" "${COSMOS_WAIT_MAX}" || true; }

advisor_ready_check() { curl -fsS "${ADVISOR_URL}/status" >/dev/null 2>&1; }

check_port() {
  # Warn if a TCP port is already bound — catches conflicts before docker compose up.
  local port="$1" label="$2"
  if ss -tlnH 2>/dev/null | awk '{print $4}' | grep -qE ":${port}$"; then
    warn "Port ${port} (${label}) is already in use — check for conflicts before continuing."
  fi
}

docker_group_reminder() {
  groups | grep -q docker && return
  warn "You are not in the docker group in this shell."
  if is_wsl2; then
    warn "In WSL2, run:  exec su -l \$USER"
    warn "or open a fresh Ubuntu terminal (newgrp persists only for subshells)."
  else
    warn "Run 'newgrp docker' or open a new terminal."
  fi
}

nos3_containers_running() {
  # Returns true if any NOS3/OpenC3 containers are up
  [[ $(docker ps --format '{{.Names}}' 2>/dev/null \
       | grep -cE 'nos3|openc3|cosmos' || true) -gt 0 ]]
}

ensure_nos3_running() {
  docker ps >/dev/null 2>&1 \
    || die "Docker not available. Run 'exec su -l \$USER' or open a new terminal."

  # Two-stage check: containers alive AND port responding
  if nos3_containers_running && curl -fsS "${COSMOS_URL}" >/dev/null 2>&1; then
    info "COSMOS already up at ${COSMOS_URL}"; return
  fi

  if nos3_containers_running; then
    warn "NOS3 containers are up but COSMOS not yet responding — waiting"
    cosmos_ready_check; return
  fi

  warn "NOS3 not running — attempting make launch"
  cd "${NOS3_DIR}"
  make launch > "${NOS3_LAUNCH_LOG}" 2>&1 &
  LAUNCH_PID=$!
  cosmos_ready_check

  if is_wsl2; then
    warn "WSL2: background processes (make launch, advisor, poller) are killed"
    warn "when all Ubuntu terminals close. Re-run --mode demoday after reopening."
  fi
}

ensure_advisor_running() {
  if advisor_ready_check; then
    info "Advisor already up at ${ADVISOR_URL}"; return
  fi
  warn "Advisor not reachable — starting"
  [ -f "${ADVISOR_SCRIPT}" ] \
    || die "${ADVISOR_SCRIPT} not found. Run --mode attack first."
  restart_advisor
}

ensure_siem_running() {
  if curl -fsS "${ES_URL}" >/dev/null 2>&1 \
      && curl -fsS "${KIBANA_URL}/api/status" >/dev/null 2>&1; then
    info "Elastic SIEM stack already up."; return
  fi
  warn "SIEM stack not reachable — starting"
  [ -f "${SIEM_DIR}/docker-compose.yml" ] \
    || die "${SIEM_DIR}/docker-compose.yml not found. Run --mode siem first."
  cd "${SIEM_DIR}"
  docker compose up -d
  poll_url "Elasticsearch" "${ES_URL}"               120 || warn "ES slow to start"
  poll_url "Kibana"        "${KIBANA_URL}/api/status" 180 || warn "Kibana slow to start"
}

kibana_post() {
  # kibana_post DESCRIPTION ENDPOINT PAYLOAD_FILE
  local desc="$1" endpoint="$2" payload="$3"
  info "Pushing: ${desc}"
  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${KIBANA_URL}${endpoint}" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    --data-binary "@${payload}")
  case "${http_code}" in
    200|201) info "  → ${http_code} OK" ;;
    409)     info "  → 409 already exists (overwrite flag should handle this)" ;;
    *)       warn "  → ${http_code} unexpected for ${desc} — check Kibana logs" ;;
  esac
}

# ─── advisor writer / launcher ────────────────────────────────────────────────
write_advisor() {
  info "Writing advisory service: ${ADVISOR_SCRIPT}"
  cat > "${ADVISOR_SCRIPT}" <<'PYEOF'
"""
demo_advisor.py — NOS3 attack/defend + Ollama advisory service.

Endpoints:
  GET  /status    Current advisory state (JSON)
  GET  /llm       Ask Ollama about the current state (graceful error if unavailable)
  POST /nominal   Reset to nominal
  POST /attack    Inject attack scenario
  POST /defend    Transition to recovery
  POST /llm       Same as GET /llm

Upgrade path:
  Replace STATES dict values with real OnAIR plugin output.
  Replace ask_ollama() body with a call to your inference API for live telemetry.
"""

import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

STATE_JSON   = os.environ.get("STATE_JSON",   "demo_state.json")
HOST         = "0.0.0.0"
PORT         = int(os.environ.get("ADVISOR_PORT", "8010"))
OLLAMA_HOST  = os.environ.get("OLLAMA_HOST",  "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3")

STATES = {
    "nominal": {
        "phase":              "nominal",
        "spacecraft_mode":    "SAFE",
        "radio_link":         "ENABLED",
        "anomaly_score":      0.03,
        "event":              "none",
        "recommended_action": "continue nominal ops",
        "explanation":        "System appears nominal.",
    },
    "attack": {
        "phase":              "attack",
        "spacecraft_mode":    "SCIENCE",
        "radio_link":         "DEGRADED",
        "anomaly_score":      0.92,
        "event":              "telemetry_inconsistency_and_link_degradation",
        "recommended_action": "return spacecraft to SAFE mode and verify Radio path",
        "explanation": (
            "Advisory: telemetry behavior is inconsistent with current mode "
            "and link state. Possible uplink injection or radio subsystem fault."
        ),
    },
    "defend": {
        "phase":              "defend",
        "spacecraft_mode":    "SAFE",
        "radio_link":         "RECOVERING",
        "anomaly_score":      0.17,
        "event":              "recovery_in_progress",
        "recommended_action": (
            "hold SAFE mode, re-enable telemetry output, "
            "confirm housekeeping stability"
        ),
        "explanation": (
            "Recovery action taken. Continue monitoring before resuming science ops."
        ),
    },
}

def load_state():
    with open(STATE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_JSON, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def ask_ollama(state: dict) -> dict:
    system_prompt = (
        "You are a spacecraft anomaly assistant for a NOS3/COSMOS demo. "
        "Respond in JSON with exactly four keys: "
        "summary, likely_cause, immediate_action, confidence. "
        "Keep each value to one concise mission-ops sentence."
    )
    payload = json.dumps({
        "model":  OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": json.dumps(state)},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data    = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "").strip()
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = {"raw": content}
            return {"ok": True, "model": OLLAMA_MODEL, "response": parsed}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTPError {exc.code}: {exc.reason}"}
    except Exception as exc:        # noqa: BLE001
        return {"ok": False, "error": str(exc)}

class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, code=200):
        body = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_llm(self):
        result = ask_ollama(load_state())
        self._send_json(result, 200 if result.get("ok") else 502)

    def do_GET(self):
        if self.path in ("/", "/status", "/advisory"):
            self._send_json(load_state())
        elif self.path == "/llm":
            self._handle_llm()
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        key = self.path.lstrip("/")
        if key in STATES:
            state = STATES[key].copy()
            save_state(state)
            return self._send_json(state)
        if self.path == "/llm":
            return self._handle_llm()
        self._send_json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        return

if __name__ == "__main__":
    print(f"Demo advisor  →  http://{HOST}:{PORT}", flush=True)
    print(f"Ollama target →  {OLLAMA_HOST}  model={OLLAMA_MODEL}", flush=True)
    HTTPServer((HOST, PORT), Handler).serve_forever()
PYEOF
}

restart_advisor() {
  info "Stopping any running advisor instance"
  pkill -f "demo_advisor.py" 2>/dev/null || true
  sleep 1
  STATE_JSON="${STATE_JSON}" \
  ADVISOR_PORT="${ADVISOR_PORT}" \
  OLLAMA_HOST="${OLLAMA_HOST}" \
  OLLAMA_MODEL="${OLLAMA_MODEL}" \
    nohup "${PYTHON_BIN}" "${ADVISOR_SCRIPT}" > "${ADVISOR_LOG}" 2>&1 &
  sleep 2
  advisor_ready_check \
    || { cat "${ADVISOR_LOG}"; die "Advisory service failed to start."; }
  info "Advisor listening on :${ADVISOR_PORT}"
}

# ─── SIEM writers ─────────────────────────────────────────────────────────────
write_siem_compose() {
  info "Writing ${SIEM_DIR}/docker-compose.yml"
  cat > "${SIEM_DIR}/docker-compose.yml" <<EOF
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:${STACK_VERSION}
    container_name: demo-elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - xpack.security.enrollment.enabled=false
      - ES_JAVA_OPTS=-Xms1g -Xmx1g
    ports:
      - "9200:9200"
    volumes:
      - esdata:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:9200 >/dev/null || exit 1"]
      interval: 15s
      timeout: 10s
      retries: 20

  kibana:
    image: docker.elastic.co/kibana/kibana:${STACK_VERSION}
    container_name: demo-kibana
    depends_on:
      elasticsearch:
        condition: service_healthy
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
      - XPACK_SECURITY_ENABLED=false
    ports:
      - "5601:5601"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:5601/api/status >/dev/null || exit 1"]
      interval: 20s
      timeout: 10s
      retries: 30

  filebeat:
    image: docker.elastic.co/beats/filebeat:${STACK_VERSION}
    container_name: demo-filebeat
    user: root
    depends_on:
      elasticsearch:
        condition: service_healthy
      kibana:
        condition: service_healthy
    command: ["filebeat", "-e", "--strict.perms=false"]
    volumes:
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - ./logs:/demo-logs:ro
      - ./filebeat-data:/usr/share/filebeat/data
    restart: unless-stopped

volumes:
  esdata:
EOF
}

write_filebeat_config() {
  info "Writing ${SIEM_DIR}/filebeat.yml"
  cat > "${SIEM_DIR}/filebeat.yml" <<'EOF'
filebeat.inputs:
  - type: filestream
    id: ccsds-demo-events
    enabled: true
    paths:
      - /demo-logs/ccsds-events.ndjson
    parsers:
      - ndjson:
          overwrite_keys: true
          add_error_key: true

processors:
  - add_fields:
      target: labels
      fields:
        demo_stack: "nos3-openc3-onair-ollama"
        telemetry_format: "ccsds"
        course_use: "student_siem_demo"

setup.kibana:
  host: "kibana:5601"

output.elasticsearch:
  hosts: ["http://elasticsearch:9200"]
  index: "ccsds-demo-events-%{+yyyy.MM.dd}"

setup.template.name: "ccsds-demo-events"
setup.template.pattern: "ccsds-demo-events-*"

logging.level: info
EOF
}

write_poller() {
  info "Writing CCSDS event poller: ${POLLER_SCRIPT}"
  cat > "${POLLER_SCRIPT}" <<'PYEOF'
"""
ccsds_event_poller.py
Polls the NOS3 demo bridge status endpoint and appends ECS-style NDJSON
events to disk for Filebeat -> Elasticsearch ingestion.

Change-detection: only writes a new event when the state signature changes.

Upgrade path:
  Replace safe_get() target with a real OpenC3 COSMOS API query or an OnAIR
  plugin output feed to move from demo bridge to live telemetry.
"""

import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

BRIDGE_STATUS_URL = os.environ.get(
    "BRIDGE_STATUS_URL", "http://localhost:8011/api/status"
)
EVENT_LOG = os.environ.get(
    "EVENT_LOG", os.path.expanduser("~/demo/siem/logs/ccsds-events.ndjson")
)
POLL_SECONDS = float(os.environ.get("POLL_SECONDS", "1.0"))

last_signature = None


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_event(status: dict) -> dict:
    telemetry      = status.get("telemetry", {})
    anomaly        = status.get("anomaly",   {})
    sparta         = status.get("sparta",    {})
    recommendation = status.get("recommendation", "")

    event_kind = anomaly.get("event", "none")
    severity   = sparta.get("severity", "normal")
    sev_int    = {"normal": 1, "high": 5}.get(severity, 8)

    return {
        "@timestamp": iso_now(),
        "event": {
            "kind":     "event",
            "category": ["network", "intrusion_detection", "configuration"],
            "type":     ["info"] if event_kind == "none" else ["indicator"],
            "reason":   event_kind,
            "severity": sev_int,
        },
        "ecs":     {"version": "8.11.0"},
        "service": {
            "name":    "nos3-demo-bridge",
            "type":    "spacecraft-telemetry",
            "version": "1.0",
        },
        "observer": {"name": "OpenC3/OnAIR Demo", "type": "siem-pipeline"},
        "labels": {
            "mission_mode":     str(telemetry.get("mode",   "UNKNOWN")),
            "telemetry_target": str(telemetry.get("target", "UNKNOWN")),
            "telemetry_packet": str(telemetry.get("packet", "UNKNOWN")),
            "sparta_severity":  severity,
        },
        "ccsds": {
            "target":               telemetry.get("target"),
            "packet":               telemetry.get("packet"),
            "mode":                 telemetry.get("mode"),
            "hk_temp":              telemetry.get("hk_temp"),
            "cmd_count":            telemetry.get("cmd_count"),
            "err_count":            telemetry.get("err_count"),
            "radio_output_enabled": telemetry.get("radio_output_enabled"),
        },
        "anomaly": anomaly,
        "sparta":  sparta,
        "message": recommendation or f"CCSDS status event: {event_kind}",
    }


def error_event(reason: str, message: str, severity: int = 6) -> dict:
    return {
        "@timestamp": iso_now(),
        "event": {
            "kind":     "event",
            "category": ["network"],
            "type":     ["error"],
            "reason":   reason,
            "severity": severity,
        },
        "ecs":     {"version": "8.11.0"},
        "service": {"name": "nos3-demo-bridge"},
        "message": message,
    }


def append_event(ev: dict) -> None:
    os.makedirs(os.path.dirname(EVENT_LOG), exist_ok=True)
    with open(EVENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev) + "\n")


def state_signature(status: dict) -> tuple:
    t = status.get("telemetry", {})
    a = status.get("anomaly",   {})
    return (
        t.get("target"), t.get("packet"), t.get("mode"),
        t.get("cmd_count"), t.get("err_count"), t.get("radio_output_enabled"),
        a.get("event"), round(float(a.get("score", 0.0)), 3),
    )


print(f"CCSDS poller started. Bridge: {BRIDGE_STATUS_URL}", flush=True)
print(f"Event log: {EVENT_LOG}", flush=True)

while True:
    try:
        status = safe_get(BRIDGE_STATUS_URL)
        sig    = state_signature(status)
        if sig != last_signature:
            append_event(build_event(status))
            last_signature = sig
    except urllib.error.URLError as exc:
        append_event(error_event("bridge_unreachable", f"Bridge unreachable: {exc}"))
    except Exception as exc:          # noqa: BLE001
        append_event(error_event("poller_exception", f"Poller exception: {exc}", severity=7))

    time.sleep(POLL_SECONDS)
PYEOF
  chmod +x "${POLLER_SCRIPT}"
}

# ─── Kibana asset writer (Python-generated JSON to avoid heredoc encoding bugs)
write_kibana_assets() {
  local asset_dir="${SIEM_DIR}/kibana-assets"
  mkdir -p "${asset_dir}"

  # All three files are built by Python's json module so panelsJSON and other
  # nested-JSON string fields are always correctly encoded.  The function prints
  # the asset directory path on stdout for the caller.
  "${PYTHON_BIN}" - "${asset_dir}" \
      "${KIBANA_DATAVIEW_ID}" "${KIBANA_SEARCH_ID}" "${KIBANA_DASH_ID}" <<'PYEOF'
import json
import sys
import os

asset_dir, dv_id, search_id, dash_id = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

# ── 1) Data view ──────────────────────────────────────────────────────────────
dataview = {
    "data_view": {
        "id":            dv_id,
        "title":         "ccsds-demo-events-*",
        "timeFieldName": "@timestamp",
        "name":          "CCSDS Demo Events",
    },
    "override": True,
}

# ── 2) Saved search ───────────────────────────────────────────────────────────
search_source = json.dumps({
    "index":  dv_id,
    "query":  {"query": "", "language": "kuery"},
    "filter": [],
})
search_obj = {
    "attributes": {
        "title":       "CCSDS Recent Events",
        "description": (
            "All CCSDS demo events — sorted newest first. "
            "Filter by event.reason, labels.mission_mode, or "
            "labels.sparta_severity to investigate attack/defend transitions."
        ),
        "hits":    0,
        "columns": [
            "@timestamp",
            "event.reason",
            "labels.mission_mode",
            "labels.sparta_severity",
            "event.severity",
            "ccsds.mode",
            "ccsds.err_count",
            "ccsds.radio_output_enabled",
            "message",
        ],
        "sort":    [["@timestamp", "desc"]],
        "version": 1,
        "kibanaSavedObjectMeta": {"searchSourceJSON": search_source},
    },
    "references": [{
        "id":   dv_id,
        "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
        "type": "index-pattern",
    }],
}

# ── 3) Dashboard panels ───────────────────────────────────────────────────────
def lens_layer(index_id, columns):
    """Return a minimal Lens indexpattern layer dict."""
    return {
        "indexPatternId": index_id,
        "columnOrder":    list(columns.keys()),
        "columns":        columns,
    }

panel_a_attrs = {
    "title":              "Event Count Over Time",
    "description":        "Rate of CCSDS state-change events. Spikes mark attack and defend transitions.",
    "visualizationType":  "lnsXY",
    "state": {
        "datasourceStates": {
            "indexpattern": {
                "layers": {
                    "layer1": lens_layer(dv_id, {
                        "col-time": {
                            "dataType": "date", "isBucketed": True,
                            "label": "@timestamp", "operationType": "date_histogram",
                            "params": {"interval": "auto"}, "sourceField": "@timestamp",
                        },
                        "col-count": {
                            "dataType": "number", "isBucketed": False,
                            "label": "Event count", "operationType": "count",
                        },
                    })
                }
            }
        },
        "visualization": {
            "layers": [{"layerId": "layer1", "seriesType": "line",
                        "xAccessor": "col-time", "accessors": ["col-count"]}],
            "legend":      {"isVisible": True, "position": "right"},
            "valueLabels": "hide",
        },
        "query":   {"language": "kuery", "query": ""},
        "filters": [],
    },
    "references": [{"id": dv_id, "name": "indexpattern-datasource-layer-layer1", "type": "index-pattern"}],
}

panel_b_attrs = {
    "title":             "Anomaly Severity Breakdown",
    "description":       "Distribution of event.severity values. High slices indicate attack events.",
    "visualizationType": "lnsPie",
    "state": {
        "datasourceStates": {
            "indexpattern": {
                "layers": {
                    "layer1": lens_layer(dv_id, {
                        "col-sev": {
                            "dataType": "number", "isBucketed": True,
                            "label": "Severity", "operationType": "terms",
                            "params": {"size": 10,
                                       "orderBy": {"type": "column", "columnId": "col-count"},
                                       "orderDirection": "desc"},
                            "sourceField": "event.severity",
                        },
                        "col-count": {
                            "dataType": "number", "isBucketed": False,
                            "label": "Count", "operationType": "count",
                        },
                    })
                }
            }
        },
        "visualization": {
            "shape": "donut",
            "layers": [{"layerId": "layer1",
                        "primaryGroups": ["col-sev"], "metrics": ["col-count"]}],
            "legend": {"isVisible": True, "position": "right"},
        },
        "query":   {"language": "kuery", "query": ""},
        "filters": [],
    },
    "references": [{"id": dv_id, "name": "indexpattern-datasource-layer-layer1", "type": "index-pattern"}],
}

panel_c_attrs = {
    "title":             "Mission Mode Breakdown",
    "description":       "Event counts grouped by labels.mission_mode. Shows SAFE vs SCIENCE shift during attack.",
    "visualizationType": "lnsXY",
    "state": {
        "datasourceStates": {
            "indexpattern": {
                "layers": {
                    "layer1": lens_layer(dv_id, {
                        "col-mode": {
                            "dataType": "string", "isBucketed": True,
                            "label": "Mission Mode", "operationType": "terms",
                            "params": {"size": 10,
                                       "orderBy": {"type": "column", "columnId": "col-count"},
                                       "orderDirection": "desc"},
                            "sourceField": "labels.mission_mode",
                        },
                        "col-count": {
                            "dataType": "number", "isBucketed": False,
                            "label": "Count", "operationType": "count",
                        },
                    })
                }
            }
        },
        "visualization": {
            "layers": [{"layerId": "layer1", "seriesType": "bar",
                        "xAccessor": "col-mode", "accessors": ["col-count"]}],
            "legend":      {"isVisible": False},
            "valueLabels": "inside",
        },
        "query":   {"language": "kuery", "query": ""},
        "filters": [],
    },
    "references": [{"id": dv_id, "name": "indexpattern-datasource-layer-layer1", "type": "index-pattern"}],
}

# panelsJSON must be a JSON-encoded *string* (Kibana saved object format).
panels = [
    {
        "version":     "8.11.0",
        "type":        "lens",
        "gridData":    {"x": 0,  "y": 0,  "w": 24, "h": 15, "i": "panel-A"},
        "panelIndex":  "panel-A",
        "embeddableConfig": {"attributes": panel_a_attrs},
    },
    {
        "version":    "8.11.0",
        "type":       "lens",
        "gridData":   {"x": 24, "y": 0,  "w": 24, "h": 15, "i": "panel-B"},
        "panelIndex": "panel-B",
        "embeddableConfig": {"attributes": panel_b_attrs},
    },
    {
        "version":    "8.11.0",
        "type":       "lens",
        "gridData":   {"x": 0,  "y": 15, "w": 24, "h": 15, "i": "panel-C"},
        "panelIndex": "panel-C",
        "embeddableConfig": {"attributes": panel_c_attrs},
    },
    {
        "version":       "8.11.0",
        "type":          "search",
        "gridData":      {"x": 24, "y": 15, "w": 24, "h": 15, "i": "panel-D"},
        "panelIndex":    "panel-D",
        "embeddableConfig": {"enhancements": {}},
        "savedObjectId": search_id,
    },
]

dash_search_source = json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})

dashboard = {
    "attributes": {
        "title":       "CCSDS Mission Security Overview",
        "description": (
            "NOS3 + OpenC3 + OnAIR demo — "
            "attack, anomaly, and recovery timeline for classroom use."
        ),
        "panelsJSON":  json.dumps(panels),          # correctly encoded string
        "timeRestore": False,
        "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "hidePanelTitles": False}),
        "version":     1,
        "kibanaSavedObjectMeta": {"searchSourceJSON": dash_search_source},
    },
    "references": [
        {"id": dv_id,    "name": "panel-A:indexpattern-datasource-layer-layer1", "type": "index-pattern"},
        {"id": dv_id,    "name": "panel-B:indexpattern-datasource-layer-layer1", "type": "index-pattern"},
        {"id": dv_id,    "name": "panel-C:indexpattern-datasource-layer-layer1", "type": "index-pattern"},
        {"id": search_id,"name": "panel-D",                                      "type": "search"},
    ],
}

def write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    print(f"  wrote {path}")

write(os.path.join(asset_dir, "dataview.json"),    dataview)
write(os.path.join(asset_dir, "savedsearch.json"), search_obj)
write(os.path.join(asset_dir, "dashboard.json"),   dashboard)
print(asset_dir)   # last line: caller captures this as the asset_dir path
PYEOF

  # Return the asset directory path — capture the last line of Python stdout
  "${PYTHON_BIN}" - "${asset_dir}" \
      "${KIBANA_DATAVIEW_ID}" "${KIBANA_SEARCH_ID}" "${KIBANA_DASH_ID}" \
      2>/dev/null <<'PYEOF' | tail -1
import sys; print(sys.argv[1])
PYEOF
}

# ─── phase: preflight ─────────────────────────────────────────────────────────
preflight() {
  hr; info "Preflight checks"; hr

  # ── disk ───────────────────────────────────────────────────────────────────
  local free_gb
  free_gb=$(( $(df --output=avail -k "${HOME}" | tail -1) / 1024 / 1024 ))
  (( free_gb >= 30 )) \
    && info "Disk OK: ~${free_gb} GB free." \
    || warn "Only ~${free_gb} GB free — full stack needs ~30 GB."

  # ── RAM — in WSL2 /proc/meminfo shows the *allocated* WSL2 memory, not
  #   Windows total. A user with 32 GB Windows RAM but default .wslconfig
  #   gets only ~8 GB allocated, so we warn AND check .wslconfig. ───────────
  local mem_gb
  mem_gb=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024 / 1024 ))
  if (( mem_gb >= 14 )); then
    info "RAM OK: ~${mem_gb} GB allocated to this environment."
  else
    warn "Only ~${mem_gb} GB RAM visible — NOS3 + Elastic need at least 14 GB."
    if is_wsl2; then
      local win_user wslconfig
      win_user=$(wsl2_windows_user)
      wslconfig="/mnt/c/Users/${win_user}/.wslconfig"
      if [[ -n "${win_user}" ]] && grep -qi 'memory' "${wslconfig}" 2>/dev/null; then
        info ".wslconfig memory setting found at ${wslconfig}."
      else
        warn "No .wslconfig memory limit found."
        warn "Create C:\\Users\\${win_user}\\.wslconfig with:"
        warn "  [wsl2]"
        warn "  memory=14GB"
        warn "Then from PowerShell: wsl --shutdown"
        warn "Continuing — but expect OOM kills during the demo."
      fi
    fi
  fi

  # ── systemd (WSL2 only) ────────────────────────────────────────────────────
  if is_wsl2; then
    if grep -q 'systemd=true' /etc/wsl.conf 2>/dev/null; then
      info "WSL2 systemd: enabled."
    else
      warn "WSL2 systemd not enabled. Docker will need manual start."
      warn "For a smoother experience add to /etc/wsl.conf:"
      warn "  [boot]"
      warn "  systemd=true"
      warn "Then from PowerShell: wsl --shutdown"
    fi
  fi

  # ── port conflicts ─────────────────────────────────────────────────────────
  info "Checking for port conflicts"
  check_port 2900 "COSMOS/OpenC3"
  check_port "${ADVISOR_PORT}" "Advisor"
  check_port 9200 "Elasticsearch"
  check_port 5601 "Kibana"
}

# ─── phase: setup ─────────────────────────────────────────────────────────────
phase_setup() {
  hr; info "PHASE: setup"; hr

  mkdir -p "${WORKDIR}"

  info "Updating apt and installing baseline packages"
  sudo apt-get update -qq
  sudo apt-get install -y \
    ca-certificates curl git make \
    python3-pip python3-venv python3-dev \
    lsb-release gnupg iproute2

  info "Configuring Docker apt source"
  sudo install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      -o /etc/apt/keyrings/docker.asc
  fi
  sudo chmod a+r /etc/apt/keyrings/docker.asc

  local ARCH CODENAME
  ARCH="$(dpkg --print-architecture)"
  CODENAME="$(. /etc/os-release; echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")"
  echo \
    "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  info "Installing Docker engine and compose plugin"
  sudo apt-get update -qq
  sudo apt-get install -y \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

  info "Adding ${USER} to docker group"
  sudo groupadd docker 2>/dev/null || true
  sudo usermod -aG docker "$USER" || true

  # ── Docker service — WSL2-aware ────────────────────────────────────────────
  info "Starting Docker service"
  if is_wsl2; then
    if grep -q 'systemd=true' /etc/wsl.conf 2>/dev/null \
        && systemctl is-system-running >/dev/null 2>&1; then
      sudo systemctl enable --now docker || true
    else
      # No systemd or degraded — use SysV init
      sudo service docker start || true
    fi
  else
    sudo systemctl enable --now docker || true
  fi
  docker --version
  docker compose version

  docker_group_reminder

  # ── NOS3 ───────────────────────────────────────────────────────────────────
  info "Cloning NOS3 (shallow)"
  if [ ! -d "${NOS3_DIR}" ]; then
    git clone --depth 1 https://github.com/nasa/nos3.git "${NOS3_DIR}"
  else
    info "NOS3 already cloned — pulling latest"
    git -C "${NOS3_DIR}" pull
  fi
  git -C "${NOS3_DIR}" submodule update --init --recursive

  info "Creating NOS3 Python venv (optional tooling)"
  cd "${NOS3_DIR}"
  [ -d ".venv" ] || ${PYTHON_BIN} -m venv .venv

  docker_ready_check
  info "Running NOS3 prep (pulls Docker images — may take a while)"
  make prep
  info "Building NOS3"
  make

  # ── OnAIR ──────────────────────────────────────────────────────────────────
  info "Cloning OnAIR (shallow)"
  cd "${WORKDIR}"
  if [ ! -d "${ONAIR_DIR}" ]; then
    git clone --depth 1 https://github.com/nasa/OnAIR.git "${ONAIR_DIR}"
  else
    info "OnAIR already cloned — pulling latest"
    git -C "${ONAIR_DIR}" pull
  fi
  cd "${ONAIR_DIR}"
  [ -d ".venv" ] || ${PYTHON_BIN} -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  [ -f requirements.txt ] \
    || die "OnAIR requirements.txt not found — repo layout may have changed."
  pip install --upgrade pip -q
  pip install -r requirements.txt -q
  python -m pytest tests/ -q || true
  deactivate

  info "Setup complete."
}

# ─── phase: demo ──────────────────────────────────────────────────────────────
phase_demo() {
  hr; info "PHASE: demo"; hr

  [ -d "${NOS3_DIR}" ]    || die "NOS3 not found. Run --mode setup first."
  [ -f "${MISSION_XML}" ] || die "Mission file not found: ${MISSION_XML}"

  docker_group_reminder

  info "Current ground system setting:"
  grep -n 'gsw=' "${MISSION_XML}" || true

  info "Backing up mission XML"
  cp "${MISSION_XML}" "${MISSION_XML}.bak.$(date +%Y%m%d%H%M%S)"

  info "Forcing gsw to openc3"
  sed -i \
    -e 's/gsw="cosmos"/gsw="openc3"/g' \
    -e 's/gsw="yamcs"/gsw="openc3"/g' \
    -e 's/gsw="fprime"/gsw="openc3"/g' \
    "${MISSION_XML}"
  grep -n 'gsw="openc3"' "${MISSION_XML}" \
    || die "Failed to set gsw=\"openc3\". Check ${MISSION_XML} manually."

  cd "${NOS3_DIR}"
  info "Stopping any previously running stack"
  make stop-gsw 2>/dev/null || true
  make stop     2>/dev/null || true
  make clean    2>/dev/null || true

  docker_ready_check
  info "Re-running prep after GSW change"
  make prep
  info "Building NOS3"
  make

  info "Launching NOS3 stack in background"
  make launch > "${NOS3_LAUNCH_LOG}" 2>&1 &
  LAUNCH_PID=$!

  cosmos_ready_check
  info "Running containers:"; docker ps || true
  info "Demo phase complete."
}

# ─── phase: attack ────────────────────────────────────────────────────────────
phase_attack() {
  hr; info "PHASE: attack harness"; hr

  [ -d "${NOS3_DIR}" ]  || die "NOS3 not found. Run --mode setup first."
  [ -d "${ONAIR_DIR}" ] || die "OnAIR not found. Run --mode setup first."

  mkdir -p "${ADVISOR_DIR}"

  info "Writing initial demo state"
  cat > "${STATE_JSON}" <<'JSON'
{
  "phase": "nominal",
  "spacecraft_mode": "SAFE",
  "radio_link": "ENABLED",
  "anomaly_score": 0.03,
  "event": "none",
  "recommended_action": "continue nominal ops",
  "explanation": "System appears nominal."
}
JSON

  write_advisor

  docker ps >/dev/null 2>&1 \
    || die "Docker not available. Run 'exec su -l \$USER' or open a new terminal."

  if ! curl -fsS "${COSMOS_URL}" >/dev/null 2>&1; then
    warn "COSMOS not reachable — attempting make launch"
    cd "${NOS3_DIR}"
    make launch > "${NOS3_LAUNCH_LOG}" 2>&1 &
    LAUNCH_PID=$!
    cosmos_ready_check
  fi

  restart_advisor
  attack_instructions
}

# ─── phase: ollama ────────────────────────────────────────────────────────────
phase_ollama() {
  hr; info "PHASE: ollama upgrade"; hr

  [ -d "${ADVISOR_DIR}" ] || die "${ADVISOR_DIR} not found. Run --mode attack first."
  [ -f "${STATE_JSON}" ]  || die "${STATE_JSON} not found. Run --mode attack first."

  info "Checking Ollama at ${OLLAMA_HOST} (model: ${OLLAMA_MODEL})"
  if curl -fsS --max-time 10 \
      -X POST "${OLLAMA_HOST}/api/generate" \
      -d "{\"model\":\"${OLLAMA_MODEL}\",\"prompt\":\"ping\",\"stream\":false}" \
      >/dev/null 2>&1; then
    info "Ollama reachable — model ${OLLAMA_MODEL} responded."
  else
    cat <<EOF

[WARN]  Ollama not reachable at ${OLLAMA_HOST}

  Option A — recommended on this Windows demo laptop:
    Install Ollama for Windows -> start it -> pull your model:
      ollama run ${OLLAMA_MODEL}
    WSL2 reaches Windows Ollama at http://localhost:11434 automatically.

  Option B — inside WSL/Linux:
    curl -fsSL https://ollama.com/install.sh | sh
    ollama run ${OLLAMA_MODEL}

  To switch models:
    OLLAMA_MODEL=llama3 ./nos3_onair.sh --mode ollama

EOF
    die "Ollama not reachable — cannot proceed with live LLM upgrade."
  fi

  write_advisor
  restart_advisor

  info "Smoke-testing live LLM endpoint"
  local result
  result=$(curl -fsS "${ADVISOR_URL}/llm")
  echo "${result}" | grep -q '"ok": true' \
    && info "Live LLM call succeeded." \
    || { warn "LLM response: ${result}"; warn "See ${ADVISOR_LOG}"; }

  ollama_instructions
}

# ─── phase: siem ──────────────────────────────────────────────────────────────
phase_siem() {
  hr; info "PHASE: SIEM (Elastic + Kibana + Filebeat + CCSDS poller)"; hr

  docker ps >/dev/null 2>&1 \
    || die "Docker not available. Run 'exec su -l \$USER' or open a new terminal."

  info "Checking ports before starting Elastic stack"
  check_port 9200 "Elasticsearch"
  check_port 5601 "Kibana"

  mkdir -p "${SIEM_DIR}/logs" "${SIEM_DIR}/filebeat-data" "${SIEM_DIR}/scripts"

  write_siem_compose
  write_filebeat_config
  write_poller

  info "Creating Python venv for poller"
  if [ ! -d "${SIEM_DIR}/.venv" ]; then
    "${PYTHON_BIN}" -m venv "${SIEM_DIR}/.venv"
  fi
  # shellcheck disable=SC1091
  source "${SIEM_DIR}/.venv/bin/activate"
  pip install --upgrade pip -q
  deactivate

  info "Starting Elastic stack"
  cd "${SIEM_DIR}"
  docker compose up -d

  poll_url "Elasticsearch" "${ES_URL}"               120 \
    || die "Elasticsearch did not come up within 120 s."
  poll_url "Kibana"        "${KIBANA_URL}/api/status" 180 \
    || die "Kibana did not come up within 180 s."

  info "Stopping any existing poller"
  pkill -f "ccsds_event_poller.py" 2>/dev/null || true

  info "Starting CCSDS event poller"
  BRIDGE_STATUS_URL="${BRIDGE_STATUS_URL}" \
  EVENT_LOG="${EVENT_LOG}" \
    nohup "${SIEM_DIR}/.venv/bin/python" "${POLLER_SCRIPT}" \
    > "${POLLER_LOG}" 2>&1 &
  sleep 2

  info "Running Filebeat index setup"
  docker compose run --rm filebeat \
    setup \
    -E setup.kibana.host=kibana:5601 \
    -E "output.elasticsearch.hosts=[\"elasticsearch:9200\"]" \
    || true

  info "Checking first indexed documents (may be empty on first run)"
  sleep 5
  curl -fsS "${ES_URL}/ccsds-demo-events-*/_search?size=3&sort=@timestamp:desc" \
    2>/dev/null | ${PYTHON_BIN} -m json.tool 2>/dev/null || true

  siem_instructions
}

# ─── phase: kibana ────────────────────────────────────────────────────────────
phase_kibana() {
  hr; info "PHASE: Kibana assets (data view + saved search + dashboard)"; hr

  poll_url "Kibana" "${KIBANA_URL}/api/status" 60 \
    || die "Kibana not reachable. Run --mode siem first."

  local asset_dir
  asset_dir=$(write_kibana_assets)

  # ── data view (dedicated endpoint in Kibana 8+/9.x) ──────────────────────
  info "Pushing: data view (ccsds-demo-events-*)"
  local dv_code
  dv_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${KIBANA_URL}/api/data_views/data_view" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    --data-binary "@${asset_dir}/dataview.json")
  case "${dv_code}" in
    200|201) info "  → ${dv_code} data view created." ;;
    409)     info "  → 409 data view already exists." ;;
    *)       warn "  → ${dv_code} unexpected — Kibana may need more time." ;;
  esac

  kibana_post "saved search" \
    "/api/saved_objects/search/${KIBANA_SEARCH_ID}?overwrite=true" \
    "${asset_dir}/savedsearch.json"

  kibana_post "dashboard" \
    "/api/saved_objects/dashboard/${KIBANA_DASH_ID}?overwrite=true" \
    "${asset_dir}/dashboard.json"

  kibana_instructions
}

# ─── phase: demoday ───────────────────────────────────────────────────────────
phase_demoday() {
  hr; info "PHASE: demo day"; hr

  [ -d "${NOS3_DIR}" ]    || die "NOS3 not found. Run --mode setup first."
  [ -d "${ADVISOR_DIR}" ] || die "Advisor dir not found. Run --mode attack first."

  docker_group_reminder

  hr; info "Step 1/6 — COSMOS"
  ensure_nos3_running
  if nos3_containers_running && curl -fsS "${COSMOS_URL}" >/dev/null 2>&1; then
    info "COSMOS: UP"
  elif nos3_containers_running; then
    warn "COSMOS: containers up but port not responding yet — may still be starting"
  else
    warn "COSMOS: NOT RESPONDING — check ${NOS3_LAUNCH_LOG}"
  fi

  hr; info "Step 2/6 — Advisory service"
  ensure_advisor_running

  hr; info "Step 3/6 — Ollama"
  if curl -fsS --max-time 10 "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
    info "Ollama: UP at ${OLLAMA_HOST}"
  else
    warn "Ollama: NOT REACHABLE — live LLM calls will fail gracefully."
    warn "Fix: start Ollama on Windows -> ollama run ${OLLAMA_MODEL}"
  fi

  hr; info "Step 4/6 — SIEM stack"
  if [ -f "${SIEM_DIR}/docker-compose.yml" ]; then
    ensure_siem_running
    if pgrep -f "ccsds_event_poller.py" >/dev/null 2>&1; then
      info "CCSDS poller: RUNNING"
    else
      warn "CCSDS poller not running — restarting"
      BRIDGE_STATUS_URL="${BRIDGE_STATUS_URL}" \
      EVENT_LOG="${EVENT_LOG}" \
        nohup "${SIEM_DIR}/.venv/bin/python" "${POLLER_SCRIPT}" \
        > "${POLLER_LOG}" 2>&1 &
      sleep 1
      info "CCSDS poller restarted."
    fi
  else
    warn "SIEM not installed. Run --mode siem to add the Elastic layer."
  fi

  hr; info "Step 5/6 — Kibana dashboard"
  if curl -fsS "${KIBANA_URL}/api/status" >/dev/null 2>&1; then
    local dash_code
    dash_code=$(curl -s -o /dev/null -w "%{http_code}" \
      "${KIBANA_URL}/api/saved_objects/dashboard/${KIBANA_DASH_ID}")
    if [[ "${dash_code}" == "200" ]]; then
      info "Kibana dashboard: EXISTS"
    else
      warn "Kibana dashboard missing (${dash_code}) — re-pushing assets"
      phase_kibana
    fi
    info "Dashboard: ${KIBANA_URL}/app/dashboards#/view/${KIBANA_DASH_ID}"
  else
    warn "Kibana not reachable — SIEM stack may still be starting."
  fi

  hr; info "Step 6/6 — Reset advisory to NOMINAL"
  curl -fsS -X POST "${ADVISOR_URL}/nominal" >/dev/null
  info "Advisory state: NOMINAL"

  demoday_instructions
}

# ─── phase: reset ─────────────────────────────────────────────────────────────
phase_reset() {
  hr; info "PHASE: reset"; hr

  info "Returning advisory state to nominal"
  curl -fsS -X POST "${ADVISOR_URL}/nominal" >/dev/null 2>&1 \
    && info "Advisory state: NOMINAL" \
    || warn "Advisor not reachable — skipping state reset."

  info "Stopping advisory service"
  pkill -f "demo_advisor.py" 2>/dev/null \
    && info "Advisor stopped." || info "Advisor was not running."

  info "Stopping CCSDS event poller"
  pkill -f "ccsds_event_poller.py" 2>/dev/null \
    && info "Poller stopped." || info "Poller was not running."

  info "Stopping SIEM stack"
  if [ -f "${SIEM_DIR}/docker-compose.yml" ]; then
    cd "${SIEM_DIR}"
    docker compose down 2>/dev/null \
      && info "SIEM stack stopped." \
      || warn "docker compose down returned non-zero."
  else
    info "SIEM not installed — skipping."
  fi

  info "Stopping NOS3 stack"
  if [ -d "${NOS3_DIR}" ]; then
    cd "${NOS3_DIR}"
    make stop 2>/dev/null \
      && info "NOS3 stack stopped." \
      || warn "make stop returned non-zero."
  else
    warn "NOS3 dir not found — skipping make stop."
  fi

  hr
  info "Reset complete. System is ready for next run."
  info "To run again:  ./nos3_onair.sh --mode demoday"
  hr
}

# ─── printed instructions ─────────────────────────────────────────────────────
attack_instructions() {
  cat <<EOF

════════════════════════════════════════════════════════════
 ATTACK/DEFEND DEMO HARNESS READY
════════════════════════════════════════════════════════════

 Browser tabs:
   COSMOS:    ${COSMOS_URL}
   Advisory:  ${ADVISOR_URL}/status

 Walkthrough:
   curl -X POST ${ADVISOR_URL}/nominal   # reset
   curl -X POST ${ADVISOR_URL}/attack    # inject anomaly
   curl -X POST ${ADVISOR_URL}/defend    # recover
   curl         ${ADVISOR_URL}/llm       # any step, after --mode ollama

 Logs:   ${ADVISOR_LOG}   ${NOS3_LAUNCH_LOG}

 WSL2 reminder: background services die when all Ubuntu terminals close.
 Re-run --mode demoday after reopening a terminal.

════════════════════════════════════════════════════════════
EOF
}

ollama_instructions() {
  cat <<EOF

════════════════════════════════════════════════════════════
 OLLAMA LIVE LLM DEMO READY
════════════════════════════════════════════════════════════

 Model:  ${OLLAMA_MODEL}    Host: ${OLLAMA_HOST}

 Full flow:
   curl -X POST ${ADVISOR_URL}/nominal
   curl -X POST ${ADVISOR_URL}/attack  &&  curl ${ADVISOR_URL}/llm
   curl -X POST ${ADVISOR_URL}/defend  &&  curl ${ADVISOR_URL}/llm

 Switch models:  OLLAMA_MODEL=llama3 ./nos3_onair.sh --mode ollama
 Next step:      ./nos3_onair.sh --mode siem

════════════════════════════════════════════════════════════
EOF
}

siem_instructions() {
  cat <<EOF

════════════════════════════════════════════════════════════
 ELASTIC + KIBANA SIEM LAYER READY
════════════════════════════════════════════════════════════

 Kibana:          ${KIBANA_URL}
 Elasticsearch:   ${ES_URL}

 Next step (push student dashboard):
   ./nos3_onair.sh --mode kibana

 Logs:
   Poller:  ${POLLER_LOG}
   Events:  ${EVENT_LOG}

════════════════════════════════════════════════════════════
EOF
}

kibana_instructions() {
  cat <<EOF

════════════════════════════════════════════════════════════
 KIBANA ASSETS DEPLOYED
════════════════════════════════════════════════════════════

 Student dashboard (open this):
   ${KIBANA_URL}/app/dashboards#/view/${KIBANA_DASH_ID}

 Layout:
   ┌─────────────────────────┬─────────────────────────┐
   │  Event Count Over Time  │  Anomaly Severity       │
   │  line — spikes mark     │  donut — high slice on  │
   │  attack transitions     │  attack                 │
   ├─────────────────────────┼─────────────────────────┤
   │  Mission Mode Breakdown │  Recent CCSDS Events    │
   │  bar — SAFE vs SCIENCE  │  live table — newest    │
   │  shift during attack    │  event at top           │
   └─────────────────────────┴─────────────────────────┘

 Suggested student exercise:
   1. Open dashboard before any attack — note all-nominal state.
   2. Instructor: curl -X POST ${ADVISOR_URL}/attack
   3. Watch line chart spike and donut gain a high-severity slice.
   4. Filter events table: event.reason : "telemetry_inconsistency*"
   5. Instructor: curl -X POST ${ADVISOR_URL}/defend
   6. Observe severity drop and mode return to SAFE.
   7. Students write a one-paragraph incident timeline from Kibana evidence.

 Saved search (Discover):
   ${KIBANA_URL}/app/discover#/?savedSearchId=${KIBANA_SEARCH_ID}

 Re-push assets any time (idempotent):
   ./nos3_onair.sh --mode kibana

════════════════════════════════════════════════════════════
EOF
}

demoday_instructions() {
  cat <<EOF

════════════════════════════════════════════════════════════
 DEMO DAY READY
════════════════════════════════════════════════════════════

 Browser tabs:
   Mission control:   ${COSMOS_URL}
   Advisory state:    ${ADVISOR_URL}/status
   Live LLM:          ${ADVISOR_URL}/llm
   Kibana dashboard:  ${KIBANA_URL}/app/dashboards#/view/${KIBANA_DASH_ID}

 ── ACT 1 — Nominal ────────────────────────────────────

   COSMOS: send NOOP, confirm telemetry.
   If quiet: send TO_ENABLE_OUTPUT -> CFS_RADIO.
   Show advisory panel + Kibana dashboard in nominal state.
     curl -X POST ${ADVISOR_URL}/nominal

 ── ACT 2 — Attack ──────────────────────────────────────

   Narrate: system behavior inconsistent with expected state.
     curl -X POST ${ADVISOR_URL}/attack
     curl         ${ADVISOR_URL}/llm
   Point to Kibana: line chart spikes, donut gains high-severity slice.

 ── ACT 3 — Defend ──────────────────────────────────────

   COSMOS: command back to SAFE. Verify telemetry.
     curl -X POST ${ADVISOR_URL}/defend
     curl         ${ADVISOR_URL}/llm
   Kibana: show full nominal -> attack -> recovery arc in Discover.

 ── Talk track ──────────────────────────────────────────

   "Nominal ops: command and telemetry flowing through OpenC3/COSMOS."
   "Anomaly injected: degraded link, telemetry inconsistent with mode."
   "Local LLM generates a mission-ops recommendation — no cloud required."
   "Every state change lands in Elasticsearch. Students investigate
    the attack-to-recovery arc entirely inside Kibana."

 ── Between runs ────────────────────────────────────────

   ./nos3_onair.sh --mode reset
   ./nos3_onair.sh --mode demoday

 ── Health checks ───────────────────────────────────────

   COSMOS:   curl -I ${COSMOS_URL}
   Advisor:  curl    ${ADVISOR_URL}/status
   Ollama:   curl    ${OLLAMA_HOST}/api/tags
   ES:       curl    ${ES_URL}/_cat/health?v
   Kibana:   curl    ${KIBANA_URL}/api/status

 ── Logs ────────────────────────────────────────────────

   NOS3:     ${NOS3_LAUNCH_LOG}
   Advisor:  ${ADVISOR_LOG}
   Poller:   ${POLLER_LOG}
   Events:   ${EVENT_LOG}

 ── WSL2 reminder ───────────────────────────────────────

   Background services (NOS3, advisor, poller) are killed when
   all Ubuntu terminals close. Always re-run --mode demoday
   after reopening a terminal on demo day.

════════════════════════════════════════════════════════════
EOF
}

# ─── dispatcher ───────────────────────────────────────────────────────────────
case "$MODE" in
  setup|all) preflight ;;
esac

case "$MODE" in
  setup)   phase_setup ;;
  demo)    phase_demo;   [[ -n "${LAUNCH_PID}" ]] && wait "${LAUNCH_PID}" || true ;;
  attack)  phase_attack ;;
  ollama)  phase_ollama ;;
  siem)    phase_siem ;;
  kibana)  phase_kibana ;;
  all)
    phase_setup
    phase_demo
    phase_attack
    phase_ollama
    phase_siem
    phase_kibana
    [[ -n "${LAUNCH_PID}" ]] && wait "${LAUNCH_PID}" || true
    ;;
  demoday) phase_demoday; [[ -n "${LAUNCH_PID}" ]] && wait "${LAUNCH_PID}" || true ;;
  reset)   phase_reset ;;
esac
