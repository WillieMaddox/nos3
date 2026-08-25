---
key: AINOS3-106
slug: r15-latch-policy
type: Task
epic: AINOS3-79 (detector-rigor)
status: Open
priority: Medium
estimate: E 2 / T 0.5
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-106 — R15 latch policy after a clock jump

**Summary:** R15 latches until session reset after a forward clock jump, so one latched incident can mask a later, different attack.

## Description

R15 (`gps-time-divergence`, built in AINOS3-95) compares the monotonic envelope of the GPS
clock against the FSW clock. A **forward** jump raises the GPS envelope permanently, so the
divergence never returns to baseline and the rule stays active until the OnAIR session
restarts — observed live: 561 consecutive active frames after a single `SET_TIME`.

This is arguably correct — the clock really *is* wrong until reboot, so a persistent alert
reflects a persistent condition. But it has a cost: while latched, the incident aggregator
holds one open incident, and a later unrelated attack in the same session may be absorbed into
it rather than raising its own.

The decision is whether to re-baseline after N frames (bounding the incident, at the cost of
silently forgiving a clock that is still wrong), or to keep the latch and handle the masking
problem at the incident layer instead.

⚠ Do not treat this as a bug to fix reflexively — the latch is defensible. The ticket is to
make the choice deliberately and record the reasoning.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Determine empirically whether a latched R15 actually suppresses a subsequent unrelated incident, or whether the aggregator already separates them.
- [ ] `AC2` A decision recorded with reasoning: re-baseline (with N justified) or keep the latch.
- [ ] `AC3` If re-baselining: a test proving a still-wrong clock is not silently forgiven in a way that loses the detection.
- [ ] `AC4` The same question asked of the other latching rules (R5, R13) so the convention is consistent rather than per-rule accident.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
