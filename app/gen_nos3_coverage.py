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
CATALOG = os.path.join(ROOT, "data/onair/models/explanation_catalog.json")  # NOS3-312

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

# Per-technique REVIEW rationale for out-of-scope techniques — WHY it can't be
# seen and WHAT would be needed to detect it. Rendered into the "Top fields /
# review" column so every out-of-scope cell shows it has been reviewed with a
# concrete reason (not just "out of scope"). Keep each to ~1-2 sentences.
REVIEW = {
    # -- already in the scored corpus (ENRICH) as OUT-OF-SCOPE --
    "EX-0001.01": "Replayed valid commands are byte-identical to legitimate ones — no telemetry field separates them. Needs: command anti-replay (CryptoLib SDLS ARSN) surfaced as telemetry; not on the bus.",
    "EX-0009.01": "The exploit act itself emits no telemetry; only its downstream effect does (as a separate EX technique). Needs: in-FSW control-flow / memory-safety instrumentation — unmodeled.",
    "IMP-0004":   "Gradual sub-threshold degradation stays inside nominal envelopes, leaving no discrete residual. Needs: multi-day trend/degradation baselining, beyond current per-frame + short-window features.",
    "DE-0003.04": "Command-receiver RSSI is an RF-analog value the NOS3 radio sim doesn't model or telemeter. Needs: RSSI added to RADIO device telemetry (would become UNSUBSCRIBED, not conceptual).",
    "DE-0003.05": "Receiver carrier/lock state is an RF-layer state absent from the software bus. Needs: lock state exposed in RADIO device telemetry.",
    "DE-0003.07": "Crypto state lives only in CryptoLib process memory (a CFE_LIB with zero Software Bus telemetry). Needs: a CryptoLib SA-state HK packet — none exists in this build.",
    "DE-0003.11": "Watchdog state is not among the subscribed MIDs and nothing downstream surfaces it. Needs: subscribe a watchdog/health telemetry packet (UNSUBSCRIBED — recoverable, not permanent).",
    "DE-0003.12": "Poisoning corrupts an offline training dataset, not a live telemetry event. Needs: training-data provenance/integrity checks in the ML pipeline.",
    # -- reviewed but NOT scripted/scored (added via REVIEW_ADD below) --
    "EX-0003":    "Authentication runs inside CryptoLib (CFE_LIB, no SB telemetry); auth-process changes leave no HK footprint. Needs: a CryptoLib auth/SA-state HK packet.",
    "EX-0004":    "Boot-memory/boot-ROM tampering occurs below the running FSW; NOS3 models no boot layer or its telemetry. Needs: secure/measured-boot attestation.",
    "EX-0006":    "Encryption enable state (SA est flag) is internal to CryptoLib; no SB packet carries it. Needs: CryptoLib SA-state HK, or a weak RADIO frame-error proxy when bad frames are rejected downstream.",
    "EX-0009.02": "Exploiting the host Linux OS operates below the cFS application layer OnAIR observes. Needs: host-OS security monitoring (auditd/EDR) — a separate sensor from cFS telemetry.",
    "EX-0009.03": "A library-CVE exploit has no cFS-telemetry signature until it causes a downstream effect (a separate technique). Needs: SBOM/vulnerability scanning, off-board.",
    "EX-0010.03": "A rootkit's purpose is to hide from the host it infects, suppressing its own footprint; NOS3 models no kernel/rootkit layer. Needs: host-level file/memory integrity attestation, off the cFS bus.",
    "EX-0010.04": "A bootkit runs before the FSW/OS boots and persists beneath it — no running-FSW telemetry at that layer. Needs: measured-boot / TPM attestation, unmodeled.",
    "EX-0012.01": "CPU/peripheral register writes are not exposed in any cFS HK packet. Needs: a low-level register-monitoring agent — not present.",
    "EX-0012.13": "Corrupts an offline training dataset rather than emitting a live telemetry event. Needs: ML-pipeline training-data integrity/provenance.",
    "PER-0002.01":"A covert hardware path has no software telemetry and is invisible from the FSW. Needs: supply-chain hardware assurance / side-channel analysis, off-board.",
    "PER-0002.02":"A dormant software backdoor emits no distinguishing telemetry until triggered (then it acts as another EX technique). Needs: static/binary analysis of the FSW image, off-board.",
    "PER-0004":   "Key material (ekid/akid) is internal to CryptoLib's SADB; a key swap is invisible on the SB. Needs: CryptoLib key-index HK, or ground-side downlink-auth-failure detection.",
    "DE-0004":    "By design the malicious action mimics legitimate telemetry. Needs: cryptographic command provenance (CryptoLib, un-telemetered) or finer behavioral baselining than current features.",
    "DE-0007":    "Same as the rootkit case (EX-0010.03): the rootkit hides the evasion and NOS3 has no host-integrity sensor. Needs: file/memory attestation off the cFS bus.",
    "DE-0008":    "Same as the bootkit case (EX-0010.04): sub-OS persistence with no running-FSW telemetry. Needs: measured-boot attestation.",
    "DE-0011":    "Uses valid (stolen) credentials, so actions appear authorized on the bus. Needs: an identity/session layer NOS3 doesn't model; telemetry can't tell a thief from an operator.",
}

