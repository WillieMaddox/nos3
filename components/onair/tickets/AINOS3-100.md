---
key: AINOS3-100
slug: corpus-rebuild-steadyflight
type: Story
epic: AINOS3-98 (corpus-integrity)
status: In Progress
priority: High
opened: 2026-08-23
sprints: [28, 29]
---

# AINOS3-100 — Recollect the classified attack set under the steady-flight protocol

**Summary:** Recollect the classified attack set under the steady-flight protocol, replacing the AINOS3-45 collection whose mode cycling put 83 % of attack frames inside the detector's blind window.

## Description

This ticket exists because `AINOS3-45` (`AINOS3-45`, *"4th corpus instance"*) was
scoped against the collection protocol found defective in Sprint 27 — mode cycling every 60 s
against a ~45 s detector warmup, leaving **83 % of attack frames inside the blind window**.
Executing it as written would have added a fourth LOIO fold built from unusable data, which is
worse than not collecting at all, because the tier rule takes the **minimum** across folds.

`AINOS3-45` was closed as superseded rather than re-scoped, per the crosswalk's immutability
rule; the binding decision is recorded there.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Classified attack set recollected under `single_mode_hold_<MODE>`; alert-eligible attack frame fraction reported against the 84.4 % pilot figure.
- [ ] `AC2` A **corpus manifest** is produced — scenario, date, schema sha256, FSW build, per-run technique and mode, frame counts. Its absence is what made four `AINOS3-80` metrics `[unverifiable]`.
- [ ] `AC3` Labels verified against `AINOS3-96`; schema settled per `AINOS3-124`; instance count justified by `AINOS3-99` — which recommends **5 instances** (up from 3). ⚠ `AINOS3-99` also found the per-instance F1 spread is **not** blind-window-driven (77.4 % vs 77.7 % blind-frame fraction in zero-F1 vs good folds), so **the steady-flight protocol here fixes the blind window but does not, on its own, close the spread** — the spread is a footprint-reproducibility limit across runs. Collect the 5 instances for a fairer evaluation, not on the expectation that steady-flight alone tightens the folds.
- [ ] `AC4` ⚠ Collected with the **star tracker enabled** if any INERTIAL data is included — `AINOS3-86` established that INERTIAL performed no closed-loop control without it.
- [ ] `AC5` Operational discipline recorded: full `make stop` + `make launch-quiet` per run, chunks of ≤ 8 runs, never `nohup &`, parse with `csv.DictReader`.
- [ ] `AC6` ⚠ **Consume the frozen label set** (`data/onair/models/label_set.json`, `AINOS3-122 AC6`): collect only the `confirmed` + `deferred` techniques, label each run by its `label_set.json` id, and do **not** re-mint `dropped` classes (the 5 IMP, `EX-0012.04 [prereq]`) or auto-generate `[prereq]` technique labels (run chain prereqs without emitting a distinct technique label — the `AINOS3-122 AC4` finding).

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.

### 2026-09-10 · Scope set, tooling built, and a pilot that caught a corpus-killing defect

**Scope (owner decision): SUNSAFE x5 + INERTIAL x1 = 114 runs, est. 35.8 h.**

19 techniques, generated from the frozen label set: 13 `confirmed` attacks + 6 `deferred`.
`nominal` is not emitted (it comes from every run's pre-attack window) and the 6 `dropped`
classes cannot be emitted at all. Windows pre 240 s / post 300 s. Cost model is per-entry
(`pre + attack + catalog dwell + post + 2 min restart`), not a flat rate, so the estimate moves
with the windows rather than hiding them.

⚠ The INERTIAL slice is 1 instance rather than 5 because an INERTIAL run costs several times
more (`AINOS3-86` exclusion-window wait). It is a **characterisation slice** exercising the
closed-loop path on real attacks, not a training-depth slice. Depth stays in SUNSAFE, which is
the right lever: `AINOS3-99` found the fold spread is a footprint-reproducibility limit, so
INSTANCES help the evaluation and extra MODES do not.

## ⚠ The pilot caught a defect that would have silently poisoned the whole corpus

The first pilot run hardcoded `level: 4` for every attack. **The scripts do not share a level
range** — variously `[1]`, `[1,2]`, `[1,2,3]`, `[1,2,3,4]` — so `de_0003_01` exited with
`argparse: invalid choice: 4`.

**The run still looked completely healthy.** The surrounding scenario blocks ran to completion,
a full-length 2,247-frame CSV was written, and `run_attack.py` returned **exit 0**. The batch
runner recorded `exit_code: 0`. Nothing in the run's own output said the attack never fired.
At batch scale that produces **nominal frames labelled as attacks across 114 runs** — the worst
possible corpus defect, and undetectable after the fact without re-running everything.

Two independent fixes, because one was not enough:

1. **Prevention** — `build_corpus_batch.py` now derives the level per script by reading its
   own `--attack-level` choices and taking the maximum (`L2 x7, L3 x2, L4 x10` scripts). An
   explicit `--level` is validated against each script and refused if out of range.
2. **Detection** — `build_corpus_manifest.py` reads each run manifest's **per-attack**
   `exit_code` and rejects the run. Verified against the real failed pilot:
   `attack subprocess FAILED (exit 2) — no attack in this CSV`. ⚠ The run-level exit code is
   **not** sufficient; only the manifest's attack record reveals this.

## Tooling built

- **`scenarios/build_corpus_batch.py`** — generates the batch **from
  `label_set.json`** (`AC6` by construction: dropped classes filtered and the filter asserted;
  `[prereq]` ids never emitted as techniques). Per-mode instance counts
  (`--modes SUNSAFE:5 INERTIAL:1`), per-script level resolution, and a wall-clock estimate.
- **`training/build_corpus_manifest.py`** — the `AC2` deliverable. Per run: technique, mode,
  instance, scenario, attack window, CSV, frame count. Pins the frozen
  `recorded_schema_sha256` (`AINOS3-124`), FSW build sha, and git rev. **Rejects** rather than
  annotates: wrong/dropped label, schema mismatch against the freeze, missing sidecar, failed
  attack, and — for INERTIAL — a controlled fraction below 90 % (`AINOS3-86`: a run reporting
  `ST.DeviceEnabled=1` may have been in free drift throughout). All rejection paths tested.
- **`scenarios/run_attack_batch.py`** — now carries `_technique`/`_mode`/`_rep` and the
  produced **CSV name** through to its results. Without those a result row cannot be traced
  back to its frames, which is exactly what made four `AINOS3-80` metrics unverifiable.
- Batch + 15 chunks of <= 8 runs (`AC5`) under `data/onair/corpus/rebuild_2026-09-10/`,
  SUNSAFE and INERTIAL chunked separately so the INERTIAL block can be gated on capture.

## Measured, for planning

- **End-to-end per run: 14.3 min** at pre=600/post=300 (40 archived 2026-08-15 manifests:
  12.4 min in-run + **2.0 min** stack restart).
- ⚠ **42 restarts from a FIXED epoch every launch** (`2025-293T17:43:3x`, confirmed on two
  independent launches). So the orbit phase at launch is deterministic and the INERTIAL
  exclusion window is a **repeatable offset**, not a random 0–35 min wait. The 17 min/run
  INERTIAL allowance is therefore an upper bound that characterisation should reduce.
