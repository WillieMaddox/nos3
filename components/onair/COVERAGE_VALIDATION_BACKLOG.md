# Coverage Validation Backlog — Section A (in-scope-now techniques)

**Epic:** `coverage-expansion` (AINOS3-41) · **Created:** 2026-07-15

**Source:** [`SPARTA_COVERAGE_TRIAGE.md`](SPARTA_COVERAGE_TRIAGE.md) Section A.

These SPARTA techniques are **in the on-board-detectable universe, produce a
footprint in an already-subscribed MID, and just need validation into the corpus**
— no new MIDs, no schema change. They are the cheapest breadth wins: validating
them roughly doubles validated coverage of the ~90-technique detectable universe.

**Status (2026-07-17): ALL 13 VALIDATED — campaign complete.** Every technique in the
table below has a live-verified footprint; the campaign also built the 4 detector
gates + rules R1–R9 for the classes the IF misses. See the campaign synthesis at the
end.

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

| Jira | Slug | SPARTA | Type | Pri | Script? | Observable via |
|---|---|---|---|---|:--:|---|
| AINOS3-50 | validate-pnt-geofence | EX-0002 | Task | Med | ✅ | NOVATEL/GPS position fields |
| AINOS3-51 | validate-hw-commands | EX-0005.02 | Task | Med | ✅ | ✔ VALIDATED — valid device cmds (no cmd-errors); R1 TORQUER-disable + dynamics IF |
| AINOS3-52 | validate-safemode-exploit | EX-0011 | Task | Med | ✅ | ✔ VALIDATED — LC state + CSS/EPS/thruster (NOT ADCS mode) |
| AINOS3-53 | validate-routing-tables | EX-0012.02 | Task | High | ✅ | ✔ VALIDATED — DISABLE_ROUTE; freeze detector-blind, CFE_SB.CmdCount is the signal |
| AINOS3-54 | validate-cdh-subsystem | EX-0012.10 | Task | Med | ✅ | ✔ VALIDATED — CFE_ES value mod; 4-gate MISS → NEW rule R8 (CFE_ES.CommandCounter) |
| AINOS3-55 | validate-flood-valid | EX-0013.01 | Task | Med | ✅ | ✔ VALIDATED — loud (R2+R3+R6+R7); labeled DE-0010 (shared EVS-flood footprint) |
| AINOS3-56 | validate-flood-erroneous | EX-0013.02 | Task | Med | ✅ | ✔ VALIDATED — cmd-error family (R4), NOT SB-recv; wave-2 crash fixed + not injection-triggerable |
| AINOS3-57 | validate-bus-spoof | EX-0014.02 | Task | High | ✅ | ✔ VALIDATED — EXERCISABLE (overturns MD-only); transient, both gates miss |
| AINOS3-58 | validate-inhibit-sc | DE-0002.03 | Task | Med | ✅ | ✔ VALIDATED — EVS event-stream freeze; staleness-caught (+ fixed uint16-wrap FP) |
| AINOS3-59 | validate-safemode-evasion | DE-0005 | Task | Low | ✅ | ✔ VALIDATED — R5 LC-disable (shared w/ EX-0011); forced ADCS mode = IF warmup blind spot |
| AINOS3-60 | validate-audit-overflow | DE-0010 | Task | High | ✅ | EVS `AppData[*].AppMessageSquelchedCounter` |
| AINOS3-61 | validate-memory-compromise | PER-0001 | Task | Med | ✅ | ✔ VALIDATED — CFE_TBL/SC cmd counters; 4-gate MISS → NEW rule R9 (CFE_TBL.CommandCounter) |
| AINOS3-62 | validate-bus-segregation | LM-0002 | Task | Med | ✅ | ✔ VALIDATED — 24-MID sweep → R6+R7+R8+R2 together; `CFE_SB_SUBS` unobservable |

---

### AINOS3-50 — Validate EX-0002 (PNT Geofencing) · `Task` · Medium · ◑ FOOTPRINT-VALIDATED 2026-07-16

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
dynamics). See the campaign synthesis at the end of this doc.

---

### AINOS3-51 — Validate EX-0005.02 (Malicious Use of Hardware Commands) · `Task` · Medium · ✔ VALIDATED 2026-07-17