# Reviewed out-of-scope techniques that are NOT in the scored corpus — added to
# the overlay purely to record the review verdict. id -> (name, signal).
REVIEW_ADD = {
    "EX-0003":     ("Modify Authentication Process",   "CONCEPTUAL"),
    "EX-0004":     ("Compromise Boot Memory",          "CONCEPTUAL"),
    "EX-0006":     ("Disable/Bypass Encryption",       "CONCEPTUAL"),
    "EX-0009.02":  ("Operating System",                "CONCEPTUAL"),
    "EX-0009.03":  ("Known Vulnerability (COTS/FOSS)",  "CONCEPTUAL"),
    "EX-0010.03":  ("Rootkit",                         "CONCEPTUAL"),
    "EX-0010.04":  ("Bootkit",                         "CONCEPTUAL"),
    "EX-0012.01":  ("Registers",                       "CONCEPTUAL"),
    "EX-0012.13":  ("Poison AI/ML Training Data",      "CONCEPTUAL"),
    "PER-0002.01": ("Hardware Backdoor",               "CONCEPTUAL"),
    "PER-0002.02": ("Software Backdoor",               "CONCEPTUAL"),
    "PER-0004":    ("Replace Cryptographic Keys",      "CONCEPTUAL"),
    "DE-0004":     ("Masquerading",                    "CONCEPTUAL"),
    "DE-0007":     ("Evasion via Rootkit",             "CONCEPTUAL"),
    "DE-0008":     ("Evasion via Bootkit",             "CONCEPTUAL"),
    "DE-0011":     ("Credentialed Evasion",            "CONCEPTUAL"),
}


def main():
    rescore = json.load(open(RESCORE)) if os.path.exists(RESCORE) else {"per_attack": {}}
    per_attack = rescore.get("per_attack", {})
    tax = json.load(open(TAXONOMY)) if os.path.exists(TAXONOMY) else {}
    cluster_of = {}
    for rep, members in (tax.get("clusters") or {}).items():
        for m in members:
            cluster_of[m] = rep

    # NOS3-312: per-class explanation (top telemetry fields) from the catalog.
    catalog = json.load(open(CATALOG)) if os.path.exists(CATALOG) else {}
    explain_of = {tid: e.get("top_features_str", "")
                  for tid, e in (catalog.get("classes") or {}).items()}

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
            "explanation": explain_of.get(tid, ""),  # NOS3-312
            "review": REVIEW.get(tid, ""),           # why-OOS / what's-needed
        }

    # Reviewed-but-not-scored out-of-scope techniques: overlay the review verdict
    # so every out-of-scope cell shows a concrete reason, not a blank.
    for tid, (name, signal) in REVIEW_ADD.items():
        if tid in coverage:
            continue
        coverage[tid] = {
            "name": name, "tier": "OUT-OF-SCOPE", "signal": signal,
            "frame_rate": None, "incident_detected": None, "incident_total": None,
            "incident_recall": None, "label_ok": None, "cluster": None,
            "explanation": "", "review": REVIEW.get(tid, ""),
        }

    meta = {
        "generated_from": ["V5_DETECTOR_COVERAGE.md", "incident_rescore.json",
                           "cluster_taxonomy.json", "explanation_catalog.json"],
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
