---
key: AINOS3-100
slug: corpus-rebuild-steadyflight
type: Story
epic: AINOS3-98 (corpus-integrity)
status: Backlog
priority: Medium
opened: 2026-08-23
sprints: [28]
---

# AINOS3-100 — Recollect the classified attack set under the steady-flight protocol

**Summary:** Recollect the classified attack set under the steady-flight protocol, replacing the AINOS3-45 collection whose mode cycling put 83 % of attack frames inside the detector's blind window.

## Description

This ticket exists because `AINOS3-45` (`AINOS3-45`, *"4th corpus instance"*) was
scoped against the collection protocol found defective in Sprint 27 — mode cycling every 60 s
against a ~45 s detector warmup, leaving **83 % of attack frames inside the blind window**.
Executing it as written would have added a fourth LOIO fold built from unusable data, which is
worse than not collecting at all, because the tier rule takes the **minimum** across folds.

`AINOS3-45` was closed as superseded rather than re-scoped, per the crosswalk's immutability
rule; the binding decision is recorded there.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Classified attack set recollected under `single_mode_hold_<MODE>`; alert-eligible attack frame fraction reported against the 84.4 % pilot figure.
- [ ] `AC2` A **corpus manifest** is produced — scenario, date, schema sha256, FSW build, per-run technique and mode, frame counts. Its absence is what made four `AINOS3-80` metrics `[unverifiable]`.
- [ ] `AC3` Labels verified against `AINOS3-96`; schema settled per `AINOS3-95`; instance count justified by `AINOS3-99`.
- [ ] `AC4` ⚠ Collected with the **star tracker enabled** if any INERTIAL data is included — `AINOS3-86` established that INERTIAL performed no closed-loop control without it.
- [ ] `AC5` Operational discipline recorded: full `make stop` + `make launch-quiet` per run, chunks of ≤ 8 runs, never `nohup &`, parse with `csv.DictReader`.
- [ ] `AC6` ⚠ **Consume the frozen label set** (`data/onair/models/label_set.json`, `AINOS3-122 AC6`): collect only the `confirmed` + `deferred` techniques, label each run by its `label_set.json` id, and do **not** re-mint `dropped` classes (the 5 IMP, `EX-0012.04 [prereq]`) or auto-generate `[prereq]` technique labels (run chain prereqs without emitting a distinct technique label — the `AINOS3-122 AC4` finding).

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
