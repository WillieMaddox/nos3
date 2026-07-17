# SPARTA Coverage Triage — NOS3 OnAIR Monitor

**Purpose.** The demo matrix renders the full SPARTA v3.0 framework (177 leaf
technique IDs) but the NOS3 detector only carries a verdict for 32. This document
triages *every* SPARTA technique into **not-applicable / applicable-not-validated
/ done**, and — for the applicable ones — records the signal class and which MID
(if any) would move it in-scope. It answers "how much of SPARTA can NOS3 actually
cover, and what's the backlog?" and drives the MID-subscription decision.

**Created:** 2026-07-15. **Sources:** `SPARTA_DATA` in `app/sparta_coverage.html`
(v3.0), the 154 scripts under `gsw/attack_scripts/sparta/`, the 32-technique
validated corpus (`app/gen_nos3_coverage.py::ENRICH`), the 4-class signal taxonomy
(`V5_DETECTOR_COVERAGE.md` §C), and the telemetry-MID inventory.

## Two verdicts that are easy to confuse: Not-Applicable vs Out-of-Scope

This document rules techniques out for two *different* reasons, on two different
axes. Both mean "not in the detection backlog," but they are not the same verdict —
the tell is whether the attack could even *run* against the sim.

- **Not-applicable (N/A, Section D)** — the attack **can't happen in NOS3**. It
  targets something the simulation doesn't model at all (physical/RF/ground/off-board/
  no-payload), so there is no attack surface and nothing to simulate. "Would we detect
  it?" is moot because the *action itself* has no representation. Axis: **the target
  doesn't exist in the model.** E.g. reconnaissance, jamming, ASAT, ground-segment.
- **Out-of-scope (CONCEPTUAL, Section C)** — the attack **is applicable and could
  actually run** on the modeled spacecraft (it hits the flight software, crypto lib,
  or on-board values), but it produces **no observable telemetry footprint by
  construction**, so a telemetry-based monitor can *never* catch it — and no added MID
  or schema change fixes that. Axis: **the target exists, but is structurally
  unobservable.** E.g. crypto (CryptoLib emits zero SB telemetry), self-hiding
  rootkits/backdoors, untelemetered registers.

| | Attack surface in NOS3? | Detectable in principle? | Would adding a MID help? |
|---|:--:|:--:|:--:|
| **Not-applicable** (D) | ❌ no | — (moot) | — |
| **Out-of-scope / CONCEPTUAL** (C) | ✅ yes | ❌ never | ❌ no |

Out-of-scope therefore lives *under* the "applicable" branch: the triage first asks
*"does this attack apply to NOS3?"*, and only the applicable techniques split into
**in-scope-now** (Section A — detectable, needs corpus validation), **unsubscribed**
(Section B — detectable *if* a MID is added), and **CONCEPTUAL/OOS** (Section C —
applicable but permanently undetectable). Not-applicable (Section D) is the separate,
earlier fork where the attack never touches NOS3 at all. One-line contrast: an
out-of-scope technique *does something you can't see*; a not-applicable one *has
nothing to run against in the first place*.

## The filter: what an on-board FSW monitor can even see

OnAIR sees only the cFS Software Bus telemetry it subscribes to. That makes five
of the nine SPARTA tactics **structurally undetectable on-board**, regardless of
whether a script exists:

| Tactic | Leaf IDs | Verdict | Why |
|---|--:|---|---|
| **Reconnaissance** (REC) | ~27 | **N/A** | Off-board info-gathering about the target; nothing happens on the spacecraft |
| **Resource Development** (RD) | ~15 | **N/A** | Attacker building infra/malware off-board |
| **Initial Access** (IA) | ~16 | **N/A** | The *entry vector* (ground/supply-chain/RF). Its on-board *result* — a malicious command or code — is a separate EX technique, which is where we detect |
| **Lateral Movement** (LM) | 7 | mostly **N/A** | Payload/crosslink/VM/proximity — NOS3 is a single sat with no hosted payload or VM. Exception: LM-0002 (bus segregation) is on-board-observable |
| **Exfiltration** (EXF) | 16 | mostly **N/A** | Physical side-channels, RF, off-board sites. Exception: EXF-0003.02 downlink exfil (observable via the telemetry-output path) |

