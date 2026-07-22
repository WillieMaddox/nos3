# SPARTA Coverage Triage — NOS3 OnAIR Monitor

**Purpose.** The coverage-overview page (`app/sparta_coverage.html`) renders the full SPARTA v3.0 framework (177 leaf
technique IDs). The NOS3 detector now carries a verdict for **45**: **32** in the
classifier corpus + the **13 Section-A techniques gate-validated** in the 2026-07-17
campaign. This document triages *every* SPARTA technique into **not-applicable /
applicable-not-validated / done**, and — for the applicable ones — records the signal
class and which MID (if any) would move it in-scope. It answers "how much of SPARTA can
NOS3 actually cover, and what's the backlog?"

**Created:** 2026-07-15. **Last updated:** 2026-07-17 (Section A all validated; Section
B MIDs now subscribed). **Sources:** `SPARTA_DATA` in `app/sparta_coverage.html`
(v3.0), the 154 scripts under `gsw/attack_scripts/sparta/`, the classifier corpus +
`GATE_DETECTED` (`app/gen_nos3_coverage.py`), the 4-class signal taxonomy
(`V5_DETECTOR_COVERAGE.md`), and the telemetry-MID inventory.

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

- **177** SPARTA leaf techniques total; **154** scripts on disk.
- **~90** are in the on-board-detectable universe. **45 validated** = **32** in the
  classifier detection corpus + **13 Section-A gate-validated** (all live-verified
  through 2026-07-17; caught by the rule-gate / consistency / staleness gates the
  dynamics-IF misses).