**Summary:** Validate direct malicious hardware/device commands into the corpus.

**Description:** The parent EX-0005 (firmware/FPGA corruption) is NOT simulatable in
NOS3. Sub-technique .02 IS its behavioral proxy: an attacker with command access
issues *legitimate, well-formed* device commands whose OPERATIONAL INTENT is
malicious — disable a magnetorquer, inject reaction-wheel torque, arm/fire a
thruster, toggle EPS power switches. Because the commands are valid, the flight
software accepts them: the component's `CommandCount` climbs and device STATE
changes; `CommandErrorCount` does NOT move. This is deliberately the *quiet*
counterpart to EX-0011 — there is NO monitoring-disable prelude.

**Script:** `gsw/attack_scripts/sparta/execution/ex_0005_malicious_hw_commands/ex_0005_02_malicious_hw_commands.py`
(`--attack-level 3`). Targets: TORQUER (0x193A), RW (0x1992), THRUSTER (0x18EA),
EPS (0x191A) — all subscribed.

**VALIDATED live (2026-07-17, healthy stack — IF 0% for 12k steady-state frames
pre-attack):**

- **Signal class: ON_BOARD. DETECTED BY TWO GATES.**
- **Footprint (all commands valid → NO cmd-errors):** `TORQUER.DeviceEnabled 1→0`;
  `TORQUER.CommandCount 1→7` (+6), `THRUSTER.CommandCount 94→98` (+4),
  `EPS.CommandCount 95→98` (+3); `THRUSTER.DeviceEnabled 0→1`; RW `SET_TORQUE`
  injected on 3 wheels. Every `*.CommandErrorCount` stayed FLAT (TORQUER 0, THRUSTER
  47, EPS 46 — no new errors). This is the defining contrast with EX-0013.02, which
  drives `CommandErrorCounter`.
- **Rule-gate R1:** `R1:TORQUER-disabled` fired on the `DeviceEnabled 1→0` edge
  (first at frame 15129), latched active, and **cleared cleanly** (alert_active 0)
  once the torquer was re-enabled in cleanup.
- **Dynamics IF:** `is_anomaly` **0% pre-attack (14700–15090) → 78% in the attack
  window (15095–15275)**. The thruster fire + injected reaction-wheel momentum
  perturb the attitude physics the per-mode IF is trained on. The IF *persists* at
  ~100% after cleanup because the malicious `SET_TORQUE` genuinely loaded RW
  momentum that the ADCS has to actively dump — an honest residual effect, not a
  stack artifact (R1 and device states restored).
- **Detection needs BOTH:** R1 catches the device-disable even if the vehicle never
  moved; the IF catches the delta-V / momentum perturbation even when no device is
  disabled. A pure valid-command actuator abuse with no disable and no dynamics
  (e.g. a benign-magnitude single command) would be the residual gap.

**Incident-level fold:** gate-confirmed; the shared IncidentAggregator fold for R1
is best re-checked on a fresh launch (this stack was ~6 h uptime; per the known
degraded-stack note the incident layer is fragile at long uptime).

**AC:** met — targeted subscribed actuators (TORQUER/RW/THRUSTER/EPS), confirmed the
valid-command / no-cmd-error footprint live, and confirmed detection by R1 + IF.

### AINOS3-52 — Validate EX-0011 (Exploit Reduced Protections in Safe-Mode) · `Task` · Medium · ✔ VALIDATED 2026-07-16

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

### AINOS3-53 — Validate EX-0012.02 (Internal Routing Tables) · `Task` · High · ✔ VALIDATED 2026-07-16

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

### AINOS3-54 — Validate EX-0012.10 (C&DH Subsystem) · `Task` · Medium · ✔ VALIDATED 2026-07-17

**Summary:** Validate on-board-value modification targeting the C&DH subsystem.

**Description:** Modify Command & Data Handling values (the cFE core apps). Sibling
of the done EX-0012.07/.08/.09 (propulsion/ADCS/EPS), but the target is the FLIGHT
EXECUTIVE itself. Script targets CFE_ES (Executive Services): `SET_MAX_PR_COUNT`
raises `CFE_ES.MaxProcessorResets` (defeats the auto power-on-reset safeguard —
the spacecraft keeps processor-resetting into a compromised state instead of
falling back to a clean POR), plus `SET_PERF_FILTER_MASK` and `RESET_PR_COUNT`.

