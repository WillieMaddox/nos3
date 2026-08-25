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
CATALOG = os.path.join(ROOT, "data/onair/models/explanation_catalog.json")  # AINOS3-40
# Classifier confidence tiers, DERIVED from LOIO folds by
# components/onair/training/derive_classifier_tiers.py. Before 2026-08-20 these
# were hardcoded strings in ENRICH below whose derivation nobody could
# reproduce — and an audit found none of the four published ROBUST techniques
# met the documented "F1 >= 0.85 on every split" rule. The tier in ENRICH is now
# only a FALLBACK, used for techniques the classifier does not score at all
# (gate-detected and out-of-scope leaves).
TIERS = os.path.join(ROOT, "data/onair/models/classifier_tiers.json")

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
    # ⚠ CONFIRMED GAP (2026-08-17): the 0.99 came from transient-dominated data. In
    # steady flight the EPS switch toggle is detected by NOTHING — 0/3 replication reps,
    # no IF lift, no rule fired. Ticketed `detect-eps-switch`. Rate set to 0.0.
    "EX-0012.09": ("HIGH-VAR",   "ON_BOARD",     0.0,  "EPS subsystem — CONFIRMED GAP, see review"),
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
    "DE-0003.12": ("OUT-OF-SCOPE", "CONCEPTUAL",   None, "Poison AI/ML training"),
}

# ── Techniques whose coverage assessment CHANGED this sprint ────────────────
# Drives the "updated" marker on the main matrix: a parent technique card shows a
# dot when any sub-technique under it changed, so a reader scanning the matrix can
# see where to look without diffing. Reason strings surface in the tooltip.
# Clear this dict at the start of each sprint.
UPDATED_SPRINT = "Sprint 28"
UPDATED = {
    # Cleared at Sprint 28 kickoff (2026-08-23). Sprint 27 markers served their
    # readout (AINOS3-76, delivered 2026-08-23). Add entries as this sprint changes
    # coverage assessments.
    # --- AINOS3-95 (2026-08-25) ---
    "EX-0012.12": "Now gate-detected by rule-gate R15 (GPS-vs-FSW clock divergence), "
                  "live-validated against a real SET_TIME injection",
    "EX-0014.01": "Now gate-detected by rule-gate R15 (GPS-vs-FSW clock divergence), "
                  "live-validated against a real SET_TIME injection",
    "EX-0001.01": "Out-of-scope rationale corrected — SPARTA's logging workbook proposes "
                  "ground/spacecraft command-counter reconciliation, which we have not tried",
    "EX-0006":    "Out-of-scope rationale corrected — the workbook asks for the bypass "
                  "COMMAND, not the CryptoLib state; re-openable as a rule candidate",
    "PER-0004":   "Out-of-scope rationale corrected — the workbook asks for the key-change "
                  "COMMAND, not the key material",
    "EX-0012.11": "Rationale sharpened — the HS app is a BUILD gap (loaded + scheduled, no "
                  ".so), not a design limit; re-openable once built",
    "DE-0003.11": "Rationale sharpened — same HS build gap as EX-0012.11",
    "EX-0012.01": "Rationale sharpened — MM/MD are in the same not-built cluster",
    "EX-0012.13": "Narrowed — the workbook's live control (training-data drift) is a "
                  "corpus-integrity item, not an FSW observability gap",
}

