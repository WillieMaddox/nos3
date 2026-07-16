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
| validate-safemode-exploit | EX-0011 | Task | Med | ✅ | ADCS/SC mode change |
| validate-routing-tables | EX-0012.02 | Task | High | — | `CFE_SB_SUBS` (subscribed) |
| validate-cdh-subsystem | EX-0012.10 | Task | Med | — | `CFE_ES`/`CFE_SB` counters |
| validate-flood-valid | EX-0013.01 | Task | Med | ✅ | cmd counters + `CFE_SB` errors |
| validate-flood-erroneous | EX-0013.02 | Task | Med | ✅ | `CFE_SB` error family |
| validate-bus-spoof | EX-0014.02 | Task | High | ✅ | injected SB msgs vs `CFE_SB_SUBS` |
| validate-inhibit-sc | DE-0002.03 | Task | Med | ✅ | subsystem HK quiet / errors |
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

**2/2 validated Section-A techniques so far are ON_BOARD but MISSED by the deployed
IF, for the same structural reason.** DE-0010 (EVS event-flood) and EX-0002 (GPS
DeviceEnabled→0) both leave clean, subscribed footprints the v5 per-mode IF does not
flag. Contrast: the already-validated EX-0012.07/08/09 subsystem-corruption attacks
ARE caught (ROBUST tier) — because they perturb the GNC *attitude dynamics* the IF
is trained on.

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

### validate-safemode-exploit — Validate EX-0011 (Exploit Reduced Protections in Safe-Mode) · `Task` · Medium
**Summary:** Validate the safe-mode exploitation technique.
**Description:** Force the vehicle into a safe/reduced-protection mode, then act
while protections are relaxed. Script `ex_0011_exploit_safe_mode.py` exists.
Footprint: ADCS/SC mode transition (already observable — `ADCS_GNC.Mode`, `SC`).
**AC:** common criteria; confirm the mode transition is captured + any follow-on.

### validate-routing-tables — Validate EX-0012.02 (Internal Routing Tables) · `Task` · High
**Summary:** Validate SB internal-routing-table modification.
**Description:** Modify the Software Bus routing/subscription tables to redirect or
duplicate message flow. Sibling of the already-done EX-0012.04 (app/subscriber
tables). **Directly observable in the subscribed `CFE_SB_SUBS` (0x080D) packet** —
a new/changed MsgId route after init. High priority: strong expected signal, low
effort. No script yet.
**AC:** common criteria; assert the specific `CFE_SB_SUBS.Entry` change.

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

### validate-bus-spoof — Validate EX-0014.02 (Bus Traffic Spoofing) · `Task` · High
**Summary:** Validate Software-Bus traffic spoofing.
**Description:** Inject spoofed SB messages impersonating a legitimate app.
Distinct from EX-0001 replay (which is byte-identical valid traffic) — spoofing
introduces messages/values inconsistent with the sender's normal pattern.
Observable via `CFE_SB_SUBS` (unexpected source) + the impersonated app's HK
diverging. High priority: broad relevance. Script exists at technique level.
**AC:** common criteria; show the spoofed-vs-genuine divergence.

### validate-inhibit-sc — Validate DE-0002.03 (Inhibit Spacecraft Functionality) · `Task` · Medium
**Summary:** Validate disabling/inhibiting a spacecraft subsystem as evasion.
**Description:** Disable or inhibit a subsystem (e.g. via a disable command) so it
stops functioning. Footprint: the target subsystem's HK goes quiet (stalled
counters) and/or error counts rise. Script exists at technique level.
**AC:** common criteria; confirm the "goes quiet" signal on a subscribed subsystem.

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
