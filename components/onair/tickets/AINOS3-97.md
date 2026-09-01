---
key: AINOS3-97
slug: quarantine-stale-corpus
type: Task
epic: AINOS3-98 (corpus-integrity)
status: Open
priority: Medium
opened: 2026-08-11
sprints: [27, 28]
---

# AINOS3-97 — Separate live corpus data from superseded

**Summary:** As a maintainer, I want superseded corpus data quarantined out of the working set, because `data/onair/csv` holds **30 GB across 1,465 entries** mixing collections we still depend on with collections we know are invalid — and the mix invites scoring against bad data.

## Description

Several collections are known-superseded: the wave-1 attack runs whose
scripts had the four bug classes, the COSMOS-up sweep superseded by the mode-balanced
corpus, and everything collected under `scenario_all_modes_dwell` before the blind-window
defect was found (83 % of attack frames unusable).

⚠ **Dependency mapping comes first, and this is the whole risk.** `csv_corpus_v3stage` is
**frozen and still load-bearing** — the deployed classifier's LOIO, the cluster taxonomy,
the explanation catalog and the newly-derived `classifier_tiers.json` all trace to it.
Moving it would break four artifacts and silently invalidate the tier column we just fixed.
"Pre-correction" does **not** mean "safe to move".

Quarantine, not delete, at least initially: a sibling `data/onair/csv_stale/` with a README
per moved collection saying what it was, why it is superseded, and what (if anything) still
cites it. Deletion can follow once nothing references it for a sprint.

⚠ **Dependency mapping comes first, and it is the whole risk.** `csv_corpus_v3stage` is
frozen and **still load-bearing** — the deployed classifier's LOIO, `cluster_taxonomy.json`,
`explanation_catalog.json` and the newly-derived `classifier_tiers.json` all trace to it.
"Pre-correction" does **not** mean "safe to move". Quarantine, not delete.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Inventory of `data/onair/csv` by collection: date range, size, collecting scenario, and
      the defect (if any) that supersedes it.
- [ ] `AC2` **Artifact→corpus dependency map** produced *before* anything moves; every artifact in
      `data/onair/models/` traced to the corpus it was built from.
- [ ] `AC3` Superseded collections moved to `data/onair/csv_stale/` with a per-collection README.
- [ ] `AC4` Nothing that a live artifact depends on is moved — verified by regenerating at least one
      dependent artifact after the move and diffing to zero.
- [ ] `AC5` Space reclaimed recorded, and a note on whether deletion is now safe.
- [ ] `AC6` **Torn-read filter for training** (from AINOS3-118 slice 2). ⚠ Premise corrected by
      AINOS3-121: the position/MAG spoof misses are **not** caused by torn-read *desensitization* —
      the harness shows the deployed IF misses ANY single-subsystem spoof (0% in all four modes)
      because 1%-FP thresholds sit in the low tail of concentrated nominal distributions, so no
      small feature-subset can cross. A torn-read filter therefore **will not** make EX-0014.04
      detectable by the IF. It is still worth doing for a *different, confirmed* reason — torn
      NOVATEL reads false-positive rule-gate R15 (they survive its median-5 on long-uptime stacks) —
      so scope this AC to **de-noising the corpus for R15 + general data hygiene**, not as the fix
      for the PNT gap. The PNT/MAG/IMU gap fix is a per-subsystem detection primitive
      (`AINOS3-123`, under AINOS3-63 — re-homed from AINOS3-118 on 2026-08-29), not a training filter.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.

### 2026-08-26 · AC6 added — torn-read desensitization (origin: AINOS3-118 slice 2)

AINOS3-118's EX-0014.04 repair surfaced a corpus-integrity defect that belongs here: torn
NOVATEL reads scattered through the training corpus (row-level, not a whole superseded
collection) appear to teach the v5 IF that large ECEF/position deltas are normal, so a real PNT
position spoof is undetected (0 anomalies, static and ramping, in SUNSAFE). Filed as `AC6` — a
retrain-time row filter, distinct from the collection-level quarantine of AC1–AC5. See the
AINOS3-118 log + `project_ainos3_118_gps_spoof` for the validation detail.