# ── Section-A gate-detected techniques (coverage-validation campaign, AINOS3-50…62,
# live-verified through 2026-07-17). The deployed per-mode IF MISSES these by design —
# their footprint is a discrete flag/counter/freeze/spoof the dynamics model doesn't
# weight — so `frame_rate` is the IF SUNSAFE rate only where the exploit also perturbs
# physics (EX-0005.02, EX-0011), else None. They are caught by the complementary gates
# (rule-gate R1–R10, consistency-check, staleness-check), each live-verified raising an
# incident. id -> (frame_rate, label, detector).
GATE_DETECTED = {
    "EX-0002":    (None, "PNT geofencing",                  "rule-gate R1 (NOVATEL disable) → EX-0002 incident"),
    "EX-0005.02": (0.78, "Malicious use of HW commands",    "rule-gate R1 (TORQUER) + dynamics-IF (78%)"),
    "EX-0011":    (0.52, "Exploit reduced protections in safe-mode", "rule-gate R5 (LC) / R1 (CSS) + dynamics-IF (52%)"),
    "EX-0012.02": (None, "Internal routing tables",         "staleness-check (freeze) + rule-gate R6 (CFE_SB cmd)"),
    "EX-0012.10": (None, "C&DH subsystem",                  "rule-gate R8 (CFE_ES command) → EX-0012.10 incident"),
    "EX-0013.01": (None, "Flooding — valid commands",       "rule-gate R2 (EVS flood; labeled DE-0010)"),
    "EX-0013.02": (None, "Flooding — erroneous input",      "rule-gate R4 (command-error family)"),
    "EX-0014.02": (None, "Bus traffic spoofing",            "consistency-check (per-sample counter monotonicity)"),
    "DE-0002.03": (None, "Inhibit spacecraft functionality", "staleness-check (EVS freeze) + rule-gate R7 (CFE_EVS cmd)"),
    "DE-0005":    (None, "Subvert protections via safe-mode", "rule-gate R5 (LC) + R14 ADCS mode-force / mode-flap + staleness-check (AINOS3-77; flap rule live-verified 2026-08-15)"),
    "DE-0010":    (None, "Overflow audit log",              "rule-gate R2 (EVS send-rate) → DE-0010 incident"),
    "PER-0001":   (None, "Memory compromise",               "rule-gate R9 (CFE_TBL command) → PER-0001 incident"),
    "LM-0002":    (None, "Exploit lack of bus segregation", "rule-gate R10 bus-sweep meta (R6+R7+R8+R9) → LM-0002 incident"),
    "EX-0010.01": (None, "Ransomware (mass file encryption)", "rule-gate R11 (FM command) → EX-0010 file-op-burst incident"),
    "EX-0010.02": (None, "Wiper (mass file destruction)",    "rule-gate R11 (FM command) → EX-0010 file-op-burst incident"),
    "EXF-0003.02": (None, "Downlink exfiltration",           "rule-gate R12 (TO command) + R13 (downlink route-mask change) → EXF-0003.02 incident"),
    "EX-0012.12": (0.57, "System clock",                     "rule-gate R15 (GPS-vs-FSW clock divergence) → EX-0014.01 incident; live-validated 2026-08-25 against a real SET_TIME"),
    "EX-0014.01": (0.26, "Time spoof",                        "rule-gate R15 (GPS-vs-FSW clock divergence); live-validated 2026-08-25 — fired on the attack frame, 0 fires in 2,152 nominal frames"),
    "DE-0001":    (None, "Disable fault management",         "rule-gate R5 (LC state → DISABLED) — shared LC-disable footprint with EX-0011/DE-0005 (AINOS3-73)"),
    "DE-0006":    (None, "Modify whitelist",                 "rule-gate R8 (CFE_ES cmd) + R9 (CFE_TBL cmd) — presents as command activity; NOOP-only script activates no table (AINOS3-75)"),
}

