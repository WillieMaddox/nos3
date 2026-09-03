---
key: AINOS3-87
slug: detect-eps-switch
type: Story
epic: AINOS3-41 (coverage-expansion)
status: Done
priority: Medium
opened: 2026-08-11
sprints: [27, 28]
---

# AINOS3-87 — EX-0012.09 EPS switch toggle is undetected

**Summary:** As a defender, I want an EPS power-switch toggle detected, because the steady-flight replication found **nothing** detects `EX-0012.09` — not the anomaly detector, not any rule — while it is published at a **99 %** catch rate.

## Description

Measured across 3 independent runs in held SUNSAFE: IF lift **−0.4 ± 0.1**
(0.00 % of attack frames flagged) and **no rule-gate rule fired in any run**. The attack
sends `EPS_FC_SWITCH` with a `(switch_num, state)` payload — a **discrete state change**, so
the dynamics IF is structurally blind to it *by design*. That is expected and fine; what is
not fine is that its two siblings are covered and this one is not:

| technique | mechanism | caught by |
|---|---|---|
| EX-0012.08 | `ADCS_SET_MODE` | R14 (2/3 reps) |
| EX-0014.04 | GPS `FC_DISABLE` | R1 (2/3), R3 (1/3) |
| **EX-0012.09** | **`EPS_FC_SWITCH`** | **nothing (0/3)** |

The published 99 % comes from the pre-fix corpus, where 83 % of attack frames sat inside a
post-mode-switch blind window — it does not describe steady-flight behaviour.

First establish the on-board footprint, because the outcome forks:

- **If a recorded field moves** (an `EPS.DeviceHK.*` switch state, an EPS command counter),
  this is a cheap R1/R5/R6-style rule — baseline deviation or static-in-nominal new-high.
