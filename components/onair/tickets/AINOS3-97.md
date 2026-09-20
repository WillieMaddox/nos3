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
- [x] `AC2` **Artifact→corpus dependency map** produced *before* anything moves; every artifact in
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

### 2026-09-01 · AC2 DONE — artifact→corpus dependency map built (gates AINOS3-122 AC7)

`data/onair/models/artifact_corpus_map.json` — all 55 artifacts traced, from provenance fields
where present and **through the producing scripts** where the artifact carries no corpus field
(`classifier_tiers.json` → `meta.cache` → OOF → corpus; `cluster_taxonomy.json` →
`source_classifier` + OOF; `incident_rescore*` → `oof_predictions` → OOF).

**Corpus → dependents:**

| corpus | # artifacts | move-safe? |
|---|--:|---|
| **`csv_corpus_v3stage`** (frozen, load-bearing) | 18 | ⛔ **do NOT move** — OOF caches, tiers, taxonomy, explanation, `label_set.json`, incident rescores, mode_aware, the AC7 staging set |
| NOMINAL soak (IF calibration + IF pkls) | 15 | separate lineage — the IF stack, not the attack corpus |
| `csv_ainos3_30` / `_s27` | 2 | ablations — known superseded, safe to quarantine |
| `csv_corpus_v3` (~v3stage lineage) | 5 | the classifier pkls |
| `?UNKNOWN` (eval artifacts) | 6 | low risk, but need a script-trace before deletion |

⚠ **The finding AC2 exists to surface: 11 artifacts carry NO recorded corpus provenance** — the 5
classifier pkls and 6 eval JSONs (`benchmark_fayyaz`, `permode_pilot*`, `roc_*`,
`steadyflight_replication`). Their corpus is inferred by script/convention, not stored in the
file, so a purely artifact-side map is impossible for them. This is *why* AC2 is "the whole risk":
you cannot safely quarantine 30 GB while a fifth of the model artifacts don't record what they
were built from. **Forward fix:** stamp a `corpus`/`corpus_sha256` field into every regeneration
output. **Immediate:** the 6 `?UNKNOWN` eval artifacts must be script-traced before AC3 moves
anything they might cite.

**AC3/AC4 (the actual quarantine) not started** — the map is the prerequisite and is now in hand.

### 2026-09-20 · AC1 partially done — 26.9 GB quarantined, and the schema survey that AC1 needs

#### In plain terms

Nearly 27 GB of telemetry that was recorded while the stack sat idle has been moved out of
the way so it cannot be picked up by a future collection or training run. Separately, a
survey found the logs are not one dataset at all — they span eleven different column
layouts — and a guard now stops them being silently mixed.

**Idle-logging quarantine → `data/onair/csv_idle_archive/`, 26.9 GB, 50 files.** Eight
sessions whose telemetry was recorded with the stack up and nothing being exercised.
Moved, not deleted; `README.md` and `archive_manifest.json` record what and why.

⚠ **Selection needed care in both directions.** Coverage was computed against the union of
all 1,243 scenario, attack AND **soak** windows — soak manifests key on
`started_utc`/`ended_utc` rather than `start`/`end`, and the first pass missed them, which
scored every deliberate soak at 0 % and would have archived `AINOS3-86`'s 86.9 h evidence.
Every candidate was also checked against `artifact_corpus_map.json`, the `AINOS3-100`
manifest, the `csv_corpus_v3stage` symlinks, and timestamp citations across tickets.

⚠ **Quarantine decisions are better made per FILE than per session.** The 2026-08-15 soak
is the case that proves it: its 6.3 GB telemetry log was archived (the star tracker was off,
so it never flew closed-loop INERTIAL, and its FP row was superseded on 2026-09-10), while
its 215 MB of side-files stayed — `AINOS3-90`'s 55.8 incidents/hour reads the 0.4 MB
incident file, not the telemetry.

**`AC1` inventory, partial — the corpus is ELEVEN schema generations, not one.** Of 487
telemetry logs only **148** are at `schema-v1` (470 columns); the rest span 250, 256, 359,
360, 396, 442, 451, 452, 455 and 479 columns.

⚠ **Nothing detected this.** `list_clean_csvs` checked byte-repr leaks and row alignment
*within* a file and never compared headers *between* files, and `load()` concatenates with
an outer join — so a bare load over `data/onair/csv` merged eleven generations and filled
the missing columns with zeros, silently. Fixed: the loader now keeps one schema, counts
and names what it skipped, and accepts an explicit `schema=` or `strict_schema=True`
(6 tests). Verified a no-op on every existing corpus view.

⚠ `csv_corpus_v3stage` is built entirely on 250-column files, so the generations cannot be
archived by width — `AINOS3-101`'s `AC3` control and `AINOS3-122`'s `AC7` both depend on
them. Quarantining by generation is still open work under `AC3`.

**Remaining:** `AC1` full inventory (date range, size, collecting scenario per collection),
`AC3`/`AC4`/`AC5` (the generation-level moves and their verification), `AC6` torn-read
filter.

