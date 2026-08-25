---
key: AINOS3-91
slug: startracker-inert-fields
type: Spike
epic: AINOS3-41 (coverage-expansion)
status: Open
priority: Medium
opened: 2026-08-11
sprints: [27]
---

# AINOS3-91 — 5 `ST_DEV` star-tracker fields are constant

**Summary:** As a defender, I want to know why five star-tracker fields never change, because an ADCS-relevant sensor reporting nothing is either a dead subscription or a blind spot, and both matter.

## Description

In the 41,434-row weak-class corpus, `ST_DEV.Generic_star_tracker.IsValid`
and `.Q0`–`.Q3` are **constant across every frame**. Found incidentally during the
signal-feasibility ablation, where 15 of 109 added columns were inert — the other ten are
explained (6 `CFE_TBL` known-dormant, 4 `TORQUER`), these five are not. A star tracker
supplies attitude quaternions; if it genuinely produces nothing, any attack on it is
invisible, and the fused `ADCS_DI` view may be carrying the whole attitude signal alone.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Determine whether the star tracker is emitting and OnAIR is mis-parsing, or the sim never
      populates the fields (compare against the FSW struct as done for `TO_HkTlm_t` in
      AINOS3-30/88).
- [ ] `AC2` If mis-parsed: fix the schema and confirm the fields move.
- [ ] `AC3` If never populated: record it, and reclassify any star-tracker technique that depends on
      them as UNSUBSCRIBED rather than covered.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
