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
- [x] `AC2` **DONE for the 24 classifier classes** (phase 1). Behaviour vs definition compared for all 24 via `audit_script_vs_stix.py`; mismatches listed in the 2026-08-26 log. Phase 2 (~133 non-class scripts) deferred.
- [x] `AC3` Techniques with no script enumerated, separated from techniques ruled
      out-of-scope.
- [ ] `AC4` A recorded decision on STIX-as-build-source for the coverage matrix —
      yes/no with reason.
- [x] `AC5` **DONE for the 24 classifier classes.** Bucket counts in the 2026-08-26 log:
      implements-as-claimed 5 · partially-implements 18 · undecidable/probe-only 1 ·
      mislabelled 0. ⚠ Overshadowed by a label-SET finding: 5 of the 24 classes are
      SPARTA-DEPRECATED techniques.
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

### 2026-08-25 · AC2/AC5 scope decision + `audit_script_vs_stix.py` + DE-0003 verdicts

**Scope, decided with the owner:** the behavioural review (`AC2`/`AC5`) runs on the **24
classifier classes plus the mechanically-flagged script first**, then the remaining ~133 in a
later pass. Rationale: a mislabel only corrupts training if the mislabelled technique is a
**class**, and Sprint 29's retrain is what this gates. The full 157 is not abandoned — it is
phase 2. This is a deliberate, recorded narrowing, not a silent one.

**Tooling:** `components/onair/training/audit_script_vs_stix.py` — the behavioural companion
to the mechanical `map_scripts_to_stix.py`. It prints each technique's STIX definition beside
what its script actually sends (MIDs, raw hex, every `_send` action label), so the verdict is
assembled from evidence rather than a one-off read. The verdict itself is judgement and lives
here. **Mechanical baseline unchanged:** 158/159 claims resolve, 1 `NO-CLAIM`
(`demo_gnc_kill_chain.py`, legitimately claims none), 3 title mismatches (all phrasing).

**Verdicts — DE-0003 obfuscation family (7 classes).** ⚠ A systematic finding: **all seven are
`partially-implements`**, and in the *same* way. Each SPARTA technique is defined as
*obfuscation* — zero/freeze/forge a counter, prune a log, bias a clock **to hide activity** —
but every script only **probes** the target (a NOOP, or a RESET that zeroes a counter). None
implements the concealment the definition is about.

| class | STIX is about… | script does… | verdict |
|---|---|---|---|
| DE-0003.01 | masking the vehicle command counter | `CFE_ES NOOP` then `RESET` (zeroes it) | partial — zeroes, does not forge/freeze |
| DE-0003.02 | hiding rejected-command counts | bogus-FC then `CFE_ES RESET` | partial — zeroes, does not suppress increments |
| DE-0003.03 | receiver on/off "quiet windows" | `CI NOOP` (probe only) | partial — probes, never toggles a receiver |
| DE-0003.06 | thinning/rerouting downlink telemetry | `TO`/`EVS NOOP` (probe only) | partial — probes, never changes a downlink mode |
| DE-0003.08 | editing/pruning command history | `EVS NOOP` + `RESET_COUNTERS` | partial — clears counters, does not edit history |
| DE-0003.09 | biasing the clock to shift the timeline | `CFE_TIME NOOP` (probe only) | partial — probes, never sets the clock |
| DE-0003.10 | detecting GPS-ephemeris spoofing | `NOVATEL NOOP` (probe only) | partial — probes, never spoofs ephemeris |

⚠ **Why this matters for the labels, and it is not simply "the scripts are wrong".** These seven
are the classifier's DE-0003 classes. Their on-board footprint is a counter reset or a probe —
which is real telemetry and separable — so the *class* is learnable, but the label
**overstates what was demonstrated**: the model learns "someone reset ES counters", not "someone
concealed activity". Consistent with `V5_DETECTOR_COVERAGE.md` already tagging most of DE-0003
`OBFUSCATION` / out-of-scope. The honest fix is a label-name decision (call the class what the
script does), not a re-collection — carried to `AC5`'s bucket count and the retrain.

**Running verdict tally (7 of 24):** implements-as-claimed 0 · partially-implements 7 ·
mislabelled 0 · undecidable 0. ⚠ Do not extrapolate — the DE-0003 family shares a design and
may be unrepresentative; the EX/IMP classes are next.

### 2026-08-26 · AC2/AC5 verdicts — 24 classifier classes; two findings dominate the buckets

Full evidence via `audit_script_vs_stix.py` (STIX definition vs actual `_send` actions).

⚠ **Tool bug found and fixed mid-review.** The action extractor's regex stopped at the first
`{` in an f-string label, so it silently dropped `f"CFE_TBL LOAD {self.filename}"` and
`ACTIVATE` — the exact actions that distinguish the EX-0012.03/04/05 cluster. Had I rendered
verdicts on the truncated output I would have called all three "NOOP+RESET only". Fixed to
match f-string labels whole; committed. **Lesson: a parsing tool that silently under-reports
is worse than no tool — verify it captures the discriminating field before trusting a
negative.**

**Per-class verdicts:**

