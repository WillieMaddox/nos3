---
key: —
slug: coverage-triage-stix-v4
type: Spike
epic: AINOS3-41 (coverage-expansion)
status: Pending Jira key
priority: Medium
estimate: E 3 / T 1.0
opened: 2026-08-26
origin: AINOS3-96 (sparta-stix-ingest)
---

# coverage-triage-stix-v4 — Triage the SPARTA v4.0 techniques absent from our v3 matrix

**Summary:** Assess the ~93 v4.0 techniques (incl. the new 44-technique SV tactic) our v3-indexed coverage matrix has never seen, and decide whether to re-index to v4.0.

## Description

Our coverage matrix (`V5_DETECTOR_COVERAGE.md`, `app/gen_nos3_coverage.py`) is triaged against
SPARTA **v3 — 177 leaves**. The fetched bundle is **v4.0 — 270 attack-patterns**, and `AINOS3-96`
confirmed the delta includes an entirely new **`SV` tactic (44 techniques)** never assessed, plus
new/renumbered techniques elsewhere (the owner noted IA-0013, DE-0012, DE-0003.13,
IMP-0007…IMP-0014 among others).

⚠ **NOT about the classifier's classes.** A v4.0 technique with no script is a coverage gap to
assess, not a class to add — a class with no data is an empty class. This ticket only touches the
coverage matrix: for each v4.0-new technique, the same triage every leaf got — detectable /
needs-work / not-applicable / out-of-scope, with a reason.

⚠ It forces the decision `AINOS3-96 AC4` raised: the matrix is v3-indexed, the world moved to
v4.0. Re-index to v4.0 (renumbering existing leaves — a real migration) or annotate the additions
onto the v3 base? Record the choice; do not let it happen implicitly.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` The v4.0-vs-v3 delta enumerated from the bundle: added, deprecated, renumbered — a table, not a count.
- [ ] `AC2` A recorded decision on re-indexing to v4.0 vs annotating additions onto v3, with the migration cost of each.
- [ ] `AC3` Each v4.0-new technique triaged with a reason, the SV tactic's 44 included.
- [ ] `AC4` The `AINOS3-96` deprecated-technique fallout folded in: the 5 deprecated IMP leaves resolved to v4.0 successors or marked retired.
- [ ] `AC5` Coverage counts restated against whichever indexing AC2 chose, so the headline is honest about which SPARTA version it measures.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
