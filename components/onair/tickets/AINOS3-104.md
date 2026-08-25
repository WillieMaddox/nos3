---
key: AINOS3-104
slug: detect-adcs-gain-change
type: Story
epic: AINOS3-41 (coverage-expansion)
status: Open
priority: High
estimate: E 3 / T 1.0
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-104 — Detect ADCS control-gain changes

**Summary:** Nothing watches the ADCS controller gains that AINOS3-95 subscribed, though SPARTA's workbook rates 'change in control logic/algorithms' High on both the ADCS and GN&C sheets.

## Description

AINOS3-95 stage 2a subscribed `GENERIC_ADCS_AC_MID` `0x0944`, which carries every controller's
gain set: `Bdot.{Kb,b_range}`, `Sunsafe.{Kp,Kr,vmax}`, `Inertial.{Kp,Kr,Ki,phiErr_max}`, plus
the live error state (`therr`, `sumtherr`, `werr`, `qErr`).

The gaps analysis (`SPARTA_LOGGING_GAP.md`, row `GEN-CTRLLOGIC`) records this recommendation as
**closed for recording and open for detection**: the gains are now in the corpus and **no
detector looks at them**. A gain is constant in nominal flight, so a change is a clean
static-in-nominal signal of exactly the kind R5/R13 already exploit for state fields.

Ten of the workbook's thirteen subsystem sheets carry this recommendation, and the ADCS and
GN&C sheets both rate it **High** — the joint-highest-value unexploited row in the analysis.

⚠ Sequencing note: the INERTIAL gains are only meaningful when the controller actually runs,
which requires `qValid` — see AINOS3-86. A gain-change rule should be validated in SUNSAFE
first, where the controller is unconditionally active.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Nominal constancy of each gain field measured across all four ADCS modes, so 'static in nominal' is demonstrated rather than assumed.
- [ ] `AC2` A rule fires on a commanded gain change, keyed on baseline deviation (R5/R13 shape) rather than a counter new-high.
- [ ] `AC3` 0 false positives across a nominal soak of at least 3,000 frames, including at least one mode transition.
- [ ] `AC4` Validated against a LIVE gain-modification command, not offline injection.
- [ ] `AC5` The integrator wind-up observable (`Inertial.sumtherr`) is assessed as a separate signal and either used or explicitly declined with a reason.
- [ ] `AC6` Coverage overlay updated in this ticket.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