# Per-technique REVIEW rationale for out-of-scope techniques — WHY it can't be
# seen and WHAT would be needed to detect it. Rendered into the "Top fields /
# review" column so every out-of-scope cell shows it has been reviewed with a
# concrete reason (not just "out of scope"). Keep each to ~1-2 sentences.
REVIEW = {
    # -- CONFIRMED GAP (not out-of-scope; nothing detects it) --
    "EX-0012.09": "CONFIRMED GAP (2026-08-17). The published 99% came from transient-dominated data. "
                  "In steady flight a 24-run replication found NOTHING detects it: IF lift -0.4 +/- 0.1 "
                  "(0.00% of attack frames) and no rule-gate rule fired in 0/3 reps. The attack sends "
                  "EPS_FC_SWITCH — a discrete state change the dynamics IF is blind to by design — but "
                  "unlike its siblings (EX-0012.08 -> R14, EX-0014.04 -> R1) no rule covers it. Needs: "
                  "establish whether the switch toggle appears in any recorded EPS field; if yes an "
                  "R1/R6-style rule, if no reclassify as UNSUBSCRIBED. Ticketed `detect-eps-switch`.",
    # -- already in the scored corpus (ENRICH) as OUT-OF-SCOPE --
    "EX-0001.01": "⚠ Rationale corrected 2026-08-25 (AINOS3-95). Previously: 'byte-identical, no telemetry field separates them'. SPARTA's logging workbook (C&DH row 13) does not propose separating the bytes — it proposes RECONCILING the spacecraft command counter against the ground's own count, i.e. a mismatch rather than a signature. We already record every spacecraft-side counter (CI.usCmdCnt, TO.usCmdCnt, all five CFE_*.CommandCounter); the missing half is a join to COSMOS's ground-side count, not a MID. Re-openable — ticket `ground-counter-reconciliation`.",
    "EX-0009.01": "The exploit act itself emits no telemetry; only its downstream effect does (as a separate EX technique). Needs: in-FSW control-flow / memory-safety instrumentation — unmodeled.",
    "IMP-0004":   "Gradual sub-threshold degradation stays inside nominal envelopes, leaving no discrete residual. Needs: multi-day trend/degradation baselining, beyond current per-frame + short-window features.",
    "DE-0003.04": "Command-receiver RSSI is an RF-analog value the NOS3 radio sim doesn't model or telemeter. Needs: RSSI added to RADIO device telemetry (would become UNSUBSCRIBED, not conceptual).",
    "DE-0003.05": "Receiver carrier/lock state is an RF-layer state absent from the software bus. Needs: lock state exposed in RADIO device telemetry.",
    "DE-0003.07": "Crypto state lives only in CryptoLib process memory (a CFE_LIB with zero Software Bus telemetry). Needs: a CryptoLib SA-state HK packet — none exists in this build.",
    "DE-0003.11": "⚠ Sharpened 2026-08-25 (AINOS3-95). AINOS3-74 was right about the BUILD, and the reason is more specific than 'there is no HS app': cfe_es_startup.scr DOES load `hs` and sch_def_msgtbl.c DOES request HS_SEND_HK_MID — there is simply no hs.so in fsw/build/exe/cpu1/cf/ (nor cs/mm/md/hk). The workbook (C&DH row 4) rates watchdog-service logging Medium and names exactly what to log. So this is out-of-scope for the build, NOT out-of-scope by design: re-openable if and only if the app is built — ticket `build-hs-app`, then `retest-reopened-verdicts`.",
    "EX-0012.11": "⚠ Sharpened 2026-08-25 (AINOS3-95) — see DE-0003.11. The PSP watchdog is a no-op stub, but the missing HS app is a BUILD gap (loaded in the startup script and scheduled, no .so) rather than a design limit. Re-openable once `build-hs-app` lands.",
    "EX-0001.02": "Internal SBN bus replay has no external injection path in stock NOS3 (AINOS3-75): SBN over UDP is telemetry-OUT only, and the :5012 bridge injects CCSDS commands (EX-0001.01 / EX-0014.02), not raw bus messages. The foothold prerequisite is a malicious in-partition app (EX-0010). Structurally unexercisable from outside the container.",
    "DE-0003.12": "Poisoning corrupts an offline training dataset, not a live telemetry event. Needs: training-data provenance/integrity checks in the ML pipeline.",
    # -- reviewed but NOT scripted/scored (added via REVIEW_ADD below) --
    "EX-0003":    "Authentication runs inside CryptoLib (CFE_LIB, no SB telemetry); auth-process changes leave no HK footprint. Needs: a CryptoLib auth/SA-state HK packet.",
    "EX-0006":    "⚠ Rationale corrected 2026-08-25 (AINOS3-95). The encryptor STATE is indeed internal to CryptoLib — but the workbook (TT&C rows 22/24) asks for the COMMAND, not the state: 'any received bypass commands / disable encryptor — log and alert under all circumstances'. A command arriving at CI is exactly the static-in-nominal counter signal rules R6-R13 exploit. Re-openable as a RULE candidate, not a subscription — ticket `test-encryption-bypass-observability`.",
    "EX-0009.02": "Exploiting the host Linux OS operates below the cFS application layer OnAIR observes. Needs: host-OS security monitoring (auditd/EDR) — a separate sensor from cFS telemetry.",
    "EX-0009.03": "A library-CVE exploit has no cFS-telemetry signature until it causes a downstream effect (a separate technique). Needs: SBOM/vulnerability scanning, off-board.",
    "EX-0010.03": "A rootkit's purpose is to hide from the host it infects, suppressing its own footprint; NOS3 models no kernel/rootkit layer. Needs: host-level file/memory integrity attestation, off the cFS bus.",
    "EX-0010.04": "A bootkit runs before the FSW/OS boots and persists beneath it — no running-FSW telemetry at that layer. Needs: measured-boot / TPM attestation, unmodeled.",
    "EX-0012.01": "⚠ Sharpened 2026-08-25 (AINOS3-95). True of this build, but the standard cFS answer exists and is in the same not-built cluster as the watchdog: MM (Memory Manager) and MD (Memory Dwell) are loaded in cfe_es_startup.scr and their HK is scheduled, with no .so present. The workbook asks for 'log the memory register and the new value' on 12 of 13 subsystem sheets. Re-openable once `build-mm-md-apps` lands. ⚠ Note that building MM also hands an attacker a supported memory-write path.",
    "EX-0012.13": "⚠ Narrowed 2026-08-25 (AINOS3-95). Still largely offline, but the workbook (C&DH row 25) adds a live control we had not considered: 'input data drift from the distribution of training data should also be monitored'. The ML service in question is OURS, so this is a corpus-integrity item (epic AINOS3-98), not an FSW observability gap.",
    "PER-0002.01":"A covert hardware path has no software telemetry and is invisible from the FSW. Needs: supply-chain hardware assurance / side-channel analysis, off-board.",
    "PER-0002.02":"A dormant software backdoor emits no distinguishing telemetry until triggered (then it acts as another EX technique). Needs: static/binary analysis of the FSW image, off-board.",
    "PER-0004":   "⚠ Rationale corrected 2026-08-25 (AINOS3-95). Key material is internal to CryptoLib's SADB, but the workbook (TT&C row 23) asks for 'any received key change commands' — the command, not the material. Same re-open shape as EX-0006; ticket `test-encryption-bypass-observability`.",
    "DE-0004":    "By design the malicious action mimics legitimate telemetry. Needs: cryptographic command provenance (CryptoLib, un-telemetered) or finer behavioral baselining than current features.",
    "DE-0007":    "Same as the rootkit case (EX-0010.03): the rootkit hides the evasion and NOS3 has no host-integrity sensor. Needs: file/memory attestation off the cFS bus.",
    "DE-0008":    "Same as the bootkit case (EX-0010.04): sub-OS persistence with no running-FSW telemetry. Needs: measured-boot attestation.",
    "DE-0011":    "Uses valid (stolen) credentials, so actions appear authorized on the bus. Needs: an identity/session layer NOS3 doesn't model; telemetry can't tell a thief from an operator.",
    "PER-0005":   "Persists using valid (stolen) credentials, so the actions look authorized on the bus — telemetry can't tell a credentialed attacker from an operator (sibling of DE-0011). Needs: an identity/session layer NOS3 doesn't model.",
}