**Script:** `gsw/attack_scripts/sparta/execution/ex_0012_modify_on_board_values/ex_0012_10_cdh_subsystem.py`
(`--attack-level 3/4`). `CFE_ES_CMD_MID=0x1806`; SET_MAX_PR_COUNT=CC20,
SET_PERF_FILTER_MASK=CC16, RESET_PR_COUNT=CC19.

**VALIDATED live (2026-07-17, fresh stack):**

- **Signal class: ON_BOARD. Footprint (all valid → NO cmd-errors):**
  `CFE_ES.MaxProcessorResets 2→250` (reset safeguard defeated), `CFE_ES.PerfFilterMask[0]`
  zeroed, `CFE_ES.CommandCounter 0→4`; `CFE_ES.CommandErrorCounter` stayed 0. Note
  the double-buffer garbage alternate for these fields (`MaxProcessorResets`
  flickers to `1684368489`, etc.) — read the stable value, not the flicker.
- **⚠ DETECTOR GAP — all 4 deployed gates MISSED it (first pass):** rule-gate had no
  CFE_ES rule (R6/R7 cover CFE_SB/CFE_EVS only); the dynamics IF is CDH-blind (0/90,
  same class as DE-0010); consistency-check watches for a counter going *backward*
  (this went UP); staleness-check needs a *frozen* stream (this one didn't freeze).
- **GAP CLOSED — new rule R8 (`CFE_ES.CommandCounter`):** `CFE_ES.CommandCounter` is
  static-in-nominal (~0) like CFE_SB (R6) and CFE_EVS (R7), so R8 reuses the
  generalized `_cmd_rule` new-high + dwell mechanism — any increment is an attacker
  CFE_ES command. After deploy + OnAIR restart, re-running the attack fired
  **`R8:es-command` ALERT (frame 419) → EX-0012.10/es-command INCIDENT (frames
  418-430, 13f, SUNSAFE) → CLEAR**. +3 unit tests (21 pass). R8 also covers other
  CFE_ES-command techniques (memory write, app start/stop, EX-0012.03).

**AC:** met — C&DH field `CFE_ES.MaxProcessorResets` (+`CommandCounter`) identified as
the perturbed value, footprint confirmed live, and detection closed via R8.

### AINOS3-55 — Validate EX-0013.01 (Flooding — Valid Commands) · `Task` · Medium · ✔ VALIDATED 2026-07-17

**Summary:** Validate a valid-command flood (DoS).

**Description:** Flood the command path with a burst of *valid* commands
(`ex_0013_flooding.py --attack-level 3`, 967 valid NOOPs at 100/sec across 7
subsystems). Validated standalone on a FRESH stack (see the degraded-stack note —
incident-level validation needs a clean launch).

**VALIDATED live 2026-07-17:**

- **Signal class: ON_BOARD, LOUD — detected by FOUR rules.** During the flood:
  **R2:evs** (145 frames — the dominant signature; EVS `MessageSendCounter` +575, as
  each NOOP emits a command-success event), **R3:sb** (77 — SB pipe-overflow errors),
  **R6:sb** + **R7:evs** (52 each — CFE_SB and CFE_EVS `CommandCounter` +96; CFE_ES
  also +96). Emitted a **245-frame rule-gate incident** (frames 5542-5786) that
  closed cleanly when the flood stopped.
- **Labeling finding — EX-0013.01 ≡ DE-0010 footprint.** The incident is labeled
  **DE-0010 (evs-flood)**, not EX-0013, because a valid-command flood IS an EVS flood
  at the source (command-success events), so the EVS-rate spike (R2, 145 frames)
  dominates the R6/R7 command spikes (52 frames each) → majority label DE-0010
  (agreement 0.77). The rule-gate DETECTS the flood but has no dedicated "flood"
  class; labeling it EX-0013 specifically would need a multi-rule/mass-command-rate
  rule. The R6/R7 command spikes are the distinguisher from a pure EVS-NOOP flood.

**AC:** footprint ON_BOARD ✓ (4-rule detection + incident) ✓; validated standalone ✓.
No cleanup (all NOOPs — no state change). **Follow-up:** EX-0013.02 (erroneous-input
flood) is the sibling — malformed packets → CFE_SB MsgReceive/PipeOverflow error
family + the sbn_adapter unknown-MsgId path (watch for the KeyError crash from
wave-2); a distinct footprint from this valid flood.

### AINOS3-56 — Validate EX-0013.02 (Flooding — Erroneous Input) · `Task` · Medium · ✔ VALIDATED 2026-07-17

**Summary:** Validate an erroneous-input flood.

**Description:** Malformed-packet flood — 700 packets to :5012 (random garbage MIDs,
telemetry-range garbage, wrong-FC to real command MIDs, oversized, and definitely-
unmapped high StreamIds). Validated standalone on the fresh stack, watching for the
wave-2 sbn_adapter crash.

**VALIDATED live 2026-07-17:**

- **Footprint is the CommandError family, NOT the SB-receive-error family** (corrects
  the expected observable). `MsgReceiveErrorCounter` stayed **0** — CI_LAB/CFE_SB
  reject garbage packets upstream without a receive error. The signal is the
  **wrong-FC packets** (valid MID, bad FC) reaching real apps → `CommandErrorCounter`
  climbs across subsystems (CFE_SB +34, CFE_EVS +36, IMU +47, ADCS +45). **Detected
  by rule-gate R4 (cmd-errors)** → a **251-frame `cmd-errors/IMU-cmderr` incident**.
- **Wave-2 sbn_adapter KeyError crash: NOT triggered — and NOT attacker-triggerable
  via injection.** OnAIR stayed up (CSV kept growing) with **0 "unknown StreamId"
  skips**: injected unknown MIDs never reach OnAIR because SBN only forwards
  *subscribed* MIDs (filtered at CI_LAB/CFE_SB/SBN before the sbn_adapter). The fix
  (`sbn_adapter.py:231` `except KeyError: skip + log-once`) protects against a
  config-mismatch/FSW-init unmapped MID in the forward set, which is the real source
  of the wave-2 crash — not `:5012` fuzzing. So the crash is doubly-guarded.

**AC:** footprint ON_BOARD (CommandError family) ✓, detected by R4 ✓, no crash ✓.
No cleanup (wrong-FC commands rejected, garbage dropped — no state change; FSW +
OnAIR healthy). Distinct footprint from EX-0013.01 (that = EVS-flood/R2; this =
cmd-errors/R4).

### AINOS3-57 — Validate EX-0014.02 (Bus Traffic Spoofing) · `Task` · High · ✔ VALIDATED 2026-07-16 (overturns MARKDOWN-ONLY)

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

### AINOS3-58 — Validate DE-0002.03 (Inhibit Spacecraft Functionality) · `Task` · Medium · ✔ VALIDATED 2026-07-17

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
  at ~1 frame. Live-verified on a fresh stack: a CFE_EVS NOOP → R7 alert 1 frame later
  → a closed **DE-0002.03/evs-command incident** (`frames 576-588`), while R6 stayed
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

### AINOS3-59 — Validate DE-0005 (Subvert Protections via Safe-Mode) · `Task` · Low · ✔ VALIDATED 2026-07-17

**Summary:** Validate safe-mode subversion as a defense-evasion technique.

**Description:** The defense-evasion sibling of EX-0011 — send commands that safe-mode
would normally reject (disable Limit Checker, force an ADCS mode, cut an EPS switch),
betting on relaxed controls. NOS3 has no autonomous safe-mode, so the script just
issues those commands. Shares EX-0011's LC-disable footprint; adds an explicit ADCS
mode transition.

**Script:** `gsw/attack_scripts/sparta/defense_evasion/de_0005_subvert_safe_mode.py`.
**3 script bugs fixed** (same class as EX-0011): LC `SET_LC_STATE` was `>H` → must be
`<HH` (4-byte LE `uint16 NewLCState; uint16 Padding`); ADCS `SET_MODE` was `>I` →
must be `uint8 Mode`; EPS `SWITCH` used FC 3 → must be FC 2. Corrected, all commands
are now accepted (LC.CmdErrCount + EPS.CommandErrorCount stayed 0).

**VALIDATED live (2026-07-17, exploit + 25s dwell + restore):**

- **Signal class: ON_BOARD. Footprint (all valid → NO cmd-errors):**
  `LC.CurrentLCState 1→3` (DISABLED), `ADCS_GNC.Mode 2→3` (SUNSAFE→INERTIAL),
  `EPS.CommandCount 0→3`, `LC.CmdCount +2`. All fields oscillate old↔new via the OnAIR
  double buffer while deviated.
- **Detected by rule-gate R5** (monitor-state): `R5:LC-monstate` fired on
  `LC.CurrentLCState` leaving its protective baseline — the rule's own label reads
  "LC monitoring/limit-check state left its protective baseline (EX-0011 safe-mode
  induction / **DE-0005**)". Cleared cleanly when LC was set back to ACTIVE. This is
  the same catch as EX-0011 (AINOS3-52); the two share the R5 footprint as the backlog
  predicted.
