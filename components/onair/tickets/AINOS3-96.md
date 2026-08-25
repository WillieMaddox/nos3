---
key: AINOS3-96
slug: sparta-stix-ingest
type: Spike
epic: AINOS3-41 (coverage-expansion)
status: In Progress
priority: High
opened: 2026-08-19
sprints: [27 (scoped, not started), 28 (in progress)]
---

# AINOS3-96 — Use the SPARTA STIX 2.1 dataset as ground truth

**Summary:** As a security researcher, I want the SPARTA knowledge base ingested in its
**STIX 2.1** form, because it is the most granular representation available and every other
view (including the HTML matrix we built the overlay from) is derived from it.

## Description

Per the SPARTA user guide, the dataset ships as STIX 2.1 and is most easily handled with the
`stix2` Python library, or as plain JSON from the API. Three uses, in descending confidence:

1. **Validate what we claim.** We have 30-plus attack scripts asserting they implement a given
   technique. STIX carries each technique's authoritative description and relationships — a
   script whose behaviour does not match its technique's definition is a mislabelled result,
   and mislabelled results have already cost this project a full re-derivation
   (`EX-0012` wave-1).
2. **Enumerate what we have never attempted**, mechanically, instead of by reading the matrix
   by eye.
3. **Explore the design space** — relationships between techniques, countermeasures, and IOBs
   that the flat matrix does not expose.

Worth deciding as part of this: whether STIX becomes a **build-time source** for the coverage
matrix rather than the hand-maintained technique lists in `gen_nos3_coverage.py`. That would
remove a whole class of drift and is a natural fit with
[`COVERAGE_TABLE_REDESIGN.md`](../COVERAGE_TABLE_REDESIGN.md).

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` STIX bundle fetched and loadable; the fetch documented and repeatable
      (API call or download path), not a one-off manual step.
- [ ] `AC2` Every validated attack script mapped to its STIX technique object;
      mismatches between script behaviour and technique definition listed.
- [x] `AC3` Techniques with no script enumerated, separated from techniques ruled
      out-of-scope.
- [ ] `AC4` A recorded decision on STIX-as-build-source for the coverage matrix —
      yes/no with reason.
- [ ] `AC5` **Verdict per attack script**, not just a mismatch list:
      `implements-as-claimed` / `mislabelled (correct technique named)` /
      `partially implements` / `undecidable from STIX`. A count in each bucket is the
      headline result.
- [x] `AC6` **A written decision on the multi-member clusters** — does STIX support
      treating `EX-0012.{03,04,05}` as one class, or are they genuinely distinct techniques
      our telemetry cannot separate? Different problems, different fixes.

> `AC5`–`AC6` added 2026-08-23.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-08-23 · re-prioritised Medium → High; AC5 and AC6 added

Raised to High because it **gates the label set** that any corpus rebuild and retrain are
built on — a mislabelled class propagates into LOIO folds, cluster taxonomy, tier column and
explanation catalog before anyone checks.

Where it sat in Sprint 28's ordering, and why, is in
[`SPRINT_28_PLAN.md`](../SPRINT_28_PLAN.md) — that is sprint-scoped and does not belong here.

⚠ Setup: `stix2` was missing from `~/.virtualenvs/nos3` — installed 2026-08-23 (3.0.2).

### 2026-08-24 · AC1 DONE — fetch is repeatable, with a trap recorded

`components/onair/training/fetch_sparta_stix.py`; bundle at
`data/sparta/sparta_stix_latest.json` + sha256 sidecar. **SPARTA v4.0**, 4,901 objects,
270 attack-patterns (137 parent + 133 sub) across 10 tactics.

⚠ Only `f=latest` is machine-retrievable. Requesting `f=sparta_data_v3.2.json` returns the
site's **HTML page with HTTP 200 and a 4.9 MB body** — indistinguishable from success by
status code. The fetcher validates the payload; all three rejection paths unit-checked.

⚠ Our coverage matrix is triaged against **v3** (177 leaves); v4.0 has 270 and adds an
entirely new `SV` tactic (44 techniques) never assessed.

### 2026-08-24 · AC3 DONE — 113 of 270 techniques have no script

`{'SV': 44, 'EX': 36, 'IMP': 8, 'IA': 6, 'REC': 6, 'RD': 5, 'DE': 4, 'EXF': 3, 'PER': 1}`.
⚠ "has a script" ≠ validated — only ~32 techniques have validated footprints.

### 2026-08-24 · AC6 DONE — the two clusters get opposite verdicts

`components/onair/training/map_scripts_to_stix.py`; 159 scripts, 157 distinct claimed IDs,
**158/159 resolve** to a real v4.0 technique (the one flag, `demo_gnc_kill_chain.py`,
legitimately claims none). Title mismatches: 3, all phrasing.

- **`EX-0012.12` / `EX-0014.01` — the same action, not indistinguishable telemetry.** Both
  scripts send `CFE_TIME` MID `0x1805` `FC=7` SET_TIME after a NOOP; `EX-0014.01` contains no
  GNSS or injection mechanism at all. STIX defines `EX-0014.01` by its **vector** (forge the
  time seen by consumers), whereas commanding `SET_TIME` is the authorised path — the
  definition of `EX-0012.12`. Verdict **`partially implements`**. The class is unlearnable by
  construction: identical bytes, so the classifier is asked to infer intent from telemetry.
  Fix: reimplement as a genuine spoof (feasible — `ci_lab_app.c:348` republishes any MID onto
  the bus, per the `EX-0014.02` work) or drop the class.
- **`EX-0012.{03,04,05}` — genuinely distinct.** STIX describes three different targets and
  mechanisms (raw memory writes / pub-sub subscriber tables / scheduler parameters). The
  identical fold triple is a telemetry limit, so the fix is **observability, not collapsing
  the taxonomy**.

### Open

`AC2` behavioural review is 5 of 157 deep (prioritised the 26 classifier labels and the
clusters). `AC4` untouched. `AC5` needs the AC2 sweep to produce bucket counts.
