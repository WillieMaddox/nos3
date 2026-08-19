# NOS3 OnAIR Security Monitor — What It Catches / What It Doesn't

**Audience:** mission, security, and program stakeholders (no ML background assumed).

**Scope:** the v5 anomaly detector + the v3-hybrid attack classifier (selective
per-mode heads) + the four parallel detector gates (rule-gate R1–R14,
consistency-check, staleness-check) currently deployed in the OnAIR plugin against
the NOS3 cFS flight software.

**Last updated:** 2026-08-19 — folded in AINOS3-78: the `EX-0012.{03,04,05}` sibling
cluster's *labeling* regressed under the deployed hybrid, the loss is **entirely INERTIAL**,
and the mitigation is recommended but **not deployed** (Section B.1). Detection is unaffected.

**Previously:** 2026-08-15 — a 24-run replication **resolved** the question of whether the
catch rates only measure manoeuvre transients (they do not; boxed note in Section 2), but
found that the Catch column **credits the IF with rule-gate detections** and that
**`EX-0012.09` is detected by nothing** in steady flight. Added R14 mode-force + flapping
detection, the AINOS3-80 provenance tags, and the AINOS3-81 soak results including an
INERTIAL false-alarm problem now measured at **33.6 %** nominal.

**Previously:** 2026-07-30 (Sprint 26 — folded in the Section-B detections
EX-0010.01/.02, EXF-0003.02, DE-0001, DE-0006; resolved the watchdog pair +
EX-0001.02 out-of-scope and EX-0005.01 not-applicable, closing the last
not-evaluated leaves; **deployed the AINOS3-37 selective per-mode hybrid classifier**
— live-verified 2026-07-30, both per-mode heads exercised; **moved the coverage overlay's
incident-label numbers to honest hybrid out-of-fold** — 42.3 % vs the v3 global head's
34.6 % OOF, replacing the in-sample-optimistic 76.9 %). Numbers are from attack scripts empirically validated
against live FSW and from calibrated nominal soaks — not from simulation
assumptions.

**Provenance convention (AINOS3-80).** Every metric here carries a tag: **`[OOF]`**
out-of-fold · **`[live-soak]`** independent nominal flight · **`[in-sample]`** measured on
fitted data · **`[design-target]`** a configured parameter, not a measurement. An untagged
number is a bug. Intervals must state *what was resampled* — resampling test rows alone
understates uncertainty on a single-instance corpus. Full register:
[`AINOS3_80_METRIC_PROVENANCE.md`](AINOS3_80_METRIC_PROVENANCE.md).

---

## Bottom line

The monitor is a **two-stage on-board sentry** watching ~250 spacecraft
telemetry fields at ~5 Hz:

1. **Stage 1 — "Is something wrong?"** A per-flight-mode anomaly detector
   (Isolation Forest) raises an alarm when telemetry leaves the envelope it
   learned from nominal flight. **Tuned to ≤ 1 % false-alarm rate**
   `[design-target]`; **measured 0.0–0.2 % in steady-state flight**
   `[live-soak]`.
2. **Stage 2 — "What kind of attack?"** When Stage 1 alarms, an attack
   classifier (gradient-boosted trees) labels the event with a SPARTA
   technique (e.g. *EX-0012.07 propulsion command*). **~65 % correct
   technique identification on novel runs** `[OOF]` (0.645 ± 0.036 over three
   instances — the spread is wider than most differences we quote against it).
   The deployed classifier is the
   **selective per-mode hybrid** (AINOS3-37): the signal-rich INERTIAL/SUNSAFE
   modes route to their own per-mode heads (+0.06 each, ROBUST +0.10) while
   PASSIVE/BDOT keep the global head (no regression), with per-mode confidence
   calibration so a reported confidence means the same thing across heads.
3. **Parallel gate layer — "What the dynamics model can't see."** Four
   complementary gates run *beside* the IF for attacks whose footprint is a
   discrete flag/counter change, a transient spoof, or a frozen stream — none
   of which perturb the physics Stage 1 watches: **rule-gate (R1–R14)**,
   **consistency-check** (per-sample bus-spoof), and **staleness-check**
   (telemetry-freeze). The firing rule *is* the label, so no classifier is
   needed for this class. See *"Complementary detector gates"* below.

**What this means operationally:**

| Question | Answer |
|---|---|
| Will it cry wolf? | Rarely — under 1 alarm per ~5 hours of nominal flight. |
| Will it catch a real attack? | **Yes — at the incident level, 93 % of genuinely detectable state-change attacks raise an alert** (vs ~61 % of individual frames; one alert per attack is what matters). Detection is strongest in SUNSAFE; weaker in other modes. |
| Will it tell me *which* attack? | For ~8 techniques, yes with high confidence. For others it narrows to a *family* of indistinguishable techniques. A handful it cannot label at all (documented below). |
| Does Stage 2 catch things Stage 1 misses? | **No** — Stage 2 only *sharpens* what Stage 1 flagged. **But the parallel gate layer does** — it catches 13 validated Section-A techniques (flag/counter/spoof/freeze) the dynamics-IF is structurally blind to. |

---

## What it catches well

### 1. Nominal flight without false alarms (all four ADCS modes)