Scripts exist for many of these (REC/RD/IA skeletons), but a script ≠ detectability.

The **on-board-detectable universe** is therefore **Execution (48) + Persistence
(6) + Defense Evasion (28) + Impact (6) + the 2 exceptions above = ~90 leaf IDs.**
Of those, **32 are validated (done)** and **all 6 Impact techniques are done.**

## Headline

- **177** SPARTA leaf techniques total; **154** scripts on disk; **32** validated in
  the detection corpus.
- **~90** are in the on-board-detectable universe. **32 done**, **~58 not done**.
- Of the 58 not done: **13 are applicable + in-scope now** (the concrete Section A
  enumeration below; the earlier "~18" was a loose estimate), **~7 are applicable but
  UNSUBSCRIBED** (Section B — need a MID), **~33 are CONCEPTUAL** (Section C —
  structurally unobservable, permanent out-of-scope), and **~5 are borderline ON_BOARD
  candidates held out** pending a live footprint check (`EX-0001.02`, `DE-0006`,
  `EX-0005.01`). That reconciles: 13 + 7 + 33 + 5 = 58.

## A. Applicable · in-scope now · NOT yet validated (the real backlog)

These have (or can trivially have) a script, produce a footprint in an
**already-subscribed** MID, and just need to be run + validated + folded into the
corpus. **Cheapest breadth wins.**