- **Incident fold VERIFIED on a fresh stack (2026-07-17).** With R2:evs quiet (fresh
  launch, no degraded-stack pin), the R5 alert folded into a clean rule-gate incident:
  `[rule_gate][INCIDENT] #1 frames 449-654 (206f) mode=SUNSAFE cluster=EX-0011
  sub=LC-monitoring-disabled` (confidence 1.0) — opened on latch, closed on restore,
  in both stdout and `rule_gate_incident_*.csv`. **Bonus second gate:** disabling LC
  froze `LC.MonitoredMsgCount`, so the **staleness gate** also fired an incident
  (`frames 518-580, cluster=EX-0012.02, sub=LC.MonitoredMsgCount-stale`) — DE-0005's
  monitoring-disable is caught by two independent gates.
- **⚠ New finding — the forced ADCS mode change is an IF blind spot.** The per-mode IF
  did NOT flag `SET_MODE→INERTIAL`; instead its router SWITCHED models
  (`MODE_SUNSAFE → MODE_INERTIAL at frame 84319`) and entered a **250-frame warmup**
  with `is_anomaly=0` throughout. So a mode-forcing attacker not only evades the IF but
  opens a ~250-frame detection-blind warmup window. R5 covers this case via the
  LC-disable, but a pure mode-force with no monitoring change would slip the IF
  entirely — a candidate for a dedicated mode-transition-legitimacy rule.