Every alarm during a known-nominal soak is, by definition, a false positive.
Measured steady-state false-positive rate (post warm-up + hysteresis):

All figures below are `[live-soak]` — independently collected nominal flight, never used
in any fit.

| ADCS mode | Originally published | AINOS3-81 soak (7 h) | Steady-flight replication (12 runs, 600 s hold) |
|---|---|---|---|
| SUNSAFE | 0.20 % | **0.02 %** ✅ | **0.74 %** raw (0.35–1.00 % across runs) |
| PASSIVE | 0.00 % | **0.00 %** ✅ | not re-measured |
| BDOT | 0.00 % | **0.00 %** ✅ | not re-measured |
| **INERTIAL** | ~~0.00 %~~ | 0.54 % op / 7.5 % raw | ⚠ **33.6 %** (21.1–48.5 %) |

**Three of four modes are well inside the 1 % design target. INERTIAL is not**, and the
figure has grown with every measurement (0.00 % → 7.5 % → 33.6 %). An earlier worry that
INERTIAL and BDOT were "too noisy to use" was previously recorded as *disproved*; for BDOT
that still holds, **for INERTIAL it does not**.

> ⚠ **INERTIAL is currently unusable for detection (updated 2026-08-17).** The nominal
> false-alarm rate has grown with every measurement: 0.00 % published (116 min) → 7.5 % raw
> over a 7 h soak → **33.6 % across 12 runs at a 600 s hold**. The "short-run settling
> transient" explanation offered for the middle figure is **refuted** — 10 minutes is not
> enough for it to subside. Every INERTIAL attack-detection measurement sits on this noise
> floor and is uninterpretable, so the mode cannot presently be evaluated for coverage at
> all. In-sample threshold calibration (AINOS3-80 **F1**) contributes but does not explain
> 33.6 %; candidate second factors are a training gap (19,641 rows from a single 116-min
> session), a missing commanded target quaternion that our tooling never sends, or genuinely
> long settling. Ticketed as AINOS3-86 (High).
> ⚠ **Do not fix by tightening the threshold** — that drives INERTIAL's false alarms to 0.00 %
> but collapses its attack detection 60×. Earlier AINOS3-81 detail:
> [`AINOS3_81_HYBRID_DRIFT_SOAK.md`](AINOS3_81_HYBRID_DRIFT_SOAK.md).

**Long-uptime stability re-confirmed on the deployed hybrid (7 h soak, 2026-08-11,
AINOS3-81).** Across a 4 h SUNSAFE leg spanning uptime T+3h→T+7h — the band where v2 was
suspected of drifting — operational FP held at **0.01 %** and the 1st-percentile score
margin **widened** (0.052 → 0.086) rather than plateauing. Staleness and consistency gates
logged 0 alerts over 141 K frames; the rule-gate logged 2 edges in 7 h; the classifier
raised **0 false attack labels** on 2,203 IF-gated nominal frames. `[live-soak]`

**Long-uptime stability (6.6 h SUNSAFE soak, 2026-06-09).** A predecessor
detector (v2) was suspected of drifting to 50–97 % false alarms after 4–6 h of
continuous uptime. v5 does **not**: across 100 K frames / 6.6 h the operational
false-alarm rate stayed at **0.01 %**, with no progressive climb. The internal
anomaly-score margin settles during the first ~2 h then **plateaus** (1st-
percentile score holds ≈ 0.06–0.08 against a ~0 alarm threshold) — i.e. it
stops shrinking, rather than marching toward the threshold. One brief excursion
near T+6 h (0.4 % raw) self-recovered within minutes and was suppressed to
0.04 % by hysteresis. The long-uptime drift concern is considered **closed for
SUNSAFE**.

### 2. Attack detection — strong in SUNSAFE

In SUNSAFE mode, **15 of 23 state-changing techniques are caught ≥ 50 %** of
their corruption window, many at or near 100 %. Provenance: `[unverifiable]` per
AINOS3-80 **F2** — the attack rows were never fitted (the IF trains on nominal only), but
the IF's training-corpus identity is unrecorded, so disjointness cannot be proven:

> ### ⚠ RESOLVED (2026-08-15) — the Catch column conflates detectors; one real gap found
>
> A 24-run replication (4 techniques × 2 modes × 3 reps, one ADCS mode held throughout,
> scoring attack frames against each run's OWN nominal) **retired an earlier concern that
> these rates might only measure manoeuvre transients.** They do not. But it found two things
> that do need stating:
>
> **1. This column credits the IF with detections the rule-gate makes.** Three of the four
> techniques tested are *discrete state changes*, not dynamics attacks — `EX-0012.08` sends
> `ADCS_SET_MODE`, `EX-0014.04` disables the GPS receiver, `EX-0012.09` toggles an EPS switch.
> The dynamics IF is structurally blind to those by design, which is why the gate layer exists.
> Measured in steady flight: `EX-0012.08` → caught by **R14** (2/3 reps), `EX-0014.04` → caught
> by **R1** (2/3) / R3 (1/3), IF lift ≈ 0 for both. The attacks are detected; the Catch column
> attributes it to the wrong component.
>
> **2. `EX-0012.09` (EPS, published 99 %) is detected by NOTHING in steady flight** — 0/3 reps,
> no IF lift, no rule fired. A genuine coverage gap; ticketed.
>
> **The IF is vindicated where it is the right detector.** `EX-0012.07` propulsion — a genuine
> sustained-dynamics attack — measured **+77.5 ± 3.6 lift** across three runs (≈ 78–82 % of
> attack frames against ≈ 1 % nominal). When there are dynamics to see, it sees them.
>
> **Method note.** An earlier 16-run pilot suggested the detector failed broadly in steady
> flight. That was a technique-selection error: it measured the IF's response to attacks the
> rule-gate owns. Both that pilot and the first reading of this replication were wrong in the
> same way. Recorded so the next person does not repeat it — **check what an attack script
> actually commands before deciding which detector should see it.**
>
> Detail: the per-mode-pilot and replication sections of [`SPRINT_27_PLAN.md`](SPRINT_27_PLAN.md).

| Technique | Catch rate | Technique | Catch rate |
|---|--:|---|--:|
| EX-0012.07 propulsion | **100 %** | EX-0008.02 RTS | 91 % |
| EX-0012.08 ADCS | **100 %** | IMP-0005 destruction | 75 % |
| IMP-0003 denial | **100 %** | EX-0012.05 scheduler | 64 % |
| EX-0012.09 EPS | ⚠ **0 %** (see note) | EX-0012.04 app tables | 63 % |
| EX-0014.04 PNT spoof | 98 % | IMP-0006 theft | 62 % |
| EX-0014.03 sensor spoof | 91 % | IMP-0001 deception | 61 % |
| EX-0008.01 ATS | 91 % | IMP-0002 disruption | 58 % |
| EX-0012.12 system clock | 57 % | | |

### 3. Incident-level detection — the operational view

The percentages above are *frame-level* (what fraction of an attack's frames
were flagged). Operators don't act on frames — they act on **incidents** ("an
alert began at T and lasted N seconds"). The monitor now collapses a
hysteresis-confirmed run of flagged frames into one incident, and an attack
counts as caught if it raises **at least one** incident. Re-scoring the labeled
corpus at this granularity:

| Metric | Value | Provenance |
|---|---|---|
| Incident recall — genuinely detectable state-change attacks | **92.8 % (77/83)** | `[unverifiable]` — see AINOS3-80 **F2** |
| Incident recall — all SPARTA techniques (incl. undetectable-by-design) | 67.8 % (78/115) | `[unverifiable]` — see AINOS3-80 **F2** |
| Incident label accuracy (of detected; deployed hybrid) | **42.3 %** (v3 global head 34.6 % on identical folds; the old 76.9 % was in-sample-optimistic) | `[OOF]` |

> **Why "unverifiable" and not "wrong" (AINOS3-80 F2).** The IF trains on *nominal* frames
> only, so the attack rows scored here were certainly never fitted. But the deployed IF
> pickle records no training-corpus identity — no csv-dir, manifest list, or collection
> dates — so we cannot *prove* its nominal training rows are disjoint from the corpus these
> recalls are measured on. Circumstantial evidence favours disjointness (dedicated baseline
> runs; 87,398 training rows vs the corpus's 206,373). Recording training inputs in the
> artifact, as the classifier already does, would close this.

**The jump from ~61 % (frame) to ~93 % (incident) is the whole point of the
incident layer:** even a brief burst of flagged frames during an attack raises
exactly one alert, so attacks that are "only" caught 60 % of their frames are
caught ~100 % of the time as *events*. The residual gap is the
structurally-undetectable techniques (Sections B & C), not tuning. Only four
detectable attacks miss in some runs (`DE-0003.09`, `EX-0012.04`/`.04-prereq`,
`EX-0012.08`).

> **False-alarm caveat — read this.** The corpus also produced 766 "false
> incidents," but that number is **not** the operational false-alarm rate. The
> attack corpus's nominal windows use a different command cadence
> (`all_modes_dwell` @ 30 s) than the detector's training baseline, which the IF
> flags heavily by construction. The real nominal false-alarm rate is the soak
> number — **0.01 %** (Section 1) — not the corpus number.

### 4. Attack identification — confidence tiers

When Stage 1 alarms, the classifier names the technique. Reliability varies by
technique, so we report it in tiers (measured by leave-one-instance-out
cross-validation — i.e. accuracy on a spacecraft run the model never saw):

- **ROBUST (trust the label):** `DE-0003.01`, `DE-0003.10`, `EX-0008.02`,
  `IMP-0005` — F1 ≥ 0.85 on every split.
- **STABLE-MID (good as a top-3 suggestion):** `IMP-0002`, `IMP-0003`,
  `IMP-0006`, plus the `nominal` label.
- **HIGH-VARIANCE (label is a hint, not a verdict):** `EX-0008.01`,
  `EX-0012.07/.08/.09`, `EX-0014.04` — correct on some runs, not others.
- **DEAD (cannot be labeled as-is):** see next section.

Overall technique-identification accuracy is **~65 %** (top-1, novel run;
deployed selective per-mode hybrid, LOIO 0.646) — calibrated, not overfit
(held-out and cross-validated numbers agree within ~1 point). The hybrid keeps
the global head's overall level while banking the dynamic-mode gains
(INERTIAL/SUNSAFE +0.06 each, ROBUST +0.10) at zero PASSIVE/BDOT cost.

### 5. Complementary detector gates (what the dynamics-IF can't see)

The Section-A coverage campaign (AINOS3-50…62, live-verified through 2026-07-17)
proved the IF is a *dynamics* detector: blind to attacks whose footprint is a
discrete flag flip, a static-counter increment, a transient spoof, or a frozen
stream. Four lightweight gates run in parallel with the IF to close that gap. The
rule that fires *is* the label (no classifier needed), and each was live-verified
raising an incident:

- **rule-gate (R1–R14):** R1 device-disable · R2 EVS-rate · R3 SB-errors · R4
  cmd-errors · R5 monitor-state (LC/HS; fault-management disable DE-0001/EX-0011/DE-0005)
  · R6/R7/R8/R9/R11/R12 static-in-nominal command counters (CFE_SB / CFE_EVS / CFE_ES /
  CFE_TBL / FM / TO) · R10 bus-sweep meta-rule · R13 downlink route-mask change ·
  **R14 ADCS mode-force** (debounced `ADCS_GNC.Mode` transition = DE-0005) · **R14 mode-flap**
  (3 confirmed transitions in ~5 min = deliberate farming of the post-switch blind window;
  caught a simulated attacker at 121 s, live-verified 2026-08-15).
- **consistency-check:** per-sample counter-monotonicity — catches an injected
  spoof (a counter that jumps backwards) the IF and rule-gate both miss.
- **staleness-check:** a wide monotonic counter's max stops advancing — catches
  telemetry-denial / frozen streams (route-disable, EVS-suppress).

**13 Section-A techniques now caught by the gate layer** (all ON_BOARD; the IF
scores them is_anomaly≈0 unless noted):

| SPARTA | Technique | Caught by |
|---|---|---|
| EX-0002 | PNT geofencing (GPS disable) | rule-gate R1 → EX-0002 incident |
| EX-0005.02 | Malicious use of HW commands | rule-gate R1 + dynamics-IF (78 %) |
| EX-0011 | Exploit reduced protections in safe-mode | rule-gate R5/R1 + dynamics-IF (52 %) |
| EX-0012.02 | Internal routing tables | staleness-check + rule-gate R6 |
| EX-0012.10 | C&DH subsystem (CFE_ES value mod) | rule-gate R8 → EX-0012.10 incident |
| EX-0013.01 | Flooding — valid commands | rule-gate R2 (labeled DE-0010) |
| EX-0013.02 | Flooding — erroneous input | rule-gate R4 (cmd-error family) |
| EX-0014.02 | Bus traffic spoofing | consistency-check |
| DE-0002.03 | Inhibit spacecraft functionality | staleness-check + rule-gate R7 |
| DE-0005 | Subvert protections via safe-mode | rule-gate R5 + **R14 mode-force** + staleness-check |
| DE-0010 | Overflow audit log | rule-gate R2 → DE-0010 incident |
| PER-0001 | Memory compromise | rule-gate R9 → PER-0001 incident |
| LM-0002 | Exploit lack of bus segregation | rule-gate R10 bus-sweep → LM-0002 incident |

This is the direct answer to the old "Stage 2 doesn't widen the net" caveat: the
gate layer *does* widen it, by a different mechanism than the classifier.

**Section-B additions** (MIDs subscribed 2026-07-16, turned into detections in
Sprint 26 — the technique's footprint lives in a *recorded* MID that nothing read
until now):

| SPARTA | Technique | Caught by |
|---|---|---|
| EX-0010.01 | Ransomware (mass file encryption) | rule-gate R11 (FM command) → EX-0010 incident |
| EX-0010.02 | Wiper (mass file destruction) | rule-gate R11 (FM command) → EX-0010 incident |
| EXF-0003.02 | Downlink exfiltration | rule-gate R12 (TO command) + R13 (route-mask change) → EXF-0003.02 incident |
| DE-0001 | Disable fault management | rule-gate R5 (LC state → DISABLED) — shared LC-disable footprint with EX-0011/DE-0005 |
| DE-0006 | Modify whitelist | rule-gate R8 (CFE_ES cmd) + R9 (CFE_TBL cmd) — presents as command activity |

R11 keys on `FM.CommandCounter` (static-in-nominal, validated live 0/1). The two
sub-techniques are telemetry-indistinguishable at the HK level (both a File Manager
file-op burst), so R11 catches the class as one `EX-0010` incident; the command mix
disambiguates wiper vs ransomware. Deliberately does **not** key on
`DS.Payload.FileWriteCounter` — that counter climbs continuously in nominal ops (DS
logging), so it would false-positive.

R12/R13 required a subscription fix: OnAIR was originally mis-subscribed to the idle
`to_lab` HK (`0x08E8`, command-counter only). Re-pointed to the **full `to` app** HK
(`0x0880`), which COSMOS actually reads and which carries the downlink route masks
`usEnabledRoutes`/`usConfigRoutes`. R12 keys on `TO.usCmdCnt` (static-in-nominal, an
R6–R11 sibling); R13 fires when the route mask leaves its baseline (the specific
"downlink reconfigured" signal). A `TO_ENABLE_OUTPUT` redirect to an attacker trips
both. R13 also **sharpens IMP-0006 (theft)** — a downlink redirect is the on-board
footprint of telemetry theft, previously only inferred via side effects. (The re-point
also put the full **CI** app HK `0x0884` on the pipe — real command-ingest observability,
deferred to a follow-up.)

DE-0001 needed no new rule: its on-board footprint is `LC.CurrentLCState` leaving the
protective ACTIVE(1) baseline for DISABLED(3), the same signal EX-0011/DE-0005 produce
— telemetry-indistinguishable at LC (all drive the state to 3), so R5 catches the shared
fault-management-disable class (incident cluster EX-0011, the family representative).
DE-0006 (modify whitelist) likewise needed no new rule: its simulatable footprint is
CFE_ES + CFE_TBL command activity, caught by R8+R9; the NOOP-only script activates no
table, so the CFE_TBL table-activity fields stay constant (the AINOS3-30 DEAD-class
reopen trigger is **not** tripped).

Two watchdog techniques (EX-0012.11 modify-WDT, DE-0003.11 WDT-for-evasion) and one
replay technique (EX-0001.02 bus-traffic replay) were resolved **out-of-scope** this
sprint after a structural footprint check: NOS3's pc-linux PSP watchdog is a no-op stub
(no MID, no HS app; LC's "WDT" is the Watchpoint Definition Table, not a timer), and the
internal SBN bus has no external injection path. EX-0005.01 (firmware design flaws) is
**not-applicable** — NOS3 models functional behaviour, not the firmware/FPGA layer the
technique targets. This closed the last of the not-evaluated leaves: the per-leaf SPARTA
split is now **42 detected · 26 out-of-scope · 0 not-evaluated · 109 not-applicable = 177**.

---

## What it does NOT catch (the honest limits)

### A. Detection is structurally tied to SUNSAFE mode

The other modes carry little attack signal in the current corpus. **Operational
alerts should be expected almost exclusively while the FSW is in SUNSAFE.** In
BDOT/PASSIVE/INERTIAL an attack may execute with little or no Stage-1 alarm.
This is the single most important operational caveat.

### B. Two kinds of "unlabelable" attacks — and they are different

The classifier has a set of DEAD techniques (F1 ≈ 0). Investigating *where*
their telemetry actually goes reveals **two distinct failure modes** that
matter differently:

1. **Sibling-ambiguous — telemetry-identical to another technique.** These
   are not really failures: two or more SPARTA sub-techniques produce the
   *same* on-board footprint, so asking the model to split them is asking the
   impossible. Derived empirically from the confusion matrix (two classes are
   clustered only when each one's frames land on the *other* — genuine mutual
   indistinguishability, not a rare class dumping one-way onto a reliable one):
   - `EX-0012.03` ≡ `EX-0012.04` ≡ `EX-0012.05` — propulsion / app-table /
     scheduler command family
   - `EX-0012.12` ≡ `EX-0014.01` — system-clock vs time-spoof

   **Fix (no model change):** report the *cluster* ("propulsion-command-class
   attack") instead of the exact sub-technique. Re-scoring the same model at
   this granularity lifts top-1 accuracy **0.627 → 0.660 (+3.3 pts)** and
   class-balanced macro-F1 **0.301 → 0.339**, with no retraining. The lift is
   modest because only two small command-injection families are genuinely
   indistinguishable — so the real value is **correct expectation-setting**
   (don't promise ".03 vs .04" resolution that the telemetry can't support),
   not a large metric bump.

   ⚠ **The deployed hybrid made this cluster worse, and that is now diagnosed
   (AINOS3-78, 2026-08-19).** The AINOS3-37 per-mode hybrid nets +1.0 pt overall
   but *loses* 6.0 pts on this cluster (45.5 % → 39.5 % frame-level). The loss is
   **entirely INERTIAL** (44.0 % → 23.1 %, −20.9); SUNSAFE is flat and the two
   globally-routed modes are unchanged by construction. It is **not** row
   starvation — INERTIAL holds 5,564 cluster rows, more than SUNSAFE. The cause
   is loss of **cross-mode transfer**: a cluster this telemetry-ambiguous leans on
   pooled signal, and specialising to one mode removes what was carrying it (same
   mechanism AINOS3-33 found for PASSIVE). Routing **SUNSAFE only** recovers
   essentially the whole cluster loss for −0.23 pts overall — recommended, **not
   deployed**, and gated on reconciling the frame-level vs LOIO metrics first.
   **Detection is unaffected** — this is the naming half only.
2. **Nominal-ambiguous — no distinct on-board signal at all.** Techniques like
   `DE-0003.03/.08/.09`, `EX-0014.03`, `EX-0012.08` produce telemetry that
   looks like *nominal* flight. Clustering cannot help these — only better
   detection or subscribing to additional telemetry (MIDs deliberately pruned
   from the current feature set) would. These are genuine coverage gaps.

### C. Some attacks are structurally unobservable

By design, the monitor only sees the MIDs in `nos3_security_tlm.json`. A
4-class signal taxonomy describes what is and isn't observable:

| Signal class | Meaning | Examples |
|---|---|---|
| **ON_BOARD** | Visible — at least one watched field changes | IMP-0002/3/5, DE-0003.06/09/10 |
| **OBFUSCATION** | Real, but the attack hides itself (e.g. RESET zeroes the counter before the next HK packet); only an EVS event trail survives | IMP-0001, DE-0003.01/02/08 |
| **UNSUBSCRIBED** | Target subsystem's housekeeping is **not** monitored — on-board acknowledgement is structurally invisible | IMP-0006, DE-0003.03/11 |
| **CONCEPTUAL** | No-op / description-only technique — nothing to detect | DE-0003.04/05/07/12 |

UNSUBSCRIBED and CONCEPTUAL attacks are **out of scope** for telemetry-based
detection by construction, not by failure.

### D. Incident aggregation — built; label accuracy now measured out-of-fold

The monitor aggregates flagged frames into **incidents** (Section 3) — start,
duration, cluster, accumulated confidence — using the same hysteresis the IF
plugin uses for alerts. This lifted effective detection from ~61 % (frame) to
~93 % (incident).

Incident **detection** is IF-gate-driven. ⚠ **Corrected 2026-08-11 (AINOS3-80 F1):** this
section previously claimed the IF threshold is "calibrated on held-out nominal". **It is
not** — the calibration row counts are identical to the model's training row counts in all
four modes, so the threshold is the 1 % quantile of the model's *own training scores*
`[in-sample]`, and the reported `actual_fp_rate ≈ 1.00 %` is true by construction rather
than measured. The operational claim nonetheless stands: the false-alarm rates quoted in
Section 1 come from independent soaks 4–16× larger than the training sets and land at
**0.0–0.2 %**, *below* the 1 % target — i.e. the in-sample threshold generalised
conservatively. Treat "1 % FP" as a `[design-target]` and the soak numbers as the
measurement. Incident **labelling** had only ever been measured in-sample. Re-scoring the same `csv_corpus_v3stage` corpus with
leave-one-instance-out, out-of-fold predictions (AINOS3-34) gives the honest
figure. For the **deployed selective per-mode hybrid** (AINOS3-37): **42.3 % label
accuracy of detected attacks** out-of-fold — up **+7.7 pts** from the v3 global
head's 34.6 % OOF on identical folds, concentrated in the dynamic-mode / ROBUST-tier
techniques the per-mode heads target (DE-0003.10, IMP-0002, IMP-0006, EX-0014.01,
EX-0012.07 up; the telemetry-indistinguishable `EX-0012.{03,04,05}` cluster down a
little). **The coverage overlay now reports these honest OOF numbers.** ⚠ Note the
scale: the overlay previously showed **76.9 %**, which was *in-sample* and >2×
optimistic — the honest OOF hybrid figure (42.3 %) is a truer picture *and* better
than the honest v3 (34.6 %), even though the displayed number went down when the
methodology was corrected. Incident detection recall is identical either way
(78/115), exactly as expected: only the label source changed, not the IF gate.

The label collapse is tier- and mode-dependent (the per-cluster figures below are
the v3 global-head OOF breakdown that motivated the hybrid; the **current
per-technique `label_ok` under the deployed hybrid is in the coverage overlay** —
e.g. the hybrid lifts IMP-0002 and IMP-0006 to fully labelled):

- **By tier** (coherent with §4): ROBUST clusters keep their labels out-of-fold
  (`EX-0008.02` 100 %, `IMP-0005` 100 %, the `IMP-0001/2/3/6` family ~67 %);
  HIGH-VARIANCE and DEAD clusters collapse (`EX-0012.08/.09`, `EX-0014.03/.04`
  → 0 %). The aggregate is dragged down by the many always-*detected*-but-not-
  *labelable* HIGH-VAR attacks.
- **By mode** — two views that must not be confused:
  - *Incident-level* (attack attributed to its **first** corruption-frame's
    mode): PASSIVE 48 % (26/54), INERTIAL 4 % (1/23), no SUNSAFE attacks. This
    view is **misleading**: the corpus uses `scenario_all_modes_dwell`, so one
    attack's window spans every mode and is attributed to wherever it *started*
    (mostly PASSIVE, where the FSW boots/locks), and incident voting then
    recovers the label from the *good* frames in other modes.
  - *Frame-level* (each frame's actual mode — the operationally real "attacked
    while persistently in mode X" question): **PASSIVE 0.148 cluster-acc is the
    WORST**, vs INERTIAL 0.341, SUNSAFE 0.395, BDOT 0.419. This **confirms** the
    original AINOS3-33 premise (PASSIVE is the weak mode). It is **intrinsic, not
    compositional**: the same cluster labels worse in PASSIVE (e.g.
    `EX-0012.{03,04,05}` 0.29 PASSIVE vs 0.44/0.50/0.52 elsewhere) — a single
    global classifier underfits PASSIVE's quiescent telemetry regime.

**AINOS3-33 (closed — negative result):** all three mode-aware approaches were
evaluated by LOIO over the frozen corpus and **none** raise PASSIVE label
accuracy (PASSIVE cluster-acc: baseline 0.148 → mode-feature 0.146, per-mode
heads 0.120, mode-rebalanced 0.150). A PASSIVE-only specialist scoring *below*
the global model shows the global 0.148 is propped up by cross-mode transfer:
PASSIVE labeling is an **information limit, not a modeling one**, so no
mode-aware architecture on the current 894 features closes it. The real fix must
add *signal* (extra discriminating MIDs — AINOS3-30 — or temporal features), not
rearrange the model. Per-mode heads *do* help the higher-signal modes
(INERTIAL +0.06, SUNSAFE +0.06, ROBUST +0.10, overall +0.02); that upside is
now **banked and deployed** — the **AINOS3-37 selective per-mode hybrid** routes
INERTIAL/SUNSAFE to per-mode heads and keeps the global head for PASSIVE/BDOT
(baseline-identical, so no regression), live since 2026-07-30. PASSIVE remains an
information limit the hybrid does not (and cannot) close.

Bottom line: today, trust an incident's *existence* far more than its *label*,
and treat **PASSIVE labels as low-confidence regardless of model**. (Source: the
deployed overlay's `data/onair/models/cluster_rescore/incident_rescore.json` is now
the hybrid OOF rescore; hybrid out-of-fold predictions in
`cluster_rescore/loio_predictions_oof_v3hybrid.npz` — produced by
`training/export_hybrid_oof.py`, rescored via `eval_incident_rescore.py
--oof-predictions`; the v3 global-head OOF baseline is in
`loio_predictions_oof_v3stage.npz`; mode-aware sweep in `data/onair/models/mode_aware/`.)

### E. Stage 2 sharpens, it does not widen

The classifier runs **only** on frames Stage 1 already flagged (it skips ~89 %
of frames this way). It therefore **cannot** detect an attack the anomaly
detector missed. The detection net is Stage 1; Stage 2 only attaches a label.

### F. Blind window after every ADCS mode switch (AINOS3-35)

The detector suppresses alerts for **~124 s (600 frames) after each mode
switch**, to ride out the switch transient. So **detection is reliable only in a
mode held longer than ~124 s** — an attack confined to a briefly-held mode may
raise no alert. Measured over a 36-switch nominal soak, the transient itself
settles in **~36 s (~175 frames)**, so most of that blind window is avoidable;
reducing the warmup to **~250 frames (~52 s)** cuts the blind window by ~58 %
with margin over the transient.

**Closed for the mode-force case by R14 (AINOS3-77, 2026-08-11).** The worst consequence
of this window was that *forcing* a mode — the DE-0005 safe-mode-subversion step — re-arms
the warmup and so evades Stage 1 by construction. Rule-gate **R14** now flags any confirmed
`ADCS_GNC.Mode` transition and labels it DE-0005, independently of the IF.

Three things are worth recording about how it was built:

- **Not a command-counter rule.** `ADCS_HK.CommandCount` looks like an R6–R13 sibling but
  is a wrapping uint8 that increments on routine HK polling — 264,019 changes across the
  7 h soak — so it fails the static-in-nominal precondition those rules depend on.
- **Debounced, unlike R5/R13.** OnAIR's double buffer oscillates old/new for several frames
  at each switch. Replayed over the soak, naive change-detection fires **22 times for 4 real
  transitions**; requiring the new value to persist 5 frames collapses that to exactly 4.
- **0-FP evidence** `[live-soak]`: replaying the deployed rule over the full 267,260-frame
  soak yields **4 rising edges and 4 DE-0005 incidents — one per commanded transition, none
  during any mode hold.**

Live-verified 2026-08-11: a forced `SET_MODE` SUNSAFE→INERTIAL raised
`[rule_gate][ALERT] R14:adcs-mode` and one bounded incident (13 frames, `cluster=DE-0005`,
`sub=adcs-mode-force`), while the IF logged **0 anomalies and 0 alerts** across the 81
frames spanning the transition — the blind spot demonstrated and closed in the same run.
A 2-minute hold in the new mode produced no further incidents (the rule re-baselines).

---

## Coverage matrix (SPARTA techniques)

Catch rate = SUNSAFE corruption-window flag rate. Tier = classifier
reliability. Signal = observability class.

⚠ **The Catch column credits the IF with detections the rule-gate makes** — see the boxed
note in Section 2. For discrete state-change techniques the detection is real but comes from
R1/R14, not the anomaly detector. `EX-0012.09` is a confirmed gap: nothing detects it in
steady flight.

| Technique | Catch (SUNSAFE) | Classifier tier | Signal | Note |
|---|--:|---|---|---|
| EX-0008.01 ATS | 91 % | HIGH-VAR | ON_BOARD | |
| EX-0008.02 RTS | 91 % | **ROBUST** | ON_BOARD | reliably caught & labeled |
| EX-0012.03 prop cmd | < 25 % | sibling | ON_BOARD | ≡ .04/.05 cluster; ⚠ hybrid labeling regressed on this cluster, INERTIAL only (AINOS3-78) |
| EX-0012.04 app tables | 63 % | DEAD→sibling | ON_BOARD | ≡ .03/.05 family; ⚠ hybrid labeling regressed on this cluster, INERTIAL only (AINOS3-78) |
| EX-0012.05 scheduler | 64 % | sibling | ON_BOARD | ≡ .03/.04 family; ⚠ hybrid labeling regressed on this cluster, INERTIAL only (AINOS3-78) |
| EX-0012.07 propulsion | 100 % | HIGH-VAR | ON_BOARD | always detected |
| EX-0012.08 ADCS | 100 % | HIGH-VAR | ON_BOARD | always detected; label unstable across runs |
| EX-0012.09 EPS | ⚠ **0 %** | HIGH-VAR | ON_BOARD | **CONFIRMED GAP** — detected by nothing in steady flight (0/3 reps); the 99 % came from transient-dominated data. Ticketed AINOS3-87 |
| EX-0012.12 system clock | 57 % | sibling | ON_BOARD | ≡ EX-0014.01 |
| EX-0014.01 time spoof | 26 % | DEAD→sibling | ON_BOARD | ≡ EX-0012.12 |
| EX-0014.03 sensor spoof | 91 % | nominal-amb. | ON_BOARD | detected, not labelable |
| EX-0014.04 PNT spoof | 98 % | HIGH-VAR | ON_BOARD | |
| IMP-0001 deception | 61 % | low-stable | OBFUSCATION | counter telescoping |
| IMP-0002 disruption | 58 % | **STABLE-MID** | ON_BOARD | |
| IMP-0003 denial | 100 % | **STABLE-MID** | ON_BOARD | |
| IMP-0005 destruction | 75 % | **ROBUST** | ON_BOARD | reliably caught & labeled |
| IMP-0006 theft | 62 % | STABLE-MID | UNSUBSCRIBED | side effects + R13 route-mask change (downlink-redirect variant) |
| DE-0003.01 disable logging | < 25 % | **ROBUST** | OBFUSCATION | labelable when flagged |
| DE-0003.02 clear logs | < 25 % | low-stable | OBFUSCATION | counter telescoped |
| DE-0003.03 | < 25 % | DEAD (nominal) | UNSUBSCRIBED | out of scope |
| DE-0003.06 | < 25 % | DEAD (nominal) | ON_BOARD | one-way confusion only |
| DE-0003.08 | < 25 % | DEAD (nominal) | OBFUSCATION | telescoped |
| DE-0003.09 | < 25 % | DEAD (nominal) | ON_BOARD | NOOP-only |
| DE-0003.10 | < 25 % | **ROBUST** | ON_BOARD | labelable when flagged |

*(DE-0003.04/05/07/11/12 are CONCEPTUAL/UNSUBSCRIBED — out of scope for
telemetry detection.)*

---

## Provenance & caveats

- **Detection / FP numbers:** per-mode Isolation Forest
  `iforest_per_mode_v5_invariant_bolstered`, threshold calibrated to a 1 % FP
  `[design-target]` — **in-sample**, on the model's own training scores (AINOS3-80 **F1**);
  the quoted FP rates are `[live-soak]`, measured on independent nominal-flight side-files.
  ⚠ The model artifact records **no training-corpus identity** (AINOS3-80 **F2**) — see the
  caveat in Section 3.
- **Classification numbers:** the deployed selective per-mode hybrid
  `xgb_attack_classifier_v3_hybrid` (v3 global head + INERTIAL/SUNSAFE per-mode
  heads + per-mode isotonic calibration), leave-one-instance-out over a
  3-instance, mode-balanced corpus `[OOF]`: overall **0.645 ± 0.036** (folds 0.691 /
  0.641 / 0.604) vs the v3 global head's 0.627 baseline on identical folds
  (INERTIAL +0.058, SUNSAFE +0.061, ROBUST +0.099, BDOT/PASSIVE +0.000). The paired-fold
  deltas are valid, but note the instance-to-instance spread (±0.036) exceeds most of them
  — quote the absolute figure with its spread. Calibration validated out-of-fold
  (per-mode ECE ~10× tighter, held-out half). Live-verified on the running FSW 2026-07-30.
- **Attack realism:** all cited techniques were executed against live NOS3 FSW
  and confirmed to actually change spacecraft state; no number here derives
  from an unvalidated script.
- **Known undertraining:** the BDOT detector is trained on few samples (296
  rows). It produces no false alarms but also little attack signal — low
  operational impact, since attacks don't manifest in BDOT.

---

## One-line summary for a briefing slide

The previous version of this line was withdrawn on 2026-08-14 and is superseded. It claimed
the monitor "reliably flags real attacks (15/23 techniques ≥ 50 %, many ~100 %)" and that
coverage outside SUNSAFE "is limited by design rather than by tuning." The second is
affirmatively wrong — coverage outside SUNSAFE was limited by **how we collected data**
(83 % of the corpus sat inside the detector's own post-mode-switch blind window, and modes
hold indefinitely on a single command, so long per-mode collection was always possible).

Current, claiming only what is measured:

> *A deterministic rule layer catches **13 validated attack techniques** — device disables,
> command-counter changes, fault-management shutdown, downlink redirection, file-operation
> bursts, telemetry freezes and forced mode changes — each live-verified against the running
> flight software, independent of any model. Alongside it, an anomaly detector watches
> spacecraft dynamics: on a genuine sustained-dynamics attack it flags **~80 % of attack
> frames against ~1 % of nominal** (propulsion, three independent runs), and in steady
> cruise it raises **no false alarms at all**. When it alarms, a classifier names the
> technique correctly **~65 % of the time on a spacecraft run it has never seen**
> (0.645 ± 0.036, out-of-fold). Two known gaps: **`EX-0012.09` (EPS switch) is detected by
> nothing** in steady flight, and **INERTIAL mode carries a 33.6 % nominal false-alarm rate**
> that is under investigation.*
