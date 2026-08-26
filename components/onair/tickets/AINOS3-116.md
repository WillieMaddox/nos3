---
key: AINOS3-116
slug: stix-iob-pattern-index
type: Spike
epic: AINOS3-41 (coverage-expansion)
status: Done
priority: Medium
estimate: E 3 / T 0.75
opened: 2026-08-26
closed: 2026-08-26
origin: AINOS3-96 (sparta-stix-ingest)
---

# AINOS3-116 — Query the local STIX IOB↔technique↔pattern graph

**Summary:** Expose the SPARTA IOB graph already in the bundle (855 indicators, 855 indicates-relationships) as a queryable tool, so per-technique IOB coverage checks are repeatable.

## Description

`AINOS3-96` established that the full SPARTA Indicators-of-Behavior graph is **already in the
downloaded bundle** — 855 `indicator` objects each with a formal `pattern`, linked to techniques
by 855 `indicates` relationships (plus 2,652 `related-to`). No scraping of
<https://sparta.aerospace.org/related-work/iob> is needed; the data is local.

This ticket exposes that graph as a queryable tool so the per-technique IOB list — which
`AINOS3-96` pulled ad-hoc to break the EX-0014.01/EX-0012.12 degeneracy — becomes repeatable:
"every IOB pattern for technique X", "which techniques share IOB Y", "the pattern-argument
vocabulary across the corpus".

Direct payoff: for each technique, list its IOB patterns and check whether our script exercises
each — a **rigorous per-attack-vector coverage check** replacing the prose-vs-`_send` judgement
`AINOS3-96` flagged as subjective. It may make some `not-applicable` / `out-of-scope` verdicts
re-openable by naming the exact observable a detection would need.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` A tool that, given a technique id, lists its linked IOBs with their STIX patterns, from the local bundle.
- [x] `AC2` Reverse and cross queries: techniques sharing an IOB; the distinct pattern-argument vocabulary across all IOBs (the input list for `AINOS3-115`).
- [x] `AC3` A per-technique observability report joining IOBs to `mid_stix_map.json`: for each IOB, can we observe it, and does our claimed script exercise it?
- [x] `AC4` The EX-0014.01 vs EX-0012.12 case reproduced as a regression fixture — distinct techniques whose unique IOBs are the separating signal.
- [x] `AC5` Fetch provenance recorded: the bundle sha256 the graph was read from.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

⚠ **Depends on** `AINOS3-115` for AC3. AC1/AC2 are buildable standalone.

### 2026-08-26 · DONE — `stix_iob_index.py`, the IOB graph as a queryable tool

Built on AINOS3-96's finding that the graph is local: 855 indicators + 855 `indicates`
relationships. No stack, no scraping. Six commands, all five ACs demonstrated.

**`AC1` — `--technique`.** Lists a technique's IOBs + patterns. ⚠ Immediate payoff for
`AINOS3-87`: EX-0012.09's IOB **`UACE-3`** names exactly what would catch the undetected EPS
switch — `command_log:command_type='legitimate_command' AND target_subsystem != 'expected' AND
parameter_value > 'safe_threshold'`. That is the observable AINOS3-87's negative branch was
looking for, sourced from STIX rather than guessed.

**`AC2` — `--shared` and `--args`.** The argument vocabulary is **254 distinct arguments — an
exact match to AINOS3-115's independent extraction**, confirming the two tools read the graph
the same way.

**`AC3` — `--coverage`.** Joins each IOB to `mid_stix_map.json`'s states. ⚠ Corrected a bug
during build: an IOB needs **all** its arguments observable to fire, so its score is the
**weakest** argument's state, not the best — my first pass took the max and mislabelled GNTM-5
`verified` when its GPS-input half is unverified. Now conservative. Two known limitations,
recorded not hidden:

- **AND/OR:** the weakest-argument score is right for AND-patterns and under-counts OR-patterns
  (one observable arg suffices). Distinguishing them needs pattern-logic parsing — deferred.
- **selector vs measure:** a literal like `system:component='time_controller'` is a *selector*
  (which component), not a *measure* (the anomaly). Treating selectors as observables-needed
  drags some IOBs to `unmapped` (e.g. GNTM-6). A refinement, not a blocker.

**`AC4` — `--degeneracy`, the regression fixture.** Reproduces the hand analysis exactly:
`EX-0012.12` vs `EX-0014.01` → **SEPARABLE**, each with unique IOBs (EX-0014.01's GNTM-5/9/10
GPS-input signals vs EX-0012.12's onboard-value/backdoor signals). The tool now makes that
judgement mechanically for **any** of the AINOS3-96 phase-2 degeneracy groups — which is its
purpose: that 10-group work-queue can now be triaged degeneracy-vs-script-limitation by command,
not by hand.

**`AC5` — `--provenance`.** Prints the bundle sha256
(`f9ce5b05…`) and contents (270 attack-patterns, 855 indicators), so a re-download that changes
the graph is detectable.

**Hand-off:** `AINOS3-118` uses `--technique`/`--coverage` to pick buildable missing vectors and
promotes `mid_stix_map` rows to `verified` as it validates; `AINOS3-117` uses `--degeneracy`
across the phase-2 queue. ⚠ The `UACE-3` finding above is a live lead for `AINOS3-87` right now.