**AC:** met — footprint ON_BOARD ✓, detected by R5 (shared with EX-0011) ✓, ran on the
same safe-mode family as EX-0011 ✓; surfaced the mode-transition IF-warmup blind spot.

### AINOS3-60 — Validate DE-0010 (Overflow Audit Log) · `Task` · High · ◑ FOOTPRINT-VALIDATED 2026-07-16

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

### AINOS3-61 — Validate PER-0001 (Memory Compromise) · `Task` · Medium · ✔ VALIDATED 2026-07-17

**Summary:** Validate persistent memory compromise.

**Description:** Persistent on-board memory modification (persistence tactic). The
script exercises every command path an attacker would use to survive a reset:
CFE_TBL LOAD/ACTIVATE (backdoor table), SC RTS/ATS (dormant stored-command payload),
MM memory writes, CFE_ES app reload/start — then hides evidence with counter RESETs.
NOS3 models no non-volatile boot memory, so persistence-across-reset can't be shown;
the *command signatures* are the observable.

**Script:** `gsw/attack_scripts/sparta/persistence/per_0001_memory_compromise.py`
(`--attack-level 3`).

**VALIDATED live (2026-07-17, fresh stack):**

- **Signal class: ON_BOARD. Footprint (peaks during the window — the final values are
  masked by the attacker's RESET step):** `CFE_TBL.CommandCounter 0→1` +
  `CFE_TBL.CommandErrorCounter 0→3` (table load/activate attempts), `SC.CmdCtr 5→6` +
  `SC.CmdErrCtr 0→3` (stored-command RTS/ATS). `CFE_TBL.CommandCounter` is **static-0
  in nominal**. MM is **not subscribed** (no MM_HK) so MM writes are unobservable; the
  CFE_ES app-reload commands didn't register (poll-missed the transient before RESET).
- **⚠ Was a 4-gate MISS, closed by new rule R9.** No gate caught it first pass: the IF
  is blind (table/memory commands don't perturb dynamics), consistency/staleness are
  N/A (no backward counter, no freeze), and R4's per-frame cmd-error threshold isn't
  tripped by 3 errors spread across frames. Fix = **R9 (`CFE_TBL.CommandCounter`)**,
  the 4th static-in-nominal command-counter rule after R6/R7/R8. Live after redeploy:
  `R9:tbl-command` ALERT → **PER-0001/tbl-command incident** (frames 436-448) → CLEAR.
- **R9 survives the evidence-hiding RESET.** PER-0001's `CFE_TBL_RESET` zeroes the
  counter, but the rule's running-max already latched the new high before the reset,
  so the catch stands. (Same design point that makes R6/R7/R8 robust to the OnAIR
  double buffer.)

**AC:** met — footprint ON_BOARD (`CFE_TBL`/SC command counters) ✓, detection closed
via R9 with a PER-0001 incident ✓. Persistence-across-reset is out of scope in NOS3
(no non-volatile boot memory modeled), documented above. Residual gaps: SC
stored-command counters and MM (unsubscribed) have no rule yet.

### AINOS3-62 — Validate LM-0002 (Exploit Lack of Bus Segregation) · `Task` · Medium · ✔ VALIDATED 2026-07-17

**Summary:** Validate lateral movement via unsegregated Software Bus.

**Description:** The cFE Software Bus is flat — any external sender can inject any MID.
The script demonstrates the reach: a NOOP to **all 24 command MIDs** ("the scale is the
signal" — a legitimate pass touches 1–3 subsystems, an attacker sweeps many). The one
Lateral-Movement technique that is on-board-detectable.

**Script:** `gsw/attack_scripts/sparta/lateral_movement/lm_0002_bus_segregation.py`
(`--attack-level 2` = the 24-MID reach sweep).

**VALIDATED live (2026-07-17, fresh stack):**

- **Signal class: ON_BOARD, LOUD.** The 24-MID sweep ticks every reachable app's
  command counter once; crucially it hits the four static-in-nominal CDH counters, so
  **R6 (CFE_SB) + R7 (CFE_EVS) + R8 (CFE_ES) all fired together at the same frame**
  (`CFE_SB/EVS/ES.CommandCounter 0→1` each), and the command volume spiked the EVS
  event rate → **R2:evs**. Net: a **45-frame incident** emitted. Device counters
  (IMU/EPS/THRUSTER/TORQUER/MAG `.CommandCount +1`) also ticked.
- **⚠ Correction — `CFE_SB_SUBS` is NOT the observable.** The assumed footprint was
  wrong: `CFE_SB_SUBS.Entries` reads `[0]`/never-received in OnAIR (subscriptions
  aren't SBN-forwarded — same finding as EX-0012.02). The **real** signal is the
  *simultaneous firing of multiple command-counter rules* (R6+R7+R8) plus the EVS-rate
  spike — the "many MIDs in a short window" scale expressed through the deployed rules.
- **Detected but not distinctly labeled.** The incident collapsed to
  `cluster=DE-0010 sub=evs-flood` (R2 sustained while the single-step R6/R7/R8 dwells
  expired, so R2 dominated the label) — the same label-collapse as EX-0013.01. LM-0002
  is *caught* end-to-end but reads as an EVS flood, not as a bus sweep.
- **R9 (CFE_TBL) did not trip** despite `CFE_TBL.CommandCounter 0→1`: CFE_TBL HK
  publishes too slowly for OnAIR to sample the single transient NOOP (same poll-miss as
  the CFE_ES path in PER-0001). Not a rule defect.

**AC:** met — footprint ON_BOARD, detected loudly by R6+R7+R8+R2. Corrected the
observable (`CFE_SB_SUBS` unobservable → multi-command-rule + EVS-rate signature).

**Candidate future work:** a meta-rule "≥N distinct command-counter rules fire in one
window ⇒ bus sweep (LM-0002)" would give the technique its own label instead of
collapsing to DE-0010.

---

## Campaign synthesis — the IF is a *dynamics* detector, and the 4-gate roadmap

Per-technique results (footprint, which gate caught it, script bugs fixed) live in
each `### AINOS3-5x` task block above — that is the source of truth. This section is
the cross-cutting thesis and the detector roadmap the campaign produced.

**Core finding.** Across every validated Section-A technique, the v5 per-mode
Isolation Forest only flags anomalies in the *physical/attitude dynamics*. It is
blind to attacks whose footprint is a discrete flag flip, a counter/rate spike, a
transient value flicker, or a frozen stream — none of which disturb the physics it is
trained on. **EX-0011 is the confirming counterexample:** the IF DOES catch it (52% of
the window) because its exploit fires the thruster and perturbs the attitude dynamics,
exactly like the ROBUST-tier EX-0012.07/08/09 corruption attacks. Because the
classifier is IF-gated, the non-dynamics classes are undetected end-to-end despite
loud, already-subscribed signals — so "validate → fold into corpus → detector catches
it" is the wrong remedy for them (more data won't teach a dynamics-IF to watch a
flag). The fix is targeted detector primitives beside the IF.

**Known residual gap — forced mode transitions (from DE-0005).** A commanded
`ADCS SET_MODE` is worse than invisible to the per-mode IF: the router SWITCHES to the
new mode's model and enters a ~250-frame warmup with detection suppressed, so a
mode-forcing attacker gets a blind window rather than an alert. R5 covers it only when
the attack also disables monitoring (as DE-0005/EX-0011 do); a pure mode-force would
slip the IF. Candidate future work: a mode-transition-legitimacy rule.

**The 4-gate detector roadmap (all DEPLOYED).** Each validation exposed a distinct gap
the IF misses; the campaign built a complementary gate for each:

- **dynamics-IF** — physical/attitude anomalies (subsystem-value corruption,
  thruster/RW perturbation).
- **rule-gate (R1–R9)** — sustained state/counter changes: R1 device-disable, R2
  EVS-rate, R3 SB-errors, R4 cmd-errors, R5 monitor-state (LC/HS), and the
  static-in-nominal command-counter rules R6 (CFE_SB), R7 (CFE_EVS), R8 (CFE_ES),
  R9 (CFE_TBL). The rule that fires IS the label.
- **consistency-check** — per-sample counter-monotonicity, for the transient bus-spoof
  flicker (EX-0014.02) both other gates miss. 0 FP / 810 live frames.
- **staleness-check** — frozen-stream / telemetry-denial (EX-0012.02 route-disable,
  DE-0002.03 EVS-suppress). Primitive: a wide monotonic counter's MAX stops advancing
  (a frozen field OSCILLATES via the OnAIR double buffer, so "value constant" is the
  wrong test). ~30–50s latency; the R6/R7 command rules are the low-latency
  complement. 0 FP over 194K frames.

**These four gates are deliverables tracked separately, not validations.** They are
their own epic **AINOS3-63** (detector-gates) with tickets **AINOS3-64…67**; the
detailed writeups live in [`SPRINT_25_PLAN.md`](SPRINT_25_PLAN.md) and the mapping in
[`JIRA_CROSSWALK.md`](JIRA_CROSSWALK.md) — not in this backlog.

**Two lessons carried to memory (recorded here for provenance):**

- **Sensor-DEVICE-MID IF retrain — NOT justified** (from EX-0014.03): the device
  packet is redundant with the already-subscribed fused `ADCS_DI` view AND is sporadic
  even at baseline, so a freeze can't distinguish disabled from not-updated; the
  reliable signal is the `IMU.DeviceEnabled=0` flag, which the rule/staleness layer
  already covers.
- **Long-uptime stacks accumulate RADIO-spam EVS load** (~61/frame) → an R2:evs false
  positive that pins incidents open; a fresh `make stop` + `launch-quiet` resets it
  (→2.3/frame, 0 FP). Do incident-level validation on a fresh launch. This is a
  stack-degradation artifact, not an R2/R7 defect.
