---
key: AINOS3-84
slug: drop-bus-activity-retrain
type: Task
epic: classification-trust
status: Open
priority: Backlog
opened: 2026-08-11
sprints: [27]
---

# AINOS3-84 — Retrain dropping harmful bus-activity features

**Summary:** As an ML engineer, I want a retrain that drops the pure bus-activity features the AINOS3-39 audit found net-harmful, for a small free labeling gain on PNT / theft / denial.

## Description

The AINOS3-39 counter-reliance audit found the generic counters net-contribute
overall, but a few *pure bus-activity* features MASK real signal — dropping `CFE_SB.MemInUse`
and the global EVS rate raised EX-0014.04 (PNT) F1 and helped IMP-0003 (denial) / IMP-0006
(theft). This is a scoped, low-risk retrain: remove only the demonstrably-harmful pure
bus-activity features (not the genuine per-app streams), retrain, and confirm LOIO shows no
regression elsewhere before any deploy. Best folded into a `signal-feasibility` retrain if that clears,
to avoid a redundant retrain/deploy cycle.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` The harmful pure bus-activity features (per AINOS3-39) removed; classifier retrained on the
      frozen corpus.
- [ ] `AC2` LOIO shows the PNT/theft/denial gain retained with no regression on other clusters or modes.
- [ ] `AC3` Deploy only through the AINOS3-37 live-verify + one-line-rollback discipline; ini + build
      tree synced.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
