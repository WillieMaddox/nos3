---
key: AINOS3-95
slug: sparta-logging-gap-analysis
type: Spike
epic: AINOS3-41 (coverage-expansion)
status: Open
priority: High
opened: 2026-08-11
sprints: [27, 28]
---

# AINOS3-95 — SPARTA logging best practices vs what we record

**Summary:** As a defender, I want SPARTA's *Space Vehicle Logging Best Practices* mapped against the telemetry we actually record, because the binding constraint on this project is **observability** (AINOS3-69) and this is an authoritative, technique-indexed list of what a spacecraft *should* be logging.

## Description

Sourced from SPARTA's Indicators-of-Behavior page
(<https://sparta.aerospace.org/related-work/iob>): a guide PDF plus a **~20-sheet workbook**,
both in `data/sparta/` (git-ignored — Aerospace Corporation's to distribute; re-download from
the IOB page). Two distinct payoffs, and they should not be conflated:

1. **Consistency.** Our logging method changed repeatedly across the project, leaving a mix
   of formats and field sets. The guide gives an external standard to normalise against
   rather than an internally-invented one.
2. **Coverage.** The workbook indexes recommended log sources **by SPARTA technique**. Any
   row naming telemetry we don't currently subscribe to is a concrete observability lead —
   exactly what AINOS3-88 concluded we lack, and it arrives already tied to techniques
   rather than guessed at.

Every sheet must be read. A partial pass would most likely miss the sheets that matter,
since the useful content is the technique↔log-source mapping, not the prose.

**The artifact, measured** (2026-08-23) — `data/sparta/Space_Vehicle_Logging_Best_Practices-Distro_A.xlsx` is **19 sheets but only ~330 data
rows**: 13 subsystem sheets (Propulsion, ADCS, EPS, GN&C, C&DH, TT&C, SMS, TCS, Payload ×5)
at 11–38 rows × 10 cols each, plus `SPARTA_Mapping` — the technique ↔ log-source index —
at 78 rows × 7 cols, and five reference/metadata sheets. Reading it is half a day; the work
is cross-referencing against our 382-column schema. Expect the 5 Payload sheets to be **not
modelled by NOS3**; read them anyway and record that verdict, because "not modelled" is a
legitimate and reusable answer.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` All ~20 sheets reviewed; a one-line purpose recorded for each so the next reader can skip
      to the relevant one.
- [ ] `AC2` A gap table: recommended log source → do we record it (yes / inconsistently / no) → which
      MID would carry it if not.
- [ ] `AC3` Recommended sources split into **subscribable now** (a MID exists on the bus),
      **needs FSW work**, and **not modelled by NOS3**, with a count for each.
- [ ] `AC4` Any technique currently marked out-of-scope/UNSUBSCRIBED in `V5_DETECTOR_COVERAGE.md`
      that the workbook says *is* loggable is flagged explicitly — those are re-openable verdicts.
- [ ] `AC5` Feeds AINOS3-69's observability constraint and the AINOS3-45 corpus decision; does **not**
      itself subscribe anything.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.

