---
key: AINOS3-87
slug: detect-eps-switch
type: Story
epic: AINOS3-41 (coverage-expansion)
status: Open
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

- [ ] `AC1` Footprint confirmed live: run EX-0012.09 in held SUNSAFE (`single_mode_hold_SUNSAFE`) and
      identify which recorded field, if any, changes. Parse with `csv.DictReader`, never
      `awk -F','`.
- [ ] `AC2` **If an observable moves:** rule built as a sibling of R1/R5/R6–R13, labeled to EX-0012.09;
      0-FP over a nominal soak; unit tests; plugin synced to the build tree; live-verified.
- [ ] `AC3` **If nothing moves:** reclassified UNSUBSCRIBED in `V5_DETECTOR_COVERAGE.md` and the SPARTA
      matrix, with the evidence and a note on which MID would be needed.
- [ ] `AC4` Either way, the published 99 % catch rate is corrected to what is actually measured.

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
