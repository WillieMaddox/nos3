---
key: AINOS3-89
slug: catch-rate-provenance-gap
type: Spike
epic: AINOS3-79 (detector-rigor)
status: Open
priority: Medium
opened: 2026-08-11
sprints: [27]
---

# AINOS3-89 — Published catch rates disagree with measurement

**Summary:** As an analyst, I want to know why published per-technique catch rates disagree with fresh measurement **in both directions**, because until that is explained no per-technique number in the coverage doc can be quoted with confidence.

## Description

Measuring the same techniques on the 2026-08-11 corpus at the deployed
threshold gave results that diverge sharply from the published table, and not consistently:

| technique | published | measured | direction |
|---|--:|--:|---|
| EX-0014.04 PNT | 98 % | **7.4 %** | far worse |
| DE-0003.06 | < 25 % | **48.7 %** | far better |

A 90-point gap is too large for instance variance. Candidate causes: the attack script
behaves differently between collections (the Section-A campaign vs the weak-class corpus);
the published numbers came from a different corpus or a different threshold; or the
corruption-window labelling differs. This is distinct from the transient confound already
resolved by the steady-flight replication — these are same-corpus, same-threshold
comparisons.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Cause identified for at least the `EX-0014.04` case, the largest gap.
- [ ] `AC2` Determine whether the published table, the recent corpus, or both are unrepresentative.
- [ ] `AC3` Every per-technique catch rate in `V5_DETECTOR_COVERAGE.md` either re-derived from a named
      corpus with a provenance tag, or explicitly marked as unverified.
- [ ] `AC4` Note recorded in `AINOS3_80_METRIC_PROVENANCE.md`, which owns the provenance register.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
