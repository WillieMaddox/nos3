---
key: AINOS3-118
slug: stix-guided-attack-generation
type: Story
epic: AINOS3-41 (coverage-expansion)
status: Open
priority: Medium
estimate: E 5 / T 2.0
opened: 2026-08-26
origin: AINOS3-96 (sparta-stix-ingest)
---

# AINOS3-118 — Generate and repair attack scripts from STIX IOB patterns

**Summary:** Use the IOB patterns as a formal spec to build attacks for uncovered vectors and repair the 18 partial scripts AINOS3-96 found — pattern-guided, not title-guided.

## Description

Every attack script predates the STIX install and was written from technique **titles**. The 855
IOB patterns are a formal spec of what each technique should *produce*, driving both new scripts
and repairs to weak ones — turning the `sparta-attack-script` skill from title-guided to
pattern-guided. Two workstreams, both fed by `AINOS3-116` + `AINOS3-115`:

1. **New attacks for uncovered vectors.** The index lists, per technique, the IOB patterns our
   script does *not* exercise — each a concrete missing vector. Where the pattern's arguments map
   to observables we record, it is buildable now; the owner notes this may make some
   `not-applicable` / `out-of-scope` techniques achievable by naming exactly what a working attack
   must move.
2. **Repair the 18 `partially-implements` scripts** from `AINOS3-96`: EX-0014.03/.04 *disable*
   sensors where the pattern demands *false-data injection*; EX-0014.01 *sets* system time where
   the pattern demands a *spoofed GPS input*. The pattern says what a faithful implementation does.

⚠ **Evaluation-provenance applies without exception.** A regenerated script is not done until
live-validated against the FSW (`/sparta-attack-test`) — the rule that cost this project a full
re-derivation once. A paper match with no footprint is not an attack.

⚠ **Large, open-ended** — 18 repairs plus unknown new vectors. Slice per technique/family; this is
an epic seed, not one change.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` A prioritised list of buildable missing vectors (arguments that map to recorded observables), distinct from those needing observability work first.
- [ ] `AC2` The EX-0014.01 repair as the first slice and exemplar: a script spoofing the NOVATEL GPS time input (via the `ci_lab` republish path), producing a GPS-time-anomaly footprint EX-0012.12 cannot — live-validated, confirming R15 actually catches it (closing the `AINOS3-96` 'recorded ≠ works' caveat).
- [ ] `AC3` Each repaired/new script live-validated via `/sparta-attack-test`; paper-only matches do not count.
- [ ] `AC4` For scripts that cannot produce their pattern's footprint, a recorded reason (observability gap vs not-modelled), feeding `AINOS3-117`.
- [ ] `AC5` Sliced into reviewable per-technique units.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

⚠ **Depends on** `AINOS3-116` and `AINOS3-115`. AC2 (EX-0014.01) is buildable earlier — its observables are already known.
