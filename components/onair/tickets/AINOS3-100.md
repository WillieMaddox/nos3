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

### 2026-09-12 · ⚠ INERTIAL slice BLOCKED — the star tracker is locked inside the Earth cone

The INERTIAL arm does not work, and the reason is now measured rather than guessed. **All 19
runs of the first attempt, and 7/7 of the second, were rejected by the capture gate.**

## First attempt — my omission

`inertial_capture.py` existed, the ~35 min exclusion-window bootstrap was documented, and the
docstring told callers to verify capture — **but the scenario never waited**. It damped,
commanded the orbit-normal target, entered INERTIAL and started its timed window immediately.
Capture 0–49.8 %; every run reported `exit 0`. Only the corpus manifest's capture gate caught
it. Fixed: `single_mode_hold_INERTIAL` now blocks on sustained `qValid` **and** varying
`ADCS_AC.Inertial.*`, 30 s poll, 45 min ceiling.

## Second attempt — the real mechanism

With the wait in place, runs cost **~62 min each** and still yielded **0 accepted of 7**. Four
logged `CAPTURED` (0.6–31.1 min) but capture was never *sustained*: 9.8 %, 11.9 %, 33.6 %.

Ruled out by measurement, not argument:

| candidate | evidence |
|---|---|
| damping failure | ✗ timed-out runs damped fine, \|w\| 0.08–0.10 deg/s |
| Sun exclusion | ✗ boresight-to-Sun stayed 40–107 deg, never inside the 30 deg cone |
| orbit phase / bad luck | ✗ one run held `qValid = 0` across **40,854 frames — over a full orbit**, ST enabled and `DeviceCount` incrementing throughout |
| my geometry model | ✗ live probe reads boresight-nadir **58.4 deg** vs threshold **80.4 deg** and 42 independently reports `Valid = 0` — the model agrees with 42 exactly |

**The boresight is LOCKED, not sweeping.** Probed live every 2 min:

```
simUTC        |w|     bore-nadir  limb+10   bore-sun   42 Valid
19:17.09     0.057      58.36      80.35     62.50        0
21:19.29     0.140      58.00      80.36     56.63        0
23:20.99     0.057      58.86      80.38     52.11        0
25:22.49     0.128      59.15      80.42     47.62        0
```

Boresight-to-nadir moved **0.8 deg in 6 minutes**. An inertially-fixed vehicle would see nadir
sweep at the orbital rate — **3.9 deg/min, ~23 deg over that window**. Meanwhile
boresight-to-Sun moved **15 deg**, so the body *is* rotating: at close to orbit rate, in the
sense that holds nadir fixed in the body frame. A near-LVLH lock.

**Why the damp step causes it.** The orbital rate is **0.0649 deg/s**. For nadir to sweep the
body frame once per orbit the residual rate must be well BELOW that. Every rate the damp step
actually leaves is comparable to it:

| observed \|w\| | vs orbital rate |
|--:|--:|
| 0.115 | 1.77x |
| 0.097 | 1.49x |
| 0.089 | 1.38x |
| 0.048 | 0.75x |

`DETUMBLE_TARGET_DEG_S = 0.35` is **5.4x the orbital rate**. I set it at "the natural SUNSAFE
floor" without considering the rate it had to beat. To be inertially fixed to within 10 % the
target would need to be **< 0.0065 deg/s**, ~54x tighter — and the measured SUNSAFE floor is
0.05–0.14 deg/s, so **SUNSAFE cannot reach it**. Damping harder is not available.

⚠ **This is a catch-22 in the plant, not a tuning problem.** Escaping the lock needs attitude
control; INERTIAL attitude control is gated on `qValid`; `qValid` needs the star tracker out of
the Earth cone. The only actuator that works while blinded is SUNSAFE, and SUNSAFE is what
leaves the vehicle in the lock.

⚠ The 2026-09-10 manual capture (0.4–0.6 deg pointing, `qValid` 100 %, held) is **not
contradicted** — it reached INERTIAL from a *different* attitude/rate state, after the
intermittent-control episode had pumped rates to ~2 deg/s. Closed-loop INERTIAL is reachable;
it is not reachable **from the state the damp step leaves**, which is what a repeatable
collection protocol requires.

## Disposition

The INERTIAL slice is **not collectable** under the current protocol at any sane run budget.
Measured over a 7.8 min baseline (sim 19:17 -> 27:08), boresight-to-nadir drifts
**+0.108 deg/min** against the **3.9 deg/min** an inertially-fixed vehicle would see — a **36x**
shortfall. At that drift, clearing 59.2 deg -> 80.5 deg takes **196 min (3.3 h) per run**, i.e.
**~62 h for 19 runs**, and only if the drift stays linear and the lock breaks at all.

**The SUNSAFE arm is unaffected and complete** (95 runs, 19 techniques x 5 instances, AC1
97.0 %) — that is the trainable corpus and `AINOS3-101` can proceed on it.

Carry to Sprint 30 as its own scoped problem — options, none of them free:

1. **Enter INERTIAL from a non-SUNSAFE state.** The lock is a property of what the damp leaves;
   a different entry state may not lock. Needs characterisation, not a guess.
2. **Re-mount the star tracker in `SC_NOS3.txt`** (boresight axis, or Earth exclusion angle).
   Cheapest and most reliable, but it changes the simulated plant — every prior ST-related
   result would need its provenance noted.
3. **Accept SUNSAFE-only coverage** and record INERTIAL as structurally uncollectable on this
   vehicle configuration, which is itself a defensible finding for the coverage doc.