| ID | Technique | Script? | Footprint / observable via |
|---|---|:--:|---|
| EX-0002 | PNT Geofencing | ✅ | NOVATEL/GPS position fields |
| EX-0005.02 | Malicious Use of Hardware Commands | ✅ | component HK command counters |
| EX-0011 | Exploit Reduced Protections in Safe-Mode | ✅ | ADCS/SC mode change |
| EX-0012.02 | Internal Routing Tables | — | `CFE_SB_SUBS` (subscribed) — new/altered routes |
| EX-0012.10 | Command & Data Handling Subsystem | — | `CFE_ES`/`CFE_SB` counters |
| EX-0013.01 | Flooding — Valid Commands | ✅ | EVS send-rate + command counters (DoS flood; validate standalone — doesn't fit the all-modes-dwell window) |
| EX-0013.02 | Flooding — Erroneous Input | ✅ | `CFE_SB`/subsystem CommandError family (garbage rejected upstream) |
| EX-0014.02 | Bus Traffic Spoofing | ✅ | injected SB messages vs `CFE_SB_SUBS` |
| DE-0002.03 | Inhibit Spacecraft Functionality | ✅ | subsystem HK going quiet / error counts |
| DE-0005 | Subvert Protections via Safe-Mode | ✅ | mode change (sibling of EX-0011) |
| DE-0010 | Overflow Audit Log | ✅ | **EVS sent-rate** — `CFE_EVS_HK.MessageSendCounter` + `AppData[CFE_EVS].AppMessageSentCounter` spike (validated 2026-07-16: ON_BOARD, but the deployed IF misses it — squelched-counter does NOT fire) |
| PER-0001 | Memory Compromise | ✅ | sibling of EX-0012.03 memory write |
| LM-0002 | Exploit Lack of Bus Segregation | ✅ | `CFE_SB_SUBS` — traffic crossing to unexpected apps |

## B. Applicable · UNSUBSCRIBED · needs a MID to become detectable

Footprint exists but in a MID OnAIR does **not** subscribe to. **This section drives
the MID decision** — a MID is only worth adding if it moves a technique here (or a
DEAD class) in-scope. Map:

| Candidate MID | Unlocks (moves in-scope) |
|---|---|
| **`TO_LAB_HK` (0x08E8)** — telemetry output | **EXF-0003.02** downlink exfiltration · sharpens **IMP-0006** theft (currently UNSUBSCRIBED, detected only by side-effect) |
| **`LC_HK` (0x08A7)** — limit checker | **DE-0001** Disable Fault Management (watchpoint/actionpoint state) |
| **`DS_HK` (0x08B8)** + **`FM_HK` (0x088A)** — data storage / file mgr | **EX-0010.01** Ransomware · **EX-0010.02** Wiper (file create/delete/write counters) |
| **`CI_LAB_HK` (0x08E0)** — command ingest | sharpens the command-injection family (EX-0013.*, DE-0003.01/02) at the ingress |
| **sensor DEVICE pkts** (0x0911/21/26/2B/36) | sharpens **EX-0014.03** sensor spoof (currently DEAD) at the source, beyond the fused `ADCS_DI` view |
| *(watchdog MID — may not exist)* | **EX-0012.11 / DE-0003.11** WDT — verify a subscribable WDT/health packet exists before counting on this |

Note the pipe budget: `CFE_SBN_CLIENT_MAX_MSG_IDS_PER_PIPE = 32`, **21 used → ~11
free**. Prioritize MIDs by how many rows above they unlock, then **re-collect +
re-measure** (the AINOS3-30 lesson: a MID only helps if an attack perturbs it).

## C. Applicable on-board but CONCEPTUAL — permanent out-of-scope

No amount of telemetry helps; the technique has no observable on-board footprint by
construction. Do **not** spend corpus/MID effort here. These attacks *could* run
against the sim — they just leave no trace (see *Two verdicts that are easy to
confuse* above: out-of-scope ≠ not-applicable).

- **Crypto (CryptoLib has zero SB telemetry):** EX-0003 modify-auth, EX-0006
  disable-encryption, PER-0004 replace-keys, DE-0003.07 crypto-modes *(done, OOS)*.
- **Self-hiding malware:** EX-0010.03/.04 rootkit/bootkit, DE-0007/08 evasion-via-
  rootkit/bootkit, PER-0002.01/.02 backdoors, DE-0004 masquerading, DE-0011
  credentialed-evasion.
- **OS/vuln/registers/AI-poison:** EX-0009.02 OS, EX-0009.03 known-vuln, EX-0012.01
  registers (not telemetered), EX-0012.13 / DE-0003.12 poison-AI/ML *(off-board)*.
- **Already-classified OOS from the corpus:** EX-0001.01 replay, EX-0009.01 FSW
  exploit, IMP-0004 degradation, DE-0003.04 RSSI, DE-0003.05 lock-modes.

## D. Not applicable to NOS3 (physical / RF / ground / no-payload)

The attack surface isn't modeled, so the technique can't even run against the sim —
distinct from Section C's out-of-scope, which *can* run but leaves no footprint (see
*Two verdicts that are easy to confuse* above). Whole-tactic N/A (REC, RD, IA) plus: SEU (EX-0007), ASAT (EX-0017.*), directed
energy (EX-0018.*), jamming (EX-0016.*, DE-0002.02), missile spoof (EX-0014.05),
side-channels (EX-0015, EXF-0002.*), boot ROM (EX-0004), science/payload (EX-0012.06,
EXF-0010, LM-0001/0006), space-domain-awareness (DE-0009.*), ground-segment
(DE-0002.01, EXF-0007/08/09, PER-0003), constellation/crosslink/VM/proximity
(LM-0003/04/05, EXF-0004/05/06). NOS3 models none of these targets.

## Recommended sequencing

1. **Cheapest breadth first (Section A):** validate the ~11 in-scope-now techniques
   into the corpus. Most already have scripts; this roughly *doubles* validated
   coverage of the detectable universe with no new MIDs and no schema change.
2. **Then targeted MIDs (Section B), backward from the taxonomy:** add the MID(s)
   that unlock the most rows — `TO_LAB_HK` (exfil + theft) and `DS_HK`/`FM_HK`
   (wiper/ransomware) are the highest-leverage; the sensor DEVICE packets are the
   bet on the EX-0014.03 DEAD class. Re-collect + re-measure after each.
3. **Document C/D as closed:** the CONCEPTUAL and N/A sets are out-of-scope *by
   construction*; recording that is itself a coverage answer (we cover ~X of ~90
   detectable techniques, not X of 177).

**Note on numbers:** counts are "~" because a handful of techniques are judgment
calls at the ON_BOARD/UNSUBSCRIBED/CONCEPTUAL boundary (e.g. DE-0006 modify-
whitelist, LM-0002 bus-segregation). Each such call is resolved the same way any
footprint is — run it against the live FSW and read the telemetry (evaluation-
provenance), not by assumption.
