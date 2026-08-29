---
key: AINOS3-84
slug: drop-bus-activity-retrain
type: Task
epic: AINOS3-31 (classification-trust)
status: Open
priority: Backlog
opened: 2026-08-11
sprints: [27]
---

# AINOS3-84 — Retrain dropping harmful bus-activity features

**Summary:** As an ML engineer, I want a retrain that drops the pure bus-activity features the AINOS3-39 audit found net-harmful, for a small free labeling gain — the PNT (`EX-0014.04`) improvement being the one that survives the IMP removal.

## Description

The AINOS3-39 counter-reliance audit found the generic counters net-contribute
overall, but a few *pure bus-activity* features MASK real signal — dropping `CFE_SB.MemInUse`
and the global EVS rate raised `EX-0014.04` (PNT) F1. This is a scoped, low-risk retrain:
remove only the demonstrably-harmful pure bus-activity features (not the genuine per-app
streams), retrain, and confirm LOIO shows no regression elsewhere before any deploy.

⚠ **Evidence base narrowed 2026-08-28.** The original justification named three beneficiaries —
PNT plus `IMP-0003` (denial) and `IMP-0006` (theft). Both IMP classes are among the five
deprecated-`IMP` classes removed from the label set (`label-set-freeze`, `AINOS3-96`
2026-08-28), so **two-thirds of this ticket's cited gain no longer exists as measured**. The
surviving PNT result was itself measured on the old 24-class label set, so it does not transfer
automatically either — it must be **re-measured against the frozen labels** before this retrain
is justified at all. Do not fold this into a retrain on the strength of the AINOS3-39 numbers;
re-run the drop-experiment on the post-freeze corpus first. Best still folded into the
Sprint-29 retrain (`AINOS3-101`) if it clears, to avoid a redundant retrain/deploy cycle.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` The harmful pure bus-activity features (per AINOS3-39) removed; classifier retrained on the
      frozen corpus.
- [ ] `AC1a` ⚠ **Pre-req:** the AINOS3-39 drop-experiment is re-run on the post-`label-set-freeze` corpus, so the "harmful features" list and the PNT gain are established on the frozen label set — not inherited from the pre-removal 24-class measurement.
- [ ] `AC2` LOIO shows the surviving gain (PNT, plus whatever `AC1a` confirms) retained with no regression on other clusters or modes.
- [ ] `AC3` Deploy only through the AINOS3-37 live-verify + one-line-rollback discipline; ini + build
      tree synced.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
