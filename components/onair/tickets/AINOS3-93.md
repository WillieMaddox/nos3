---
key: AINOS3-93
slug: overlay-column-scope-mismatch
type: Bug
epic: AINOS3-79 (detector-rigor)
status: Open
priority: Medium
opened: 2026-08-11
sprints: [27]
---

# AINOS3-93 — `Catch` and `Incidents` are not comparable

**Summary:** As a presenter, I want the overlay to stop displaying two figures side by side that describe non-overlapping populations, because reading across them produces confident wrong conclusions — and it already has, twice.

## Description

The technique panel shows **Catch** and **Incidents** as adjacent columns.
They cannot be compared:

- **Catch** is the per-frame flag rate **in SUNSAFE only**.
- **Incidents** are attributed to each attack's **first corruption frame's mode**. Attacks
  start where the FSW boots, so the corpus holds **91 PASSIVE · 23 INERTIAL · 1 BDOT ·
  0 SUNSAFE** incidents.

The two columns therefore share **zero attacks**. No arithmetic between them means anything
— not a difference, not a ratio, not a direction — yet the layout invites exactly that.
`V5_DETECTOR_COVERAGE.md` §B already warns these are "two views that must not be confused",
but the overlay presents them as if they were one.

This is not hypothetical. **Two false conclusions have already been drawn from it:**

1. `EX-0012.09` showing "0 % caught" beside "3/3 incidents" was read as a stale-data
   contradiction. It is not — those incidents are simply all non-SUNSAFE.
2. `EX-0012.08` (incident recall 67 % *below* its 100 % catch) was flagged as an inverted
   result suggesting the incident aggregator was dropping real signal, and was one step from
   being ticketed as a detector defect. It is an artifact of comparing disjoint populations.
   `app/check_overlay_consistency.py` carries the retracted test as a comment so the mistake
   is not re-made.

The fix is presentational, not analytical — no re-measurement is required, which is what
separates this from **AINOS3-89** (that one owns whether the Catch *values* are right; this
one owns whether they can be read against the neighbouring column at all).

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Each column states its population in the UI — at minimum "SUNSAFE frames" on Catch and the
      attributed-mode rule on Incidents — so scope is visible without opening the coverage doc.
- [ ] `AC2` A panel whose Incidents contain no frames from Catch's mode does not render them as a
      side-by-side pair, or renders them visibly separated.
- [ ] `AC3` The footer key explains that the two columns are not comparable and why (one sentence).
- [ ] `AC4` `check_overlay_consistency.py` still passes with no new blocking finding; its `SAYS-BOTH`
      rule is re-examined once the presentation changes, since it exists to catch the same
      misreading.
- [ ] `AC5` Ideally: report incidents per mode, or restrict the pairing to a common mode, so the
      comparison becomes meaningful rather than merely labelled — record the decision either way.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