- The remaining ~45 split: **~7 are Section B** (their MID is now SUBSCRIBED after the
  16-MID pass, but detection isn't built/validated yet — no longer "needs a MID"),
  **~33 are CONCEPTUAL** (Section C — structurally unobservable, permanent out-of-scope),
  and **~5 are borderline ON_BOARD candidates held out** pending a footprint check
  (`EX-0001.02`, `DE-0006`, `EX-0005.01`). That reconciles: 45 + 7 + 33 + 5 = 90.

## A. Applicable · in-scope now · ✅ ALL 13 VALIDATED (campaign complete 2026-07-17)

All 13 have a script, produce a footprint in an **already-subscribed** MID, and were
**validated live against the FSW** — see [`COVERAGE_VALIDATION_BACKLOG.md`](COVERAGE_VALIDATION_BACKLOG.md)
for the per-technique writeups. Key finding: the dynamics-IF is *blind* to the
flag/counter/freeze/spoof class, so most are caught by the parallel gates
(rule-gate R1–R10, consistency-check, staleness-check); two also perturb physics enough
for the IF. Several footprint guesses in the original table were **wrong** and are
corrected below.

| ID | Technique | Script? | Detected by (validated) | Footprint / observable via |
|---|---|:--:|---|---|
| EX-0002 | PNT Geofencing | ✅ | rule-gate R1 | `NOVATEL_HK.DeviceEnabled 1→0` (position barely moves in SUNSAFE; HK freezes on aged stacks — repro on a fresh launch) |
| EX-0005.02 | Malicious Use of Hardware Commands | ✅ | R1 + dynamics-IF (78 %) | device `CommandCount` climbs, NO cmd-errors; TORQUER disable + thruster/RW physics |
| EX-0011 | Exploit Reduced Protections in Safe-Mode | ✅ | R5/R1 + dynamics-IF (52 %) | LC state + CSS/EPS/thruster (**NOT ADCS mode** — corrected) |
| EX-0012.02 | Internal Routing Tables | ✅ | staleness + R6 | route-disable freezes the MID; `CFE_SB.CommandCounter` is the command signal (**`CFE_SB_SUBS` NOT observable**, reads `[0]`) |
| EX-0012.10 | Command & Data Handling Subsystem | ✅ | R8 | `CFE_ES.CommandCounter` + `MaxProcessorResets` (SET_MAX_PR_COUNT) |
| EX-0013.01 | Flooding — Valid Commands | ✅ | R2 (+R3/R6/R7) | EVS send-rate spike (labeled DE-0010 — shared footprint) |
| EX-0013.02 | Flooding — Erroneous Input | ✅ | R4 | subsystem `CommandError` family (garbage rejected upstream; `MsgReceiveErrorCounter` stays 0) |
| EX-0014.02 | Bus Traffic Spoofing | ✅ | consistency-check | per-sample wide counter jumps backwards (**`CFE_SB_SUBS` NOT observable**) |
| DE-0002.03 | Inhibit Spacecraft Functionality | ✅ | staleness + R7 | `CFE_EVS_HK.MessageSendCounter` freeze (EVS event-type suppress) |
| DE-0005 | Subvert Protections via Safe-Mode | ✅ | R5 + staleness | LC state (sibling of EX-0011); forced ADCS `SET_MODE` = an IF warmup blind spot |
| DE-0010 | Overflow Audit Log | ✅ | R2 | EVS send-rate `CFE_EVS_HK.MessageSendCounter` (squelch does NOT fire; IF stays blind) |
| PER-0001 | Memory Compromise | ✅ | R9 | `CFE_TBL.CommandCounter` (evidence-hiding `CFE_TBL_RESET` survived by the running-max) |
| LM-0002 | Exploit Lack of Bus Segregation | ✅ | R10 bus-sweep | ≥3 static command counters trip together (**`CFE_SB_SUBS` NOT observable**) |

## B. Applicable · MID now SUBSCRIBED · pending validation (was: UNSUBSCRIBED)

**Updated 2026-07-16/17 — the MID bottleneck is largely resolved.** The 16-MID
subscription pass (AINOS3-30) added *every* candidate MID below to OnAIR (pipe cap
`CFE_SBN_CLIENT_MAX_MSG_IDS_PER_PIPE` raised **32 → 48**). They are now **recorded but
not yet turned into features/detections** — subscribing only helps if an attack
perturbs the MID *and* a feature/rule reads it (the AINOS3-30 lesson: the CFE_TBL
change-detect features read constant-0 and were kept dormant). So this is no longer
"needs a MID"; it is **"MID present, detection not yet built/validated"** — the
successor backlog to Section A.

| MID (now subscribed as) | Could unlock | Status / finding |
|---|---|---|
| **`TO` (TO_LAB_HK 0x08E8)** | **EXF-0003.02** downlink exfil · sharpen **IMP-0006** theft | subscribed (`TO.Payload.*`); not yet validated |
| **`LC` (LC_HK 0x08A7)** | **DE-0001** disable fault management | subscribed + **already in use** (R5 `LC.CurrentLCState`, staleness `LC.MonitoredMsgCount`); DE-0001 itself not yet validated |
| **`DS` + `FM` (0x08B8 / 0x088A)** | **EX-0010.01** ransomware · **EX-0010.02** wiper | subscribed (`DS.Payload.FileWriteCounter` etc., `FM.*`); not yet validated |
| **`CI` (CI_LAB_HK 0x08E0)** | command-injection family at the ingress | subscribed, but **NOT a cmd-injection signal in NOS3** — externally injected commands hit the `:5012` UDP→SB bridge and **bypass CI_LAB**, so `CI.Payload.IngestPackets` doesn't move (found during DE-0010) |
| **sensor DEVICE pkts** (`IMU_DEV`/`CSS_DEV`/`MAG_DEV`/`FSS_DEV`/`ST_DEV`) | sharpen **EX-0014.03** sensor spoof (DEAD) | subscribed, but **redundant** with the fused `ADCS_DI` view and the freeze isn't IF-detectable (AINOS3-30 NULL / EX-0014.03 finding); kept dormant |
| *(watchdog MID)* | **EX-0012.11 / DE-0003.11** WDT | **still UNSUBSCRIBED — no subscribable WDT/health packet exists** in this build (verified 2026-07-17) |

Net: the remaining work is **turning the newly-recorded MIDs into validated detections**
(a new backlog), not adding MIDs. Watchdog (EX-0012.11 / DE-0003.11) is the only genuine
UNSUBSCRIBED holdout, and it may have no telemeterable packet at all.

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

1. **Section A — ✅ DONE (2026-07-17).** All 13 in-scope-now techniques are validated
   live; the campaign built the 4 detector gates (rule-gate R1–R10, consistency-check,
   staleness-check) for the classes the IF misses. Folded into the coverage overview +
   `V5_DETECTOR_COVERAGE.md`. (Gate-detected → validated standalone, not folded into the
   classifier training corpus — the classifier is IF-gated and wouldn't learn them.)
2. **Section B — MIDs now SUBSCRIBED; build the detections (the current backlog).** The
   16-MID pass already added `TO`/`DS`/`FM`/`CI`/`LC` HK + sensor DEVICE packets, so the
   remaining work is turning them into validated detections, not adding MIDs. Highest
   leverage: `TO` (exfil + theft) and `DS`/`FM` (wiper/ransomware). Two findings narrow
   it: `CI` is not a command-injection signal (`:5012` bypass) and the sensor DEVICE
   packets are redundant with `ADCS_DI` (AINOS3-30 NULL). Watchdog (EX-0012.11/DE-0003.11)
   is the only genuine unsubscribed holdout — verify a WDT packet even exists.
3. **Document C/D as closed:** the CONCEPTUAL and N/A sets are out-of-scope *by
   construction*; recording that is itself a coverage answer (we cover ~X of ~90
   detectable techniques, not X of 177).

**Note on numbers:** counts are "~" because a handful of techniques are judgment
calls at the ON_BOARD/UNSUBSCRIBED/CONCEPTUAL boundary (e.g. `DE-0006` modify-
whitelist, still held out). LM-0002 bus-segregation *was* one such call — it has since
been resolved ON_BOARD and validated (Section A). Each such call is resolved the same
way any footprint is — run it against the live FSW and read the telemetry (evaluation-
provenance), not by assumption.
