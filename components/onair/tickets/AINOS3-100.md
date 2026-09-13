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

⚠ **Corrected on a longer baseline.** A 9-sample, 16.3-minute least-squares fit supersedes the
first 4-point estimate — that baseline was too short and its slope too noisy:

| quantity | slope | note |
|---|--:|---|
| boresight → nadir | **+0.239 deg/min** | vs **3.9** if inertially fixed — **16x** short |
| boresight → Sun | **-1.876 deg/min** | sweeping ~8x faster than nadir |
| Earth threshold | +0.031 deg/min | orbit radius drifting |

So the Earth cone would clear in **~91 min**, not the 196 min the short baseline implied. But
⚠ **the Sun cone arrives first**: boresight-to-Sun was 32.8 deg and closing at 1.9 deg/min,
crossing the 30 deg exclusion within ~1 minute. The tracker goes **sun-blind before it clears
the Earth cone**, and with the Sun sweeping at 1.9 deg/min it cycles in and out on a ~3.2 h
period. A usable window needs BOTH cones clear simultaneously, which is far rarer than either
alone.

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
On the corrected 9-sample fit the Earth cone alone clears in **~91 min per run** (~29 h for 19
runs), but that is a floor rather than an estimate: the Sun cone must be clear at the same
moment, and it cycles on a ~3.2 h period, so the true per-run wait is longer and not reliably
bounded. Either way the slice is not collectable at a sane budget.

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

### 2026-09-12 · ✅ SOLVED — the damping step was the cause; removing it makes INERTIAL collectable

⚠ **My previous entry's disposition was wrong and is retracted.** The INERTIAL slice is not
"structurally uncollectable" and does not cost 29–62 h. A run now completes in **12 minutes**
and passes the capture gate.

**First INERTIAL run ever accepted:** `DE-0003.01`, capture **92.4 %**, AC1 alert-eligible
**100 %**, 4,000 frames, 719.6 s wall-clock.

## The mechanism — three regimes, and the damp aims at the worst one

| body rate | behaviour |
|---|---|
| **~orbital rate (0.05–0.15 deg/s)** | near-LVLH lock: body rotation nearly cancels the orbital sweep, nadir crawls at **0.25 deg/min**, blind for hours ← **what damping produced** |
| **fast tumble (~2 deg/s)** | boresight sweeps through the cone in minutes, tracker validates, controller takes hold and damps ITSELF ← **what works** |
| truly inertial (< 0.0065 deg/s) | nadir sweeps at 3.9 deg/min, window inside ~40 min ← unreachable; SUNSAFE's measured floor is 0.05–0.14 deg/s |

`_detumble_before_inertial` was added to stop burst control "pumping" the rates (measured
0.64 → 2.31 deg/s in 60 s while blinded). **That pumping is the mechanism that achieves
capture, not a pathology.** Damping first parks the vehicle squarely in the resonance band.

Measured live 2026-09-12: entering INERTIAL while tumbling at ~1.95 deg/s, boresight-to-nadir
went **18.1 → 94.1 deg in five minutes** (~15 deg/min), cleared the 82.5 deg threshold, 42
reported `Valid=1`, the controller captured and then **damped itself to 0.229 deg/s** while
holding ~90 deg off nadir. Capture then held at `qValid` 100 % on re-check 5 min later.

**The fix is to REMOVE the step I added, not tune it.** `_detumble_before_inertial` is retained
but no longer called, with the full reasoning in its docstring — the wrong turn is more
instructive than the fix, and the control arm may still want it.

## Corrections to the record

Five successive claims of mine about this were wrong, each from extrapolating too little data:

1. "Sun cone arrives first" — a straight-line fit through a turning point. The Sun angle
   bottomed at 32.8 deg and reversed; it never entered the 30 deg cone.
2. "Locked, waiting cannot help" — the lock is real but conditional on low rates.
3. "3.3 h per run / 62 h for 19" then "91 min / 29 h" — both superseded; the real figure is
   **12 min per run**, ~4 h for 19.
4. "Not collectable at any sane budget" — retracted outright.

What survived every correction and is directly measured: the geometry model agrees with 42
exactly, the near-LVLH lock is real at low rates, and the damp target (0.35 deg/s, 5.4x the
0.0649 deg/s orbital rate) was chosen without reference to the rate it had to beat.

⚠ The capture gate is what made this findable. Every one of the 26 bad runs reported `exit 0`
and would have entered the corpus as controlled INERTIAL data.

### 2026-09-13 · ✅ CORPUS COMPLETE — 113 runs; the last gate failure was my window, not the data

**113 accepted runs · 413,472 frames · 19 techniques.** SUNSAFE 95 (19 x 5 instances),
INERTIAL 18, AC1 alert-eligible 97.2 %.

## The capture gate was measuring the wrong span

Five INERTIAL runs sat stubbornly at 67–70 % capture across three collection attempts. Profiling
`qValid` by decile showed why:

```
DE-0003.01   [  8,   0,  28,  61, 100, 100, 100, 100, 100, 100]
EX-0008.02   [  7,   0,  17,  61, 100, 100, 100, 100, 100, 100]
```

The first 3–4 deciles are **capture acquisition**, not the sample. OnAIR begins recording when
the stack launches, so a session CSV also holds FSW boot and — for INERTIAL — the 1–12 min the
vehicle spends deliberately tumbling toward a star-tracker window. Scoring capture over the
whole file rated those runs 67–70 % while **every frame of their declared sample, including all
attack frames, was 100 % controlled**.

⚠ Scoping to the scenario block was **not** enough and is worth recording: the block's
`start_utc` is stamped *before* the capture wait that runs inside it, so it still contains
acquisition. The fix anchors on the attack window — the one timestamp recorded exactly — and
takes `pre_seconds` before it through the end, which is precisely the span the run declares as
its sample.

⚠ **This narrows WHAT is measured, not the 90 % bar.** The threshold is untouched. The
distinction matters: all 18 accepted INERTIAL runs score **100.0 %** on the corrected span — they
are not marginal passes rescued by a redefinition.

Same class of error as the AC1 window bug earlier in this ticket: the number was right about
the wrong span. Twice now, so the lesson is worth stating plainly — **a metric over a session
CSV must declare which frames are the sample**, because the file is always larger than the run.

## The one genuine holdout

`EX-0012.07` (propulsion) at **77.2 %** is a real result, not a defect. The attack fires
thrusters and spins the vehicle to ~141 deg/s, which breaks the INERTIAL hold by physics — that
is the technique's own footprint. It is the only one of the 19 whose attack destabilises the
attitude it was flying. Recorded as a finding rather than retried: a controlled INERTIAL hold
through a thruster burn is not a thing the vehicle can do.

## Corrections

The harness kills that punctuated this collection were **not** explained by any of my four
successive theories — manifest memory use, environmental exhaustion, the detached launch, or
commit-limit exhaustion. The last of those was a real measured defect (`Committed_AS` exceeded
`CommitLimit`; raising `vm.overcommit_ratio` 50 -> 90 took headroom from -0.9 GB to +206 GB) and
worth fixing on its own terms, but it did not stop the kills either. I never found their cause.
