---
key: AINOS3-94
slug: coverage-table-schema
type: Spike
epic: AINOS3-79 (detector-rigor)
status: Open
priority: Medium
opened: 2026-08-11
sprints: [27]
---

# AINOS3-94 — Redesign the coverage-table schema

**Summary:** As a maintainer, I want the per-technique coverage table rebuilt around a cell contract that makes mode, provenance and null-state explicit, because nine separate defects in Sprint 27 trace to the schema rather than to the care taken with any one number.

## Description

Full argument and proposed schema in
[`COVERAGE_TABLE_REDESIGN.md`](COVERAGE_TABLE_REDESIGN.md). In short, four structural causes:

- **C1 — the row's unit is wrong.** One row per technique, but mode dominates the answers
  (nominal FP 0.00 %→33.6 %, naming 10 %→35 % across modes). Each column resolves mode
  *silently and differently*: `Catch` is SUNSAFE-only, `Incidents` are attributed to the
  attack's first-frame mode (**zero** SUNSAFE), `tier` averages all four. `Catch` and
  `Incidents` share no attacks yet sit adjacent.
- **C2 — three questions in one row** (did we see it · which detector · can we name it), so
  `Catch` mixed IF detections with rule-gate catches and `tier` absorbed `SIBLING`, which is
  cluster membership, not a confidence level.
- **C3 — per-cell provenance is displayed nowhere.** `frame_rate` is the last hardcoded
  numeric column left.
- **C4 — `None` means not-measured, suppressed, *and* not-applicable**, all rendered `—`.

C1 and C3 alone account for six of the nine defects. This is a **schema-first** spike: define
the cell contract, migrate the generator, let the overlay follow. The overlay is the cheap
part; the expensive part is four artifacts feeding it on mismatched assumptions nobody wrote
down.

⚠ **Accept deliberately:** making mode explicit turns one number per technique into four
cells, most reading `not-measured`, because outside SUNSAFE they are. The table will look
markedly worse. That is a presentation regression and an honesty improvement, and it must be
briefed as such — ideally alongside the ROBUST correction rather than as a second surprise.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Cell contract defined (`value` · `unit` · `state` · `scope.mode` · `provenance` ·
      `interval.resampled`) with a validator that **fails the build** on a missing `state`,
      `scope` or `provenance` — mirroring the doc's "an untagged number is a bug" rule.
- [ ] `AC2` Already-derived columns (tier, cluster, explanation) migrated onto it with **no
      re-measurement**, proving the contract on real data.
- [ ] `AC3` A written decision on stages 3–5 (per-mode `frame_rate`, the detection/attribution/naming
      split, per-mode rendering) — scoped and sequenced, not necessarily built in this spike.
- [ ] `AC4` Boundary with **AINOS3-89** recorded: stage 3 subsumes it, so the two must not both run.
- [ ] `AC5` Sequencing recorded: stages 3–5 gated on **AINOS3-86**, since making mode a first-class
      axis while INERTIAL is uninterpretable builds a column of noise.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
