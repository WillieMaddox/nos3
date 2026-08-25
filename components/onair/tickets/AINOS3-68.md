---
key: AINOS3-68
slug: deepsad-revisit
type: Spike
epic: —
status: Blocked
priority: Backlog
opened: 2026-07-15
sprints: [26]
---

# AINOS3-68 — Reopen Phase 5 (DeepSAD / VAE) feasibility

**Summary:** As an ML engineer, I want to re-run the Phase-5 semi-supervised deep anomaly-detector (DeepSAD / VAE) feasibility assessment once a signal-broadening effort has changed the data-sufficiency picture that drove the original NO-GO.

## Description

`AINOS3-69` (next-ml-bet) returned Phase-5 DeepSAD as **NO-GO** — the
binding constraint was signal / observability, not model capacity, so a deep
semi-supervised model wouldn't beat the deployed IF + XGB stack on the available data. This
spike is **gated, not scheduled**: it reopens only when the signal picture materially
improves. The designated gate is `AINOS3-30` (recover the nominal-ambiguous DEAD classes),
which returned **NULL** (its CFE_TBL premise was disproven), so the gate is **not cleared**.
Reopen when either (a) a validated technique finally moves the CFE_TBL table-activity fields
and revives AINOS3-30 with real signal (see the AINOS3-75 / DE-0006
trigger note above), or (b) the Section-B detections + corpus growth broaden the labeled
signal enough to change the data-sufficiency verdict.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Reopened only against a cleared gate (AINOS3-30 revived, or a materially broader corpus);
      the trigger that cleared it is recorded.
- [ ] `AC2` DeepSAD / VAE re-assessed against the then-current corpus vs the deployed IF + XGB
      baseline under LOIO.
- [ ] `AC3` Deliverable is a GO/NO-GO recommendation with evidence — no deploy from the spike itself.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