# Reviewed out-of-scope techniques that are NOT in the scored corpus — added to
# the overlay purely to record the review verdict. id -> (name, signal).
# NOTE: EX-0004 (boot memory) was moved OUT of here — per SPARTA_COVERAGE_TRIAGE.md
# Section D it is Not-Applicable (NOS3 models no boot layer, so the target doesn't
# exist), not out-of-scope. N/A is classified in the overlay's NA_TECH map, not here.
REVIEW_ADD = {
    "EX-0003":     ("Modify Authentication Process",   "CONCEPTUAL"),
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
    "PER-0005":    ("Credentialed Persistence",        "CONCEPTUAL"),
    "DE-0004":     ("Masquerading",                    "CONCEPTUAL"),
    "DE-0007":     ("Evasion via Rootkit",             "CONCEPTUAL"),
    "DE-0008":     ("Evasion via Bootkit",             "CONCEPTUAL"),
    "DE-0011":     ("Credentialed Evasion",            "CONCEPTUAL"),
    # AINOS3-74/75 (Sprint 26): watchdog pair + bus-traffic replay resolved
    # out-of-scope after a live/structural footprint check.
    "EX-0012.11":  ("Modify Watchdog / Health Monitor", "UNSUBSCRIBED"),
    "DE-0003.11":  ("Watchdog State for Evasion",       "UNSUBSCRIBED"),
    "EX-0001.02":  ("Bus Traffic Replay",               "CONCEPTUAL"),
}