| class | STIX intent | script actually does | verdict |
|---|---|---|---|
| DE-0003.01 | mask vehicle command counter | NOOP + ES RESET (zeroes it) | partial |
| DE-0003.02 | hide rejected-cmd counts | bogus-FC + ES RESET | partial |
| DE-0003.03 | receiver on/off quiet windows | CI NOOP (probe) | partial |
| DE-0003.06 | thin/reroute downlink | TO/EVS NOOP (probe) | partial |
| DE-0003.08 | edit command history | EVS NOOP + RESET_COUNTERS | partial |
| DE-0003.09 | bias clock to shift timeline | CFE_TIME NOOP (probe) | partial |
| DE-0003.10 | detect GPS-ephemeris spoof | NOVATEL NOOP (probe) | partial |
| EX-0012.03 | raw memory write | CFE_TBL LOAD/ACTIVATE `CFE_TBL.SPARE0` (missing file) | partial |
| EX-0012.04 | subscriber-table remap | CFE_TBL LOAD/ACTIVATE `SC.RTS_TBL001` (missing file) | partial |
| EX-0012.05 | scheduler-param edit | CFE_TBL LOAD/ACTIVATE `SCH.SCHED_DEF` (missing file) | partial |
| EX-0012.07 | edit propulsion params | THRUSTER ENABLE/DISABLE (device toggle) | partial |
| EX-0012.08 | edit ADCS gains/masks | ADCS SET_MODE (mode force) | partial |
| **EX-0012.09** | edit EPS config | **EPS SWITCH toggle** — a real config/state change | **implements** |
| **EX-0012.12** | modify clock services | **CFE_TIME SET_TIME** | **implements** |
| EX-0014.01 | *spoof* time (external vector) | CFE_TIME SET_TIME — byte-identical to EX-0012.12 | partial (dup) |
| EX-0014.03 | inject false *sensor data* | CSS/FSS/IMU/MAG/ST DISABLE/ENABLE — denial, not spoof | partial |
| EX-0014.04 | *spoof* GNSS/PNT | NOVATEL DISABLE/ENABLE — denial, not spoof | partial |
| EX-0008.01 | absolute-time *time-bomb* | SC START_ATS/STOP_ATS (trigger existing) | partial |
| EX-0008.02 | relative-time *time-bomb* | SC ENABLE/START_RTS (trigger existing) | partial |
| **IMP-0002** | disruption | TO ENABLE_OUTPUT→attacker + EVS burst | **implements** ⚠dep |
| **IMP-0003** | denial | EVS NOOP flood | **implements** ⚠dep |
| **IMP-0006** | theft | TO ENABLE_OUTPUT→attacker (redirect tlm) | **implements** ⚠dep |
| IMP-0001 | deception | EPS switch + manufactured EVS event | partial ⚠dep |
| IMP-0005 | destruction | **explicit NOOPs only** ("NOT actually destroying") | undecidable ⚠dep |

**Buckets:** implements-as-claimed **5** · partially-implements **18** · undecidable/probe-only
**1** · mislabelled **0** = 24.

**Two findings dominate, and neither is per-script:**

1. ⚠ **5 of 24 classes are SPARTA-DEPRECATED techniques.** Every IMP class (IMP-0001/2/3/5/6)
   is `[DEPRECATED]` in STIX v4.0 — SPARTA retired the whole `IMP` "Impact" family and
   replaced the survivors with `IMP-0007` Native Functionality Abuse, `IMP-0008` State/Mode
   Manipulation, `IMP-0009` Configuration Manipulation. The classifier is being trained to
   name techniques that no longer exist. **This is the single highest-value label-set finding
   in the ticket** and feeds AINOS3-101 directly: those five classes need remapping to their
   v4.0 successors or removal, not re-collection.
2. ⚠ **The "intent vs observable" gap explains 18 of the 24 partials.** The SPARTA definitions
   describe adversary *intent* — conceal, spoof, plant a time-bomb — while the scripts
   demonstrate the *observable command path* — reset a counter, disable a sensor, trigger a
   sequence. The class labels overstate what the telemetry shows. This is **not** "the scripts
   are broken": the on-board footprint is real and (mostly) separable; the label just claims
   more than the frame proves. The honest fix is a **label-naming pass** (name each class for
   what is demonstrable), decided in AINOS3-101 — not a re-collection.

**`AC6` corroborated behaviourally.** EX-0012.{03,04,05} target genuinely different tables
(`SPARE0` / `RTS_TBL001` / `SCHED_DEF`) but via one identical command (`CFE_TBL LOAD` of a
non-existent file → identical failed-load footprint). Distinct techniques, telemetry-identical
mechanism → the fix is observability, not collapsing the taxonomy. And EX-0014.01 ≡ EX-0012.12
is confirmed at the byte level (both are `SET_TIME`), so that pair *is* collapsible.

⚠ **`AC4` still open** — the STIX-as-build-source decision. Now better-informed: STIX is
authoritative enough to have caught 5 deprecated classes and 18 intent/observable gaps, which
argues *for* using it as the label authority — but it defines intent, not footprint, so it
cannot be the sole source for a *telemetry* classifier's class names. That tension is the
decision AC4 has to record. Deferred to a focused pass.
