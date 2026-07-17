# Coverage Validation Backlog — Section A (in-scope-now techniques)

**Epic:** `coverage-expansion` (AINOS3-41) · **Created:** 2026-07-15
**Source:** [`SPARTA_COVERAGE_TRIAGE.md`](SPARTA_COVERAGE_TRIAGE.md) Section A.

These SPARTA techniques are **in the on-board-detectable universe, produce a
footprint in an already-subscribed MID, and just need validation into the corpus**
— no new MIDs, no schema change. They are the cheapest breadth wins: validating
them roughly doubles validated coverage of the ~90-technique detectable universe.

**Count:** the triage headline estimated "~18"; the concrete, defensible
enumeration below is **13 techniques** (the estimate was loose). A few more
borderline ON_BOARD candidates (`EX-0001.02` bus replay, `DE-0006` modify-whitelist,
`EX-0005.01` design flaws) are held out pending a footprint check — add them here
only if a live run confirms a subscribed field moves.

**Common acceptance criteria** (every ticket below, per the evaluation-provenance
rule — never trust a footprint claim without a live run):

1. Attack script exists (or is created via `/sparta-attack-script`) for the exact
   SPARTA sub-technique.

2. **Footprint validated against the live FSW**: ≥1 *subscribed* telemetry field
   demonstrably moves during the corruption window (parse with `csv.DictReader`).
   Record the signal class (expected ON_BOARD).

3. Folded into the mode-balanced corpus (`run_attack_batch.py` list) — or, if the
   technique doesn't fit `all_modes_dwell` (e.g. a DoS flood), validated standalone
   with its window documented.

4. Detection tier reported (frame catch + incident recall) and added to
   `app/gen_nos3_coverage.py::ENRICH`, `V5_DETECTOR_COVERAGE.md`, and the demo.

Enter Jira keys in [`JIRA_CROSSWALK.md`](JIRA_CROSSWALK.md).

| Slug | SPARTA | Type | Pri | Script? | Observable via |
|---|---|---|---|:--:|---|
| validate-pnt-geofence | EX-0002 | Task | Med | ✅ | NOVATEL/GPS position fields |
| validate-hw-commands | EX-0005.02 | Task | Med | — | component HK command counters |
| validate-safemode-exploit | EX-0011 | Task | Med | ✅ | ✔ VALIDATED — LC state + CSS/EPS/thruster (NOT ADCS mode) |
| validate-routing-tables | EX-0012.02 | Task | High | ✅ | ✔ VALIDATED — DISABLE_ROUTE; freeze detector-blind, CFE_SB.CmdCount is the signal |
| validate-cdh-subsystem | EX-0012.10 | Task | Med | — | `CFE_ES`/`CFE_SB` counters |
| validate-flood-valid | EX-0013.01 | Task | Med | ✅ | cmd counters + `CFE_SB` errors |
| validate-flood-erroneous | EX-0013.02 | Task | Med | ✅ | `CFE_SB` error family |
| validate-bus-spoof | EX-0014.02 | Task | High | ✅ | ✔ VALIDATED — EXERCISABLE (overturns MD-only); transient, both gates miss |
| validate-inhibit-sc | DE-0002.03 | Task | Med | ✅ | ✔ VALIDATED — EVS event-stream freeze; staleness-caught (+ fixed uint16-wrap FP) |
| validate-safemode-evasion | DE-0005 | Task | Low | ✅ | mode change (sibling of EX-0011) |
| validate-audit-overflow | DE-0010 | Task | High | ✅ | EVS `AppData[*].AppMessageSquelchedCounter` |
| validate-memory-compromise | PER-0001 | Task | Med | ✅ | sibling of EX-0012.03 memory write |
| validate-bus-segregation | LM-0002 | Task | Med | ✅ | `CFE_SB_SUBS` — traffic to unexpected apps |

---

### validate-pnt-geofence — Validate EX-0002 (PNT Geofencing) · `Task` · Medium · ◑ FOOTPRINT-VALIDATED 2026-07-16

**Summary:** As a defender, I want EX-0002 (PNT geofencing manipulation) validated
into the corpus so the detector is scored against it.
**Description:** Attack disables the GPS receiver (NOVATEL) to cut PNT data (level
2) and shifts CFE_TIME STCF (level 3), forcing ADCS onto stale nav.
**VALIDATED live (2026-07-16, `ex_0002_pnt_geofencing.py --attack-level 2`):**

