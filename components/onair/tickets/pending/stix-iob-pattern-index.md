---
key: —
slug: stix-iob-pattern-index
type: Spike
epic: AINOS3-41 (coverage-expansion)
status: Pending Jira key
priority: Medium
estimate: E 3 / T 0.75
opened: 2026-08-26
origin: AINOS3-96 (sparta-stix-ingest)
---

# stix-iob-pattern-index — Query the local STIX IOB↔technique↔pattern graph

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

- [ ] `AC1` A tool that, given a technique id, lists its linked IOBs with their STIX patterns, from the local bundle.
- [ ] `AC2` Reverse and cross queries: techniques sharing an IOB; the distinct pattern-argument vocabulary across all IOBs (the input list for `mid-stix-observable-map`).
- [ ] `AC3` A per-technique observability report joining IOBs to `mid_stix_map.json`: for each IOB, can we observe it, and does our claimed script exercise it?
- [ ] `AC4` The EX-0014.01 vs EX-0012.12 case reproduced as a regression fixture — distinct techniques whose unique IOBs are the separating signal.
- [ ] `AC5` Fetch provenance recorded: the bundle sha256 the graph was read from.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

⚠ **Depends on** `mid-stix-observable-map` for AC3. AC1/AC2 are buildable standalone.
