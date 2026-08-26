---
key: AINOS3-90
slug: verify-nominal-incident-filter
type: Task
epic: AINOS3-79 (detector-rigor)
status: Done
priority: High
opened: 2026-08-11
closed: 2026-08-23
sprints: [27, 28]
---

# AINOS3-90 — Is `cluster=nominal` filtered from the operator view?

**Summary:** As an operator, I want to know whether incidents labelled `cluster=nominal` reach the operator display, because that single fact decides whether INERTIAL's **71 false incidents per hour** are an invisible annoyance or a credibility problem.

## Description

The AINOS3-81 soak raised 81 false incidents in 7 h of nominal flight — 71 of
them in a single hour of INERTIAL — all labelled `cluster=nominal`. If the overlay / operator
view filters those out, the impact is confined to log volume. If it does not, the monitor
cries wolf roughly once a minute in that mode, which would dominate any stakeholder
impression of reliability. **We have not checked.** Cheap to answer and it re-prioritises
`AINOS3-86` (AINOS3-86) either way.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` Determine, from the deployed overlay/reporter path, whether `cluster=nominal` incidents are
      surfaced or suppressed. Evidence, not inference.
- [x] `AC2` If surfaced: raise the priority of AINOS3-86 and note the operator impact in
      `V5_DETECTOR_COVERAGE.md`.
- [x] `AC3` If suppressed: record where the filter lives, so it is not removed by accident later.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.

### 2026-08-23 · AC1–AC3 DONE — nothing filters `cluster=nominal`, at any layer

**Result:** ✅ DONE (2026-08-23) — **NO. Nothing filters it, at any layer.** The answer is
the credibility branch, and the ticket's implied cheap mitigation turns out to be a trap.

**Code evidence — the deployed reporter path has no cluster predicate.** Every closed
incident reaches the operator through `_handle_incident`
(`fsw/plugins/xgb_classifier/xgb_classifier_plugin.py:585`), which prints a
`[xgb_cls][INCIDENT #N] … → nominal` line and appends the row to `incident_*.csv`
unconditionally. There is no `if cluster == "nominal"` anywhere in the chain, and the three
sibling gates (`rule_gate`, `consistency_check`, `staleness_check`) write their own incident
files by the same unfiltered pattern. Nothing downstream re-reads those files with a filter
either — the coverage overlay in `app/` is a static offline artifact, and OnAIR publishes no
telemetry into COSMOS, so the console log and the CSV **are** the operator view.

**Data evidence — 55.8 false incidents/hour, all visible.** Measured on
`incident_2026-08-15T14-29-46-306680_pid11.csv`: an 86.9 h `MODE_INERTIAL` session whose
manifest (`scenarios/manifest_2026-08-15T14-29-48Z.json`) confines its attack batch to the
first 15 min. Restricting to the post-batch, definitively-nominal window — 86.6 h,
**4,836 incidents, 100 % `cluster=nominal`**, median 8 frames — gives **55.8 incidents/hour**.
The ticket's figure of 71/hr is the same order; treat 55.8 as the measured replacement.
Across all 113 archived incident files, 5,865 of 6,435 INERTIAL incidents (**91.1 %**) carry
`cluster=nominal`.

⚠ **Do not "just filter `cluster=nominal`" — it would cost 48.4 % of true attack frames.**
The mitigation is tempting because it is one predicate and it is 100 %-effective on the clean
window above. It is also exactly the shape of the sun-acquisition rule that nearly shipped on
a clean nominal correlation. Checked on the attack side first, per this sprint's standing
rule: in `loio_predictions_oof_v3hybrid_full.npz`, **48.4 % of the 79,932 true-attack frames
are themselves predicted `nominal`** (BDOT 54.2 % · PASSIVE 55.7 % · SUNSAFE 47.8 % ·
**INERTIAL 39.3 %**). Suppressing that cluster suppresses those frames too.

*Stated limit:* that 48.4 % is **frame-level**, and incidents aggregate frames by summed
top-1 probability, so the incident-level cost is lower — but it is not zero, and nobody has
measured it. A nominal-suppression filter is therefore **not** a free win and must not ship
without that measurement.

**Consequence for `AINOS3-86`:** urgency **confirmed High**. 55.8 visible false incidents per
hour in a mode with no attack running is a credibility problem in the operator's face, not a
log-volume annoyance, and the one-line cosmetic escape is closed.

**Side finding, not chased:** three archived incident files carry `cluster` values of `25`
and `15` in `MODE_PASSIVE` — integers where a label belongs, i.e. a header-version mismatch
between the writer and those files. 11 rows, all pre-dating the hybrid deployment. Noted for
`AINOS3-97`'s inventory rather than fixed here.