- **If nothing moves**, the technique is **UNSUBSCRIBED** and should be *reclassified* rather
  than detected. That is still a valuable outcome: it corrects a 99 % claim to an honest
  "structurally invisible", and tells us whether subscribing an EPS MID would close it.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` Footprint confirmed live: run EX-0012.09 in held SUNSAFE (`single_mode_hold_SUNSAFE`) and
      identify which recorded field, if any, changes. Parse with `csv.DictReader`, never
      `awk -F','`. **Live (2026-09-03): `EPS.CommandCount` 0→1 and `EPS.DeviceHK.Switch[1]`
      `[0,0,0]`→`[3300,250,170]` (Status 0xAA = ON). Both observables move.**
- [x] `AC2` **Observable moves → rule built.** `R17:eps-command` — `EPS.CommandCount` new-high + dwell,
      a sibling of R6–R12, labeled to EX-0012.09. `EPS.CommandCount` static-0 in nominal (22 h soak +
      live baseline) → 0-FP by construction (quiet through the nominal soak). 4 unit tests added (83
      pass). Plugin synced to the build tree. **Live-verified: firing EX-0012.09 fired `R17` and
      emitted incident `cluster=EX-0012.09 sub=eps-command`, reproduced on a second send.**
- [x] `AC3` **N/A — the observable moved, so the AC2 branch was taken, not the UNSUBSCRIBED branch.**
      (The IF *is* structurally blind — no consumption telemetry — but the switch command is caught by
      the rule, so the technique is detected, not reclassified.)
- [x] `AC4` The published 99 % is corrected in `V5_DETECTOR_COVERAGE.md`: EX-0012.09 is now **caught by
      R17** (the 99 % was a transient-dominated corpus artifact); the four gap/`0 %` statements updated.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.

### 2026-08-25 · AC3's negative branch is already answered — this ticket got cheaper (via AINOS3-95)

`AC3` forks on "if nothing moves, reclassify UNSUBSCRIBED and name the MID that would be
needed". SPARTA's logging workbook answers the naming half from an external authority, so that
branch no longer needs an investigation.

The workbook's `EPS` sheet names **change in power consumption** as the EPS detection signal,
baselined BOL/EOL with upper and lower limits (row 11, Medium). Measured against our schema:
`GENERIC_EPS_Hk_tlm_t` carries **five voltages and zero currents** —
`BatteryVoltage`, `Bus3p3Voltage`, `Bus5p0Voltage`, `Bus12Voltage`, `SolarArrayVoltage`, plus
three temperatures and the `Switch` bitfield.

So a switch toggle **cannot** move a consumption feature, because the schema has none. That
turns the measured **IF lift −0.4 ± 0.1** from "we could not find an observable" into a
structural explanation, and makes the UNSUBSCRIBED branch the well-evidenced one rather than a
fallback.

⚠ This does **not** close the ticket: `AC1`/`AC2` still require checking whether the toggle
appears in any *recorded* field (`EPS.DeviceHK.Switch` and `EPS.CommandCount` are both
recorded), and `AC4` still requires correcting the published 99 % catch rate. What is removed
is the open-ended search for an observable that the schema cannot contain.

**Named missing field, for AC3:** per-switch load or current telemetry in
`GENERIC_EPS_Hk_tlm_t` — an FSW change to the EPS sim, not a subscription.

### 2026-09-03 · DONE — R17:eps-command built + live-verified (closes the EX-0012.09 gap)

Live footprint (held SUNSAFE), then rule, then live verify — all on the same stack.

**AC1 footprint (live).** Baseline `EPS.CommandCount = 0`, all switches OFF. Fired EX-0012.09
(`EPS_FC_SWITCH`, switch 1 ON, `0x191A` FC2 via `CI_LAB:5012`). Result: `EPS.CommandCount` **0→1**
and `EPS.DeviceHK.Switch[1]` **`[0,0,0]`→`[3300, 250, 170]`** (Voltage/Current energized,
Status 0xAA=ON). So the "observable moves" branch — a rule, not the UNSUBSCRIBED reclassification.
⚠ The ticket's earlier lean toward UNSUBSCRIBED was about the *consumption* feature (which the EPS
schema genuinely lacks, so the IF stays blind); it overlooked that `EPS.CommandCount` and the switch
state are both recorded and both move.

**AC2 rule.** `R17:eps-command` — `EPS.CommandCount` new-high + dwell, a config-only sibling of
R6–R12 (the generic static-in-nominal counter mechanism). Precondition verified: `EPS.CommandCount`
is **static at 0** across a 22 h nominal soak (`csv.DictReader`, not `awk`) and the live baseline, so
0-FP is by construction — and it was quiet through the nominal soak before the attack. Added to the
`_cmd_rule` map + `_TECH_LABEL` + `_incident_label` (→ `EX-0012.09 / eps-command`), plus a docstring.
4 unit tests (latch / static-never-fires / double-buffer-flicker / incident-label); **83 pass**.

**Live verify.** Synced the plugin to the build tree, cycled the stack, fired the attack:
`[rule_gate][ALERT] frame=325 rule=R17:eps-command … (EX-0012.09)` → `[CLEAR]` after dwell →
`[INCIDENT] cluster=EX-0012.09 sub=eps-command`, reproduced on a second send. Cleanup restored the
switch OFF.

**AC4.** `V5_DETECTOR_COVERAGE.md`: the four "detected by nothing / ⚠ 0 % / confirmed gap" statements
for EX-0012.09 are corrected to "caught by R17"; the honest note is that the old 99 % was a
transient-dominated corpus artifact and R17 catches it whenever the switch command is on the bus.

**Operational note (this session).** The stack needs GSW up *before* `make launch-quiet` (`make gsw`
build once, then GSW survives `make stop`, so cycle with `make stop` + `make launch-quiet`). And
always read the **actively-growing** CSV, past OnAIR's ~30–60 s startup warmup — several early "0 Hz"
readings this session were warmup pauses or stale files, not real stalls.