- **Signal class: ON_BOARD, clean.** `NOVATEL_HK.DeviceEnabled: 1→0` (GPS disabled)
  — an unambiguous discrete flag, in subscribed telemetry (221 frames). The
  position/attitude drift is mostly natural orbital dynamics over the window; the
  flag is the smoking gun. GPS re-enabled afterward (cleanup).

- **Deployed IF MISSES it:** is_anomaly=0 / alert=0 across all GPS-disabled frames
  (score ~0.12, MODE_SUNSAFE). In SUNSAFE the ADCS uses sun/mag not GPS, so
  disabling GPS barely perturbs the *attitude dynamics* the IF watches — the flag
  flip itself isn't a feature the IF weights.

**AC:** footprint ON_BOARD ✓. Detection needs a rule on `NOVATEL_HK.DeviceEnabled`
(or re-test in an INERTIAL/nav-dependent mode where stale GPS actually perturbs
dynamics). See the campaign-findings note below.

---

## Campaign findings (running) — the IF is a *dynamics* detector, not a *state* detector

**Tally (2026-07-16): 4 Section-A techniques validated — DE-0010, EX-0002,
EX-0014.03, EX-0011 — all ON_BOARD; the dynamics-vs-state split is now sharp.**
The first three are pure flag/counter footprints the v5 per-mode IF MISSES
(is_anomaly=0); the rule-gate covers them. **EX-0011 is the confirming
counterexample: the IF CATCHES it (52% of window)** because its exploit fires the
thruster + toggles EPS/CSS and thus perturbs the GNC *attitude dynamics* the IF is
trained on — exactly like the already-caught EX-0012.07/08/09 corruption attacks
(ROBUST tier). So the rule "IF sees dynamics perturbation, is blind to pure
state/counter changes" holds across all validated cases. (The rule-gate ALSO
caught EX-0011 via CSS-disable + EVS cmd-errors, so it's double-covered.)

**5th (2026-07-16): EX-0014.02 bus-spoof — a THIRD detector-gap class.** Not a
flag/counter state-change and not a dynamics attack: a spoofed telemetry packet
injected onto the SB via CI_LAB (:5012). Overturned its MARKDOWN-ONLY triage
(injection demonstrably works). Its footprint is a **transient out-of-distribution
value flicker** that BOTH gates miss — the IF is counter/value-blind unless the
spoof perturbs fused dynamics, and the rule-gate's leaky integrator can't latch a
1-2 frame flicker. Catching it needs a new detector primitive: **per-sample
range/schema/monotonicity consistency** (counter went backwards, value out of
physical bounds), orthogonal to both the dynamics-IF and the sustained-signal
rule-gate. **BUILT + DEPLOYED 2026-07-16** (consistency_check plugin, fsw b58a2b4).
The detector roadmap now has THREE deployed complementary gates: dynamics-IF
(physics), rule-gate (sustained state/counter, incl. R5 monitor-state), and
consistency-check (per-sample counter-monotonicity, 0 FP / 810 live frames).

**6th (2026-07-16): EX-0012.02 routing-table modification — a FOURTH detector-gap
class (staleness).** CFE_SB DISABLE_ROUTE severs a MsgId→pipe route; disabling the
SBN route FREEZES that MID in OnAIR (telemetry denial). A frozen stream has no
delta, so all three delta-based gates miss it (same as EX-0014.03 frozen fields).
Two complementary fixes, BOTH BUILT: a per-MID STALENESS detector (MID hasn't
updated in N frames) for the freeze, and a CFE_SB.CommandCounter rule (rule-gate R6)
for the route COMMAND itself (SB route/subscription commands are rare in nominal
ops). Also corrected the triage: CFE_SB_SUBS is NOT OnAIR-observable ([0]).

**7th (2026-07-17): DE-0002.03 inhibit-spacecraft — same freeze class, and the
staleness gate's first real-attack catch.** EVS event suppression (CFE_EVS
DISABLE_EVENT_TYPE all types) FROZE `CFE_EVS_HK.MessageSendCounter` for 70s → the
**staleness gate caught it** (true positive) — the inverse of DE-0010's EVS flood.
Two lessons: (a) DE-0002.03 (EVS suppress) and EX-0012.02 (route disable) share the
SAME frozen-counter footprint, so the staleness gate detects both but labels both
EX-0012.02 — **R7, a CFE_EVS-command rule, is now BUILT** (rule_gate b586b7a; sibling
of R6) and catches/labels it DE-0002.03 at the command (~1 frame, live-verified); (b)
it exposed a staleness **uint16-wrap FP** (DS.FileWriteCounter wraps 65535→0, pinning
the running max) — fixed (fsw b9b37cb): a >50%-relative backwards drop is a wrap/reset,
re-baseline the max. Re-validated over 194K frames, 0 FP + TP preserved.