def main():
    rescore = json.load(open(RESCORE)) if os.path.exists(RESCORE) else {"per_attack": {}}
    per_attack = rescore.get("per_attack", {})
    tax = json.load(open(TAXONOMY)) if os.path.exists(TAXONOMY) else {}
    cluster_of = {}
    for rep, members in (tax.get("clusters") or {}).items():
        for m in members:
            cluster_of[m] = rep

    # AINOS3-40: per-class explanation (top telemetry fields) from the catalog.
    catalog = json.load(open(CATALOG)) if os.path.exists(CATALOG) else {}
    explain_of = {tid: e.get("top_features_str", "")
                  for tid, e in (catalog.get("classes") or {}).items()}

    # Derived confidence tiers (preferred over ENRICH's fallback strings).
    tiers_doc = json.load(open(TIERS)) if os.path.exists(TIERS) else {}
    tier_of = {k: v["tier"] for k, v in (tiers_doc.get("classes") or {}).items()}
    if not tier_of:
        print(f"!! WARNING: {os.path.basename(TIERS)} missing — falling back to the "
              f"hardcoded ENRICH tiers, which are NOT reproducible. Regenerate with "
              f"components/onair/training/derive_classifier_tiers.py", flush=True)

    coverage = {}
    for tid, (tier, signal, frame_rate, label) in ENRICH.items():
        pa = per_attack.get(tid, {})
        det, n = pa.get("detected"), pa.get("n")
        coverage[tid] = {
            "name": label,
            "tier": tier_of.get(tid, tier),
            "tier_source": "derived" if tid in tier_of else "fallback",
            "signal": signal,
            "frame_rate": frame_rate,
            "incident_detected": det,
            "incident_total": n,
            "incident_recall": pa.get("recall"),
            "updated": UPDATED.get(tid), "updated_sprint": UPDATED_SPRINT if tid in UPDATED else None,
            "label_ok": pa.get("label_ok"),
            "cluster": cluster_of.get(tid),
            "explanation": explain_of.get(tid, ""),  # AINOS3-40
            "review": REVIEW.get(tid, ""),           # why-OOS / what's-needed
        }

    # Section-A gate-detected techniques (rule-gate / consistency / staleness — the
    # per-mode IF misses them). Each was live-verified raising an incident, so status is
    # "detected" via the gate (see the overlay's `c.gate` handling); the detector is
    # named in the review column. These do NOT come from the classifier incident-rescore.
    for tid, (frame_rate, label, detector) in GATE_DETECTED.items():
        if tid in coverage:
            # Already classifier-scored via ENRICH. A technique can be BOTH scored and
            # gate-detected — before 2026-08-25 this loop dropped the gate silently, so
            # R15's catch of EX-0012.12 / EX-0014.01 would never have surfaced. Attach
            # the gate to the existing entry instead of discarding it.
            coverage[tid]["gate"] = detector
            existing = coverage[tid].get("review") or ""
            note = "Also caught by " + detector + "."
            coverage[tid]["review"] = (existing + " " + note).strip() if existing else note
            if tid in UPDATED:
                coverage[tid]["updated"] = UPDATED[tid]
                coverage[tid]["updated_sprint"] = UPDATED_SPRINT
            continue
        coverage[tid] = {
            "name": label, "tier": "RULE-GATE", "signal": "ON_BOARD",
            "frame_rate": frame_rate, "incident_detected": None, "incident_total": None,
            "incident_recall": None, "label_ok": None,
            "updated": UPDATED.get(tid), "updated_sprint": UPDATED_SPRINT if tid in UPDATED else None,
            "cluster": cluster_of.get(tid), "explanation": "",
            "review": "Caught by " + detector + " (dynamics-IF blind by design).",
            "gate": detector,
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
            "updated": UPDATED.get(tid), "updated_sprint": UPDATED_SPRINT if tid in UPDATED else None,
        }

    meta = {
        "generated_from": ["V5_DETECTOR_COVERAGE.md", "incident_rescore.json",
                           "cluster_taxonomy.json", "explanation_catalog.json"],
        "model": "iforest_per_mode_v5 + xgb_attack_classifier_v3_hybrid (AINOS3-37 selective per-mode)",
        "incident_recall_headline": rescore.get("incident_detection_recall"),
        "n_techniques": len(coverage),
        "updated_sprint": UPDATED_SPRINT,
        "updated_techniques": sorted(UPDATED),
        # AINOS3-80: every displayed number states how it was measured. Tags:
        # OOF = out-of-fold · live-soak = independent nominal flight ·
        # in-sample = measured on fitted data · design-target = a configured
        # parameter, not a measurement · unverifiable = see the note.
        "provenance": {
            "label_ok": "OOF — leave-one-instance-out over the 3-instance frozen "
                        "corpus, rescored through the deployed hybrid's routing "
                        "(export_hybrid_oof.py). Replaced an in-sample figure that "
                        "was >2x optimistic (76.9% -> 42.3%).",
            "incident_recall": "unverifiable — the attack rows were never fitted (the "
                               "IF trains on nominal only), but the deployed IF "
                               "artifact records no training-corpus identity, so "
                               "disjointness cannot be proven. See AINOS3-80 F2.",
            "frame_rate": "MIXED — a 24-run steady-flight replication showed this "
                          "column credits the IF with detections the rule-gate makes "
                          "(EX-0012.08 -> R14, EX-0014.04 -> R1; IF lift ~0 for both), "
                          "and that EX-0012.09 is detected by nothing (0/3 reps). Where "
                          "the IF IS the right detector it is vindicated: EX-0012.07 "
                          "propulsion measures +77.5 +/- 3.6 lift in steady flight.",
            "false_positive_rate": "live-soak — SUNSAFE 0.02-0.74%, PASSIVE/BDOT "
                                   "0.00%. INERTIAL is a serious open defect: 33.6% "
                                   "nominal (21.1-48.5%) across 12 runs at a 600s "
                                   "hold, up from 0.00% published and 7.5% over a 7h "
                                   "soak; the settling explanation is refuted and the "
                                   "mode is currently unusable for detection "
                                   "(ticketed inertial-false-alarms). The 1% figure "
                                   "quoted elsewhere is a design-target calibrated "
                                   "in-sample, not a measurement (AINOS3-80 F1).",
            "technique_top1": "OOF — 0.645 +/- 0.036 across three instances; the "
                              "spread exceeds most deltas quoted against it.",
            "tier": "OOF — derived by derive_classifier_tiers.py from LOIO folds of "
                    "the DEPLOYED hybrid, scored at the level actually reported "
                    "(cluster F1 for multi-member clusters). Was hardcoded and "
                    "unreproducible until 2026-08-20; an audit then found none of the "
                    "four techniques published as ROBUST met the documented "
                    "'F1 >= 0.85 on every split' rule (DE-0003.01 averaged 0.03). "
                    "ROBUST is currently EMPTY — IMP-0005 is the closest at min 0.848 "
                    "— and the bar was deliberately not lowered to populate it.",
            "explanation": "OOF-independent — per-class mean-|SHAP| over the frozen "
                           "corpus, computed against the DEPLOYED hybrid with live "
                           "routing (a frame in a routed mode is explained by that "
                           "mode's head). Percentages are each field's share of the "
                           "summed attribution over ALL fields, so the displayed "
                           "top-6 need not total 100%.",
            "cluster": "OOF — re-derived from the hybrid's confusion matrix at the "
                       "deployed tau=0.1; membership is UNCHANGED from the v3-global "
                       "taxonomy at every tau tested (0.10/0.15/0.20/0.30).",
            "audit": "components/onair/AINOS3_80_METRIC_PROVENANCE.md",
        },
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
