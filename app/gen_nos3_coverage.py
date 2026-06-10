#!/usr/bin/env python3
"""NOS3-211 — generate the NOS3 detection-coverage overlay data for the SPARTA
demo app from the validated artifacts.

Emits a `window.NOS3_COVERAGE` JS object (one entry per SPARTA sub-technique the
NOS3 OnAIR monitor was evaluated against), combining:
  - frame-level SUNSAFE catch rate + classifier tier + signal class
    (from V5_DETECTOR_COVERAGE.md — encoded here as the source of truth),
  - incident-level recall + label accuracy
    (live from data/onair/models/cluster_rescore/incident_rescore.json),
  - the telemetry-indistinguishable cluster (cluster_taxonomy.json).

Output: app/nos3_coverage.js  (and prints it). The demo app inlines / loads it.

Run:  python3 app/gen_nos3_coverage.py
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESCORE = os.path.join(ROOT, "data/onair/models/cluster_rescore/incident_rescore.json")
TAXONOMY = os.path.join(ROOT, "data/onair/models/cluster_rescore/cluster_taxonomy.json")

# Source of truth from V5_DETECTOR_COVERAGE.md coverage matrix.
# tier:  ROBUST | STABLE-MID | HIGH-VAR | SIBLING | LOW-STABLE | DEAD | OUT-OF-SCOPE
# signal: ON_BOARD | OBFUSCATION | UNSUBSCRIBED | CONCEPTUAL
# frame_rate: SUNSAFE corruption-window flag rate (None if <25% / not meaningful)
ENRICH = {
    "EX-0008.01": ("HIGH-VAR",   "ON_BOARD",     0.91, "ATS"),
    "EX-0008.02": ("ROBUST",     "ON_BOARD",     0.91, "RTS"),
    "EX-0012.03": ("SIBLING",    "ON_BOARD",     None, "Memory write"),
    "EX-0012.04": ("SIBLING",    "ON_BOARD",     0.63, "App subscriber tables"),
    "EX-0012.05": ("SIBLING",    "ON_BOARD",     0.64, "Scheduling algorithm"),
    "EX-0012.07": ("HIGH-VAR",   "ON_BOARD",     1.00, "Propulsion subsystem"),
    "EX-0012.08": ("HIGH-VAR",   "ON_BOARD",     1.00, "ADCS subsystem"),
    "EX-0012.09": ("HIGH-VAR",   "ON_BOARD",     0.99, "EPS subsystem"),
    "EX-0012.12": ("SIBLING",    "ON_BOARD",     0.57, "System clock"),
    "EX-0014.01": ("SIBLING",    "ON_BOARD",     0.26, "Time spoof"),
    "EX-0014.03": ("DEAD",       "ON_BOARD",     0.91, "Sensor data spoof"),
    "EX-0014.04": ("HIGH-VAR",   "ON_BOARD",     0.98, "PNT spoof"),
    "IMP-0001":   ("LOW-STABLE", "OBFUSCATION",  0.61, "Deception"),
    "IMP-0002":   ("STABLE-MID", "ON_BOARD",     0.58, "Disruption"),
    "IMP-0003":   ("STABLE-MID", "ON_BOARD",     1.00, "Denial"),
    "IMP-0005":   ("ROBUST",     "ON_BOARD",     0.75, "Destruction"),
    "IMP-0006":   ("STABLE-MID", "UNSUBSCRIBED", 0.62, "Theft"),
    "DE-0003.01": ("ROBUST",     "OBFUSCATION",  None, "Vehicle command counter"),
    "DE-0003.02": ("LOW-STABLE", "OBFUSCATION",  None, "Rejected command counter"),
    "DE-0003.03": ("DEAD",       "UNSUBSCRIBED", None, "Command receiver mode"),
    "DE-0003.06": ("DEAD",       "ON_BOARD",     None, "Telemetry downlink modes"),
    "DE-0003.08": ("DEAD",       "OBFUSCATION",  None, "Received commands"),
    "DE-0003.09": ("DEAD",       "ON_BOARD",     None, "System clock for evasion"),
    "DE-0003.10": ("ROBUST",     "ON_BOARD",     None, "GPS ephemeris"),
    # Out-of-scope by design (no telemetry-based detection possible)
    "EX-0001.01": ("OUT-OF-SCOPE", "CONCEPTUAL",   None, "Command packets"),
    "EX-0009.01": ("OUT-OF-SCOPE", "CONCEPTUAL",   None, "Flight software"),
    "IMP-0004":   ("OUT-OF-SCOPE", "CONCEPTUAL",   None, "Degradation"),
    "DE-0003.04": ("OUT-OF-SCOPE", "CONCEPTUAL",   None, "Command receiver RSSI"),
    "DE-0003.05": ("OUT-OF-SCOPE", "CONCEPTUAL",   None, "Command receiver lock modes"),
    "DE-0003.07": ("OUT-OF-SCOPE", "CONCEPTUAL",   None, "Cryptographic modes"),
    "DE-0003.11": ("OUT-OF-SCOPE", "UNSUBSCRIBED", None, "Watchdog timer"),
    "DE-0003.12": ("OUT-OF-SCOPE", "CONCEPTUAL",   None, "Poison AI/ML training"),
}


def main():
    rescore = json.load(open(RESCORE)) if os.path.exists(RESCORE) else {"per_attack": {}}
    per_attack = rescore.get("per_attack", {})
    tax = json.load(open(TAXONOMY)) if os.path.exists(TAXONOMY) else {}
    cluster_of = {}
    for rep, members in (tax.get("clusters") or {}).items():
        for m in members:
            cluster_of[m] = rep

    coverage = {}
    for tid, (tier, signal, frame_rate, label) in ENRICH.items():
        pa = per_attack.get(tid, {})
        det, n = pa.get("detected"), pa.get("n")
        coverage[tid] = {
            "name": label,
            "tier": tier,
            "signal": signal,
            "frame_rate": frame_rate,
            "incident_detected": det,
            "incident_total": n,
            "incident_recall": pa.get("recall"),
            "label_ok": pa.get("label_ok"),
            "cluster": cluster_of.get(tid),
        }

    meta = {
        "generated_from": ["V5_DETECTOR_COVERAGE.md", "incident_rescore.json",
                           "cluster_taxonomy.json"],
        "model": "iforest_per_mode_v5 + xgb_attack_classifier_v3",
        "incident_recall_headline": rescore.get("incident_detection_recall"),
        "n_techniques": len(coverage),
    }

    js = ("// AUTO-GENERATED by app/gen_nos3_coverage.py — do not edit by hand.\n"
          "window.NOS3_COVERAGE_META = " + json.dumps(meta, indent=2) + ";\n"
          "window.NOS3_COVERAGE = " + json.dumps(coverage, indent=2) + ";\n")
    out = os.path.join(HERE, "nos3_coverage.js")
    with open(out, "w") as f:
        f.write(js)
    print(js)
    print(f"// wrote {out}  ({len(coverage)} techniques)")


if __name__ == "__main__":
    main()