**⚠ Degraded-test-stack finding (2026-07-17): R2:evs FP-blocks incidents after long
uptime.** The R7 live run found the EVS rate at **~61/frame (max 228)** — far above
R2's threshold (15) — because the disconnected-downlink RADIO device-HK spam
("GENERIC_RADIO … error -1") accumulates over long uptime. So R2:evs fires
continuously → since R2 drives incidents, EVERY rule-gate incident stays open (never
closes → no incident file) in this state. This is a STACK-DEGRADATION artifact (a
fresh stack has EVS rate <1/frame, as in the DE-0010 validation), not an R2/R7 design
defect — but it means: (1) validate incident *emission* on a fresh stack; (2) consider
whether R2 (like R3) needs a sustained-vs-burst guard or a higher threshold for
degraded/high-EVS environments. Recommend a `make stop` + fresh `launch-quiet` before
the next incident-level validation.

**Staleness detector — BUILT + HARDENED + DEPLOYED (2026-07-16; uint16-wrap FP fixed
2026-07-17).** `staleness_check`
plugin (4th gate; fsw e08a527, registered 0b3d688e). Key correction found during
tuning: a frozen field is NOT constant — OnAIR's double buffer makes it OSCILLATE
between its two last stale values, so the primitive is "**a wide monotonic counter's
max stops advancing**," not "value unchanged." First version was live-fragile (the
watched set flipped run-to-run because discovery used the max no-advance run, a
high-variance extreme value). **Hardened** by using the **average** advance interval
(window / advances — a stable count statistic) for both the watched-set criterion and
the per-counter threshold. Result: **8 CDH/scheduler counters always watched across 5
offline windows, 0 FP over 2200 offline + 160 live frames, detects an injected freeze
at ~53 frames; live watched set matches offline.** 7 unit tests. *Limits:*
high-latency (~30–50s, poll-rate mismatch); coverage = CDH/scheduler MIDs (sensor
DeviceHK counters publish too variably). The **R6 CFE_SB.CommandCounter rule** is
**BUILT + deployed** (rule_gate a268852) — the complementary, low-latency catch (~1
frame; live-verified 0 FP, CommandCounter static in nominal) (the route COMMAND is a clean
subscribed signal; the freeze EFFECT is intrinsically high-latency).

**Emerging hypothesis:** the v5 IF detects anomalies in the *physical/attitude
dynamics*; it is largely blind to attacks whose footprint is a **discrete flag flip
or a counter/rate spike that doesn't disturb the physics** (EVS send-rate, GPS
enable flag, likely CI/SB counters, LC/DS/FM state). Because the classifier is
IF-gated, these are undetected end-to-end despite loud, subscribed signals.

**Implication:** for this class, "validate → fold into corpus → detector catches it"
is the wrong remedy — more data won't teach a dynamics-IF to watch a flag. The cheap,
high-leverage fix is a **lightweight rule/threshold layer beside the IF** (flag
discrete state changes: `*.DeviceEnabled→0`, mode changes, EVS/SB send-rate spikes),
gating the classifier in parallel with the IF. Recommend confirming with 1-2 more
diverse techniques, then prototyping that rule layer rather than grinding all 13.

**RULE-GATE PROTOTYPE — WORKS (2026-07-16).** `training/rule_gate_prototype.py`
(offline). Rules: R1 `*.DeviceEnabled` drops below session baseline; R2
`CFE_EVS_HK.MessageSendCounter` per-frame delta > auto-threshold; R3
`CFE_SB.MsgSendErrorCounter` delta > 0; R4 `*.CommandError*` delta spike. Scored on
the 44,419-frame post-restart CSV: **all 3 IF-blind attacks caught** — DE-0010
(R2+R3), EX-0002 (R1 NOVATEL), EX-0014.03 (R1 IMU) — the exact windows the IF scored
is_anomaly=0. **Nominal FP = 0.016%** (7 flicker-edge frames). Double-buffer causes
1-frame flicker at edges → a runtime impl needs the IF plugin's hysteresis
(alert/clear counters). Next: wire it as a parallel gate OR-ed with the IF (either
gate → classify + incident), so the flag/counter class is covered end-to-end with no
retrain and no new MIDs. The IF still owns the dynamics attacks (subsystem
corruption, ROBUST tier); the two gates are complementary.

**EX-0014.03 (2026-07-16) — 3/3, AND it settles the sensor-DEVICE-MID retrain
question: NO.** In NOS3, EX-0014.03 "sensor data spoof" is only exercisable as a
sensor DISABLE (true data fabrication is out of scope). Disabling the IMU flips `IMU.DeviceEnabled 1→0`. Per the source
(`generic_imu_app.c:394`), the device read + `CFE_SB_TransmitMsg` are gated on
DeviceEnabled, so the **device packet (0x0926) STOPS** when disabled: `IMU_DEV.*`
freezes, `IMU.DeviceCount` freezes, 0 device msgs in 30s. BUT: (a)
`ADCS_DI.Payload.Imu.acc` freezes **identically** — the new DEVICE MID is
**redundant** with the already-subscribed fused view; and (b) the device packet is
**sporadic even at baseline** (frozen over short enabled windows too), so a freeze
can't reliably distinguish disabled from not-updated. The reliable, clean signal is
the flag `IMU.DeviceEnabled=0`. IF misses it (is_anomaly=0 — a frozen/constant field
isn't a delta anomaly). Verdict: the sensor-DEVICE-MID IF retrain is **not justified**
for EX-0014.03 (redundant + freeze not IF-detectable); the rule layer (flag / staleness)
covers it. (Correction: an earlier note said the device "keeps producing normal data"
— that was misread stale double-buffer values; the packet actually stops.)

### validate-hw-commands — Validate EX-0005.02 (Malicious Use of Hardware Commands) · `Task` · Medium

**Summary:** Validate direct malicious hardware/device commands into the corpus.
**Description:** Attacker issues valid-but-malicious device commands to a component
(RW/EPS/THRUSTER/torquer). Footprint expected in the target component's HK command
counters + resulting device state. No script yet — create one targeting a
subscribed actuator.
**AC:** common criteria; pick a target component whose HK is subscribed.

### validate-safemode-exploit — Validate EX-0011 (Exploit Reduced Protections in Safe-Mode) · `Task` · Medium · ✔ VALIDATED 2026-07-16

**Summary:** Validate the safe-mode exploitation technique.
**Description:** In NOS3 this is NOT an ADCS/SC mode transition (the original
footprint guess was wrong). The script simulates safe-mode by disabling
monitoring (HS/LC/EVS) then exploiting: EPS switch-off, thruster arm+fire, sensor
disable. **VALIDATED live (`ex_0011_exploit_safe_mode.py --attack-level 3`,
2026-07-16):**

- **Signal class: ON_BOARD. DETECTED BY BOTH GATES — the first Section-A
  technique the IF catches on its own.** Unlike DE-0010/EX-0002/EX-0014.03 (pure
  flag/counter, IF-blind), EX-0011's *exploit* perturbs GNC dynamics: **IF
  is_anomaly=1 on 58/112 window frames (52%)** because the thruster fires at 80%
  and EPS/CSS changes disturb the attitude physics the IF is trained on.

- **Rule-gate also catches it, 3 ways:** R1 `CSS.DeviceEnabled 1→0` (CSS disable),
  R2 EVS send-rate spike, R4 `CFE_EVS_HK` cmd-errors → labeled **cmd-errors
  incident** (frames 5116-5142, SUNSAFE). So it is covered end-to-end even if the
  dynamics IF had missed it.

- **Observable fields that moved (subscribed):** `CSS.DeviceEnabled`,
  `THRUSTER.DeviceEnabled`+`CommandCount`, `EPS.CommandCount`, `LC.CmdCount`/
  `CmdErrCount`, EVS `MessageSendCounter` + `CommandErrorCounter`. **HS is NOT
  subscribed** (`HS_*`=0 cols) so the HS monitoring-disable is not observable; LC
  **is** subscribed as `LC.CurrentLCState`.

- **2 script bugs found + FIXED (live-validated):** (a) LC `SET_LC_STATE` payload
  was `>H` (2-byte BE) — must be `<HH` (4-byte LE: `uint16 NewLCState; uint16
  Padding`); it was rejected (CmdErrCount climbed, state never changed). Corrected
  form flips `LC.CurrentLCState 1→3`. (b) EVS `DISABLE_EVENT_TYPE` sent a 1-byte
  ordinal — must be a 2-byte `{uint8 BitMask; uint8 Spare}` with bit values
  (DEBUG=0x01…CRIT=0x08); corrected form is accepted (no cmd errors).

- **New observable — `LC.CurrentLCState` (a monitoring-STATE field):** with the
  fixed command it flips 1→3 (DISABLED). The rule-gate WAS blind to it (0 non-R3
  alerts — no rule watched LC state). IF-detectability of the *pure* LC flip is
  inconclusive here (confounded by settling dynamics from the thruster cleanup),
  but structurally it's a CDH-layer state field the per-mode GNC IF under-weights
  (same family as DE-0010). **→ RESOLVED: rule-gate R5 built + deployed
  2026-07-16** (fsw commit 39969a6). R5 watches monitoring/limit-check state fields
  (default `LC.CurrentLCState`, configurable) and fires on any deviation from the
  protective session baseline; live-verified emitting a closed EX-0011 incident on
  an LC disable→restore cycle while the IF stayed blind.

**AC:** footprint ON_BOARD ✓, detected by both gates ✓, script fixed ✓. Cleanup
verified (thruster disarmed, CSS/EPS/LC/EVS restored).

### validate-routing-tables — Validate EX-0012.02 (Internal Routing Tables) · `Task` · High · ✔ VALIDATED 2026-07-16

**Summary:** Validate SB internal-routing-table modification.
**Description:** Modify the Software Bus routing tables to redirect/deny message
flow. **VALIDATED live 2026-07-16 (no script — raw UDP CFE_SB commands):**

- **Exercisable via `CFE_SB DISABLE_ROUTE` / `ENABLE_ROUTE`** (MID 0x1803, CC 5 /
  CC 4). Disables a specific `MsgId → PipeId` route so that MID stops reaching the
  pipe. **Payload gotcha:** `CFE_SB_RouteCmd_Payload_t` is MsgId(u32)+PipeId(u32)+
  Spare(u8) but STRUCT-PADDED to 12 bytes → the command is 20 bytes total (8 hdr +
  12). A 9-byte payload is rejected (CmdErrCount++, length error); pad to 12.

- **Route enumeration via `CFE_SB WRITE_ROUTING_INFO` (CC 3)** → dumps a file
  (`/cf/<name>.dat`) readable on the shared mount (like AINOS3-48). Format: 64-byte
  CFE_FS header + 52-byte `CFE_SB_RoutingFileEntry_t` (MsgId u32 @0, PipeId u32 @4,
  State @8, AppName[20] @12, PipeName[20] @32). **OnAIR receives ALL telemetry via
  the SBN pipe `SBN_2_42_Pipe` (pipeid 0x0016002c)** — the route to sever for an
  OnAIR-visible effect.

- **`CFE_SB_SUBS` (0x080D) is NOT observable — reads `[0]`, not SBN-forwarded to
  OnAIR** (same pattern as NOVATEL/CI/ST). **The triage's claimed observable is
  WRONG.**

- **Footprint (DEMONSTRATED — disabled IMU_HK 0x0925 → SBN pipe):** (a) the routing
  COMMAND moves `CFE_SB.CommandCounter` (1→2 disable, →3 enable — subscribed, live,
  the clean ON_BOARD signal; SB route commands are rare/never in nominal ops); (b)
  the routing EFFECT froze `IMU.DeviceHK.DeviceCounter` at 61731 for the whole 20s
  window (telemetry DENIAL — the MID stops reaching OnAIR while the FSW keeps
  running). Reversible; ENABLE_ROUTE restored the flow (verified IMU resumed).

- **Detection: all THREE delta-based gates are BLIND to the freeze** — a frozen
  stream has no delta (consistency-check needs a backwards step: 0 alerts; rule-gate
  needs a flag-drop/spike: 0 non-R3; IF sees constant input). Same family as
  EX-0014.03's frozen fields. Catching the FREEZE needs a **per-MID staleness
  detector** ("subscribed MID hasn't updated in N frames") — **BUILT + deployed as
  the `staleness_check` plugin** (see the campaign-findings note above). Catching the
  COMMAND is **rule-gate R6** — a **CFE_SB.CommandCounter rule** (any SB
  route/subscription command is suspicious) — **BUILT + deployed** (rule_gate
  a268852), the low-latency catch (~1 frame; live-verified, 0 FP).

**AC:** exercisability confirmed ✓; footprint ON_BOARD (CFE_SB.CommandCounter) +
telemetry-freeze; triage observable corrected; detector gap (staleness) documented.
No lasting state change (route restored).

### validate-cdh-subsystem — Validate EX-0012.10 (C&DH Subsystem) · `Task` · Medium

**Summary:** Validate on-board-value modification targeting the C&DH subsystem.
**Description:** Modify Command & Data Handling values (the cFES core apps). Sibling
of the done EX-0012.07/.08/.09 (propulsion/ADCS/EPS). Footprint in the subscribed
`CFE_ES` / `CFE_SB` / `CFE_TBL` counters. No script yet — mirror the .07/.08/.09
pattern.
**AC:** common criteria; identify the C&DH field(s) perturbed.

### validate-flood-valid — Validate EX-0013.01 (Flooding — Valid Commands) · `Task` · Medium

**Summary:** Validate a valid-command flood (DoS).
**Description:** Flood the command path with a burst of *valid* commands. Script
`ex_0013_flooding.py` exists but EX-0013 was **excluded from the mode-balanced
corpus** because a DoS flood doesn't fit the `all_modes_dwell` window. Footprint:
command counters climb fast + `CFE_SB` error/overflow family.
**AC:** common criteria; **validate standalone** (document the flood window; do not
force it through all_modes_dwell).

### validate-flood-erroneous — Validate EX-0013.02 (Flooding — Erroneous Input) · `Task` · Medium

**Summary:** Validate an erroneous-input flood.
**Description:** As EX-0013.01 but with malformed/erroneous packets — drives the
`CFE_SB` `MsgReceiveErrorCounter` / `PipeOverflowErrorCounter` family and the
sbn_adapter unknown-MsgId path. Same script family.
**AC:** common criteria; standalone window; confirm the error-counter footprint.

### validate-bus-spoof — Validate EX-0014.02 (Bus Traffic Spoofing) · `Task` · High · ✔ VALIDATED 2026-07-16 (overturns MARKDOWN-ONLY)

**Summary:** Validate Software-Bus traffic spoofing.
**Description:** Inject spoofed SB messages impersonating a legitimate app. The
`.md` had this MARKDOWN-ONLY ("internal SB injection not reachable from external
UDP"). **That is WRONG — empirically overturned 2026-07-16** (per the
no-closed-by-construction rule, verified against live FSW, no script needed —
raw UDP injection):

- **Mechanism (code-confirmed):** `:5012` IS CI_LAB (`CI_LAB_BASE_UDP_PORT 5012`).
  CI_LAB ingest does `CFE_SB_TransmitBuffer(NextIngestBufPtr, false)`
  (`ci_lab_app.c:348`) — it republishes ANY received packet onto the SB **by its
  MID, with no command/telemetry filter**. So an external attacker can place a
  spoofed *telemetry* MID onto the internal SB, not just commands.

- **DEMONSTRATED:** injected a hand-crafted 29-byte `GENERIC_IMU_Hk_tlm_t`
  (MID 0x0925) with `CommandErrorCount=222` (a value that never occurs naturally).
  **OnAIR — a SB subscriber via SBN — observed `IMU.CommandErrorCount=222`** (2/80
  frames single-shot). Signal class: **ON_BOARD (spoof reaches the bus + a
  subscriber).**

- **Caveat 1 — SBN forwarding:** OnAIR only sees the MIDs SBN forwards to it.
  NOVATEL_HK/CI/ST read `[0]` (never forwarded) so a first spoof attempt on
  NOVATEL_HK (0x0870) was invisible at OnAIR — not because injection failed but
  because OnAIR is blind to that MID. (Also corrects the old DE-0010 note: "CI
  IngestPackets didn't move" was the `[0]` sentinel, i.e. CI HK not forwarded —
  NOT commands bypassing CI_LAB.) The spoof still lands on the FSW SB where
  consuming *apps* would act on it.

- **Caveat 2 — transient:** for a continuously-published MID the real publisher
  overwrites the spoof. Even a sustained 32 pkt/s flood (256 pkts/8s) held the
  observed value only ~1/40 frames — the real IMU + SBN/OnAIR sampling dominates.
  So the observed footprint is a brief FLICKER, not a durable value.

- **DETECTION GAP (both gates miss it):** the IF is counter-blind (a spoofed
  counter doesn't perturb dynamics); the rule-gate's leaky integrator can't LATCH
  a 1-2 frame flicker (R4 never reached AlertLevel). A brief/flickering spoof
  evades sustained-signal hysteresis. Detecting bus-spoofing needs a **per-sample
  out-of-range / schema-consistency check** (e.g. counter went backwards, value
  out of physical range), not an integrator — a distinct detector class from both
  the dynamics-IF and the rule-gate. A spoof of a *dynamics-relevant* value that
  the ADCS fuses (vs a counter) could still perturb the physics → IF-catchable.

**AC:** exercisability confirmed (overturns triage) ✓; footprint = transient
subscribed-telemetry flicker; detection gap documented. No FSW state changed
(telemetry spoof, not commands) — nothing to clean up.
**→ RESOLVED: consistency_check plugin built + deployed 2026-07-16** (fsw commit
b58a2b4, parent 5eb0cf2c). A third OnAIR gate, parallel to the IF and rule-gate,
that catches the per-sample spoof the other two miss. Primitive: a watched WIDE
monotonic counter dropping below its recent rolling-window floor to a mid value
(window-min beats OnAIR's double-buffer flicker; name+uint8 filters beat wraps and
physical fields). **0 FP over 810 live nominal frames; a spoofed
`IMU.DeviceHK.DeviceCounter=100` (real ~56900) produced one EX-0014.02 incident
while the rule-gate stayed silent.** Coverage caveat: catches spoofs that move a
wide (uint32, non-wrapping) counter backwards; uint8 sensor-count spoofs are
excluded (wrap-noisy). **Follow-up:** update demo/triage to reclassify EX-0014.02
from MARKDOWN-ONLY to exercisable-and-now-detected.

### validate-inhibit-sc — Validate DE-0002.03 (Inhibit Spacecraft Functionality) · `Task` · Medium · ✔ VALIDATED 2026-07-17

**Summary:** Validate disabling/inhibiting a spacecraft subsystem as evasion.
**Description:** Suppress telemetry at the source. The shipped script is a STUB
(only sends CFE_EVS NOOPs — doesn't execute the inhibit); validated directly via raw
commands. The OnAIR-observable mechanism is **CFE_EVS DISABLE_EVENT_TYPE** (0x1801
FC3, 2-byte {BitMask,Spare}) — disabling all 4 event types (bitmask 0x0F) stops the
event stream. (Inverse of DE-0010's EVS flood.)
**VALIDATED live 2026-07-17:**

- **Signal class: ON_BOARD, staleness-detected.** `CFE_EVS_HK.MessageSendCounter`
  **FROZE at 17102 for the full 70s** the event types were disabled (resumed to
  17312 on ENABLE_EVENT_TYPE). The **staleness gate fired** on it
  (`MessageSendCounter` max not advanced ≥78 frames → EX-0012.02/…-stale incident).
  So DE-0002.03's freeze footprint is caught by the staleness gate.

- **Note — shared freeze signature:** the staleness gate labels this EX-0012.02 (its
  hardcoded freeze cluster), same as a route-disable — DE-0002.03 (EVS suppression)
  and EX-0012.02 (route disable) produce the SAME frozen-counter footprint; the
  distinguishing signal is the COMMAND (CFE_EVS DISABLE_EVENT_TYPE vs CFE_SB
  DISABLE_ROUTE). R6 catches the CFE_SB command; **R7 — a CFE_EVS-command rule — is
  now BUILT** (rule_gate b586b7a): CFE_EVS_HK.CommandCounter is static in nominal
  (verified 1 value / 4530 frames), so a new high labels this DE-0002.03/evs-command
  at ~1 frame. Live-verified firing (a CFE_EVS NOOP → R7 alert) while R6 stayed
  silent. So DE-0002.03 now has two catches: staleness (freeze effect) + R7 (command).

- **Bonus — found + fixed a staleness FP:** the run exposed a persistent false stale
  on `DS.Payload.FileWriteCounter` (a uint16 counter that WRAPS 65535→0, pinning the
  running max for its next 0→65515 climb) and `SCH.ScheduleActivitySuccessCount`.
  Fixed in staleness_check (fsw b9b37cb): a large RELATIVE backwards drop (>50% of the
  running max) is a wrap/reset, not a freeze → re-baseline the max. Re-validated
  offline over **194,275 frames** (containing a real wrap): DS+SCH FP → 0, DE-0002.03
  EVS-freeze TP preserved (669 frames).

**AC:** footprint ON_BOARD (EVS event stream freeze) ✓, staleness-detected ✓; the
"goes quiet" signal confirmed on a subscribed subsystem (EVS). Cleanup: event types
re-enabled (EVS resumed).

### validate-safemode-evasion — Validate DE-0005 (Subvert Protections via Safe-Mode) · `Task` · Low

**Summary:** Validate safe-mode subversion as a defense-evasion technique.
**Description:** The defense-evasion sibling of EX-0011 — enter safe mode to relax
protections and evade. Same footprint (mode transition). Low priority: near-
duplicate of validate-safemode-exploit; validate together.
**AC:** common criteria; may share a run with EX-0011.

### validate-audit-overflow — Validate DE-0010 (Overflow Audit Log) · `Task` · High · ◑ FOOTPRINT-VALIDATED 2026-07-16

**Summary:** Validate an EVS event-log overflow used to bury evidence.
**Description:** Flood EVS with events (script sends `CFE_EVS_NOOP`, MID 0x1801)
so the audit trail is drowned. Observable in the EVS housekeeping.
**VALIDATED against live FSW (2026-07-16, `de_0010_overflow_audit_log.py`
`--attack-level 2 --flood-count 500`):**

- **Signal class: ON_BOARD, strong.** `CFE_EVS_HK.MessageSendCounter` 10564→11080
  (Δ+516) and **`AppData[CFE_EVS].AppMessageSentCounter` 2→490 (Δ+488)**, +303
  events in a single frame at peak — a huge, clean, already-subscribed signal.

- **Hypothesis CORRECTED:** the footprint is the **sent** counter, NOT
  `AppMessageSquelchedCounter`. Squelch never fired even on an instantaneous
  200-event burst (config `CFE_PLATFORM_EVS_MAX_APP_EVENT_BURST=32`,
  `APP_EVENTS_PER_SEC=15`) — the FSW's command-processing pace keeps the event
  rate under the refill. The squelch-signal claim (here + the AppData analysis +
  `V5_DETECTOR_COVERAGE.md`) is refuted for NOS3 event floods; correct to sent-rate.

- **Deployed detector MISSES it:** the v5 IF held `is_anomaly=0 / alert=0` across
  all 263 flood-burst frames (score ~0.12 vs thr ~0). The per-mode, GNC-dominated
  IF doesn't weight CDH/EVS counters; since the classifier is IF-gated, DE-0010 is
  **undetected end-to-end** despite the loud footprint.

**Re-run 2026-07-16 (post 16-MID subscription):** footprint reconfirmed (EVS sent
+379). New footprint element: **`CFE_SB.MsgSendErrorCounter` +96** (flood induces SB
send errors; already subscribed). **`CI.IngestPackets` did NOT move** — externally
injected commands hit the NOS3 UDP→SB bridge at :5012 and **bypass CI_LAB**, so
`CI_LAB_HK` is NOT a command-injection signal in NOS3 (refutes a triage assumption;
same likely applies to the EX-0013 flood tickets). No new MID adds DE-0010 signal.
**Revised AC:** footprint is confirmed ON_BOARD ✓. Folding into the corpus is
**not** guaranteed to make the IF catch it — the honest next step is (a) collect
DE-0010 + retrain and re-measure whether the IF learns the EVS-flood signature, or
more likely (b) add a targeted EVS-send-rate feature/rule, since the per-mode IF
structurally under-weights CDH-layer signal. This reframes DE-0010 from "just
validate" to "signal present but detector-blind — needs a feature, not just data."

### validate-memory-compromise — Validate PER-0001 (Memory Compromise) · `Task` · Medium

**Summary:** Validate persistent memory compromise.
**Description:** Persistent on-board memory modification (persistence tactic).
Mechanically similar to EX-0012.03 (memory write/load); the distinction is
persistence across a reset. Footprint via the same `CFE_TBL`/`CFE_ES` surfaces plus
survival across a Tier-1.5 reset. Script exists at technique level.
**AC:** common criteria; additionally show the change *persists* across a reset.

### validate-bus-segregation — Validate LM-0002 (Exploit Lack of Bus Segregation) · `Task` · Medium

**Summary:** Validate lateral movement via unsegregated Software Bus.
**Description:** Use the flat SB (no inter-app segregation) to move from one
compromised app to another — e.g. subscribe/publish across trust boundaries.
Observable via `CFE_SB_SUBS` (a subscription/route that shouldn't exist). The one
Lateral-Movement technique that IS on-board-detectable. Script exists at technique
level.
**AC:** common criteria; assert the cross-boundary subscription in `CFE_SB_SUBS`.
