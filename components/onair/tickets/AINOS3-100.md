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

- [x] `AC1` Classified attack set recollected under `single_mode_hold_<MODE>`; alert-eligible attack frame fraction reported against the 84.4 % pilot figure.
- [x] `AC2` A **corpus manifest** is produced — scenario, date, schema sha256, FSW build, per-run technique and mode, frame counts. Its absence is what made four `AINOS3-80` metrics `[unverifiable]`.
- [x] `AC3` Labels verified against `AINOS3-96`; schema settled per `AINOS3-124`; instance count justified by `AINOS3-99` — which recommends **5 instances** (up from 3). ⚠ `AINOS3-99` also found the per-instance F1 spread is **not** blind-window-driven (77.4 % vs 77.7 % blind-frame fraction in zero-F1 vs good folds), so **the steady-flight protocol here fixes the blind window but does not, on its own, close the spread** — the spread is a footprint-reproducibility limit across runs. Collect the 5 instances for a fairer evaluation, not on the expectation that steady-flight alone tightens the folds.
- [x] `AC4` ⚠ Collected with the **star tracker enabled** if any INERTIAL data is included — `AINOS3-86` established that INERTIAL performed no closed-loop control without it.
- [x] `AC5` Operational discipline recorded: full `make stop` + `make launch-quiet` per run, chunks of ≤ 8 runs, never `nohup &`, parse with `csv.DictReader`.
- [x] `AC6` ⚠ **Consume the frozen label set** (`data/onair/models/label_set.json`, `AINOS3-122 AC6`): collect only the `confirmed` + `deferred` techniques, label each run by its `label_set.json` id, and do **not** re-mint `dropped` classes (the 5 IMP, `EX-0012.04 [prereq]`) or auto-generate `[prereq]` technique labels (run chain prereqs without emitting a distinct technique label — the `AINOS3-122 AC4` finding).
- [ ] `AC7` ⚠ **Balance the corpus across all four ADCS modes.** The original scope (`SUNSAFE x5 + INERTIAL x1`, no BDOT, no PASSIVE) rested on two premises that its own log then overturned: that an INERTIAL run costs ~17 min of exclusion-window wait (the 2026-09-12 fix reduced a run to **12 min**, so the cost argument for `INERTIAL x1` is gone), and that `AINOS3-99` showed "instances help the evaluation and extra MODES do not" — ⚠ a **misreading**: `AINOS3-99` is about *evaluation variance across folds*, and says nothing about *deployment mode coverage*. Collect **INERTIAL x4 more** (to 5 instances) and **BDOT x5** and **PASSIVE x5**, same 19 techniques, same frozen label set, same gates. ⚠ Both missing modes are live in the deployed router (`RoutingModeMap` covers all four), and on the v3 corpus BDOT is one of the two modes the classifier handles **best** (sub-technique accuracy on attack frames: BDOT 0.277, SUNSAFE 0.268, INERTIAL 0.169, PASSIVE 0.113) — so a corpus without BDOT trains away the model's strongest mode. ⚠ `build_corpus_batch.MIN_PER_RUN_INERTIAL_EXTRA = 17.0` is now stale and will over-plan INERTIAL; measured post-fix is ~0 extra.

  ⚠ **Collection is FOUR separate runs, one per mode, with a verify-gate after each
  (owner preference, 2026-09-20).** Run on the dual-output adapter (`AINOS3-126`); do not
  proceed to the next mode until the finished one verifies. Order is deliberate — the two
  proven-collectable modes go first so any surprise in the two never-collected ones surfaces
  with known-good examples in hand.

  | # | Mode | Runs | Verify before proceeding |
  |---|---|--:|---|
  | 1 | **SUNSAFE ×1** | 19 | `AINOS3-126 AC2` (`blend(raw) == native`) + `AC8` footprints. If it passes, **replace** one existing offline-blended SUNSAFE instance with this live one (keep SUNSAFE at 5 — do NOT add a 6th, which changes the LOIO fold count). If it fails, stop and fix the adapter. |
  | 2 | **INERTIAL ×4** | 72 | equivalence + footprints + capture gate. Sharpest equivalence test (existing ×1 offline-blended, new ×4 live). ⚠ 18 techniques/instance — `EX-0012.07` breaks the INERTIAL hold by physics and is gate-rejected. |
  | 3 | **BDOT ×5** | 95 | equivalence + footprints. First-ever `single_mode_hold_BDOT` collection. |
  | 4 | **PASSIVE ×5** | 95 | equivalence + footprints. First-ever `single_mode_hold_PASSIVE` collection. |

  **Total ≈ 281 runs, ~55 h** (BDOT/PASSIVE per-run time estimated as SUNSAFE-like, unmeasured).
  ⚠ Each mode is its own `run_corpus_chunks` invocation, so a pause between modes is free — the
  runner already resumes from `_remainder.json`.

  ⚠ **The kills are the harness watchdog, not the machine** (proven 2026-09-19: no cgroup cap, memory PSI 0.00, zero OOM/oomd kills, 381 GB free). The Sprint-29 collection hit them and survived only because `run_corpus_chunks` is resumable (`_remainder.json`, skips completed runs). Run the collection from a normal terminal — where there is no watchdog — and the kills do not occur at all.
- [ ] `AC9` ⚠ **Rejecting a run means moving its MANIFEST too, not just its CSV.**
      `loader.load_with_labels` never reads the collection's results files — it globs the CSV
      directory and labels rows from the manifests' scenario windows. So deleting a run's row
      from `<chunk>_results.json` removes it from the RESULTS while leaving its frames fully
      labelled and trainable. A re-run then ADDS a good run without removing the bad one, and
      nothing reports the duplicate.

      A rejected run has files in **three** places, all of which must move together:

      | location | files |
      |---|---|
      | `data/onair/csv/` | `csv_out_<ts>_pid<N>.csv` + `.meta.json`, and the five plugin side-files (`iforest_out_`, `attack_class_`, `rule_gate_out_`, `consistency_out_`, `staleness_out_`, `incident_`) |
      | `data/onair/csv_blended/` | the blended pair + its `.meta.json` |
      | `data/onair/scenarios/` | `manifest_<ts>Z.json` ⚠ **the one most easily missed, and the one that re-contaminates** |

      ⚠ Timestamps differ across the three — each plugin stamps its own init time, spanning
      ~1 s — so match on the second (`*<date>T<hh-mm-ss>*`), never on the full microsecond
      stamp. Quarantine to `data/onair/csv_rejected/` with a README stating the reason;
      do not delete, since a rejected run is often the only capture of the defect that
      rejected it.

      **Verify afterwards** that no CSV or manifest is left unreferenced by any results row.
- [x] `AC8` ⚠ **Verify attack FOOTPRINTS, not just attack exit codes, before any corpus is trained on.** `AC2`'s gate checks label, schema, sidecar, subprocess exit and controlled fraction — none of which confirm that the telemetry a technique is *supposed* to move actually moved. ⚠ A generic novel-value check cannot substitute: measured 2026-09-19, the three **probe-only** techniques (which by definition change no state) score 39/45/49 novel columns, squarely inside the range of real attacks, because free-running fields generate novel values continuously. Required: a **per-technique expected-footprint table** (field + direction), asserted per run, failing the run in `build_corpus_manifest.py` when the footprint is absent, and **back-filled across the existing `rebuild_2026-09-10` runs** so `AINOS3-101`'s results inherit verified rather than assumed provenance.

⚠ **Epoch/phase policy: collect at the DEFAULT, gate REMOVED 2026-09-21.**
`AINOS3-130` was parked without a usable answer — see that ticket. The short version:
`True Anomaly` in `cfg/build/InOut/Orb_LEO.txt` genuinely moves the start phase (verified
geometrically), and it does produce eclipse variation, but **capture time varies ~2.2x at a
FIXED phase** (225-498 s), so an 8-point 1-rep sweep could not separate a better phase from a
lucky draw. Resolving it needs many reps per phase, which costs more stack time than the
capture wait it would save. Collect at `True Anomaly = 0` / epoch `2025-10-20 17:43:20` and
revisit only if the INERTIAL wait becomes the binding constraint.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.

### 2026-09-10 · Scope set, tooling built, and a pilot that caught a corpus-killing defect

#### In plain terms

A pilot run caught a defect that would have ruined the entire collection. The batch asked every
attack script for "level 4", but the scripts accept different level ranges, so one attack never
ran — and the run still reported success and wrote a full-length data file. At full scale that
means ordinary data filed as attacks across 114 runs, with no way to tell afterwards short of
redoing everything. Fixed two independent ways: work out the correct level per script, and
reject any run whose attack actually failed.

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

#### ⚠ The pilot caught a defect that would have silently poisoned the whole corpus

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

#### Tooling built

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

#### Measured, for planning

- **End-to-end per run: 14.3 min** at pre=600/post=300 (40 archived 2026-08-15 manifests:
  12.4 min in-run + **2.0 min** stack restart).
- ⚠ **42 restarts from a FIXED epoch every launch** (`2025-293T17:43:3x`, confirmed on two
  independent launches). So the orbit phase at launch is deterministic and the INERTIAL
  exclusion window is a **repeatable offset**, not a random 0–35 min wait. The 17 min/run
  INERTIAL allowance is therefore an upper bound that characterisation should reduce.

### 2026-09-12 · ⚠ INERTIAL slice BLOCKED — the star tracker is locked inside the Earth cone

#### In plain terms

Twenty-six INERTIAL runs were rejected. The vehicle keeps settling into a slow rotation that
happens to hold the star tracker pointed at the Earth for hours at a time. The conclusion at this
point was that the mode could not be collected on any sensible time budget.

The INERTIAL arm does not work, and the reason is now measured rather than guessed. **All 19
runs of the first attempt, and 7/7 of the second, were rejected by the capture gate.**

#### First attempt — my omission

`inertial_capture.py` existed, the ~35 min exclusion-window bootstrap was documented, and the
docstring told callers to verify capture — **but the scenario never waited**. It damped,
commanded the orbit-normal target, entered INERTIAL and started its timed window immediately.
Capture 0–49.8 %; every run reported `exit 0`. Only the corpus manifest's capture gate caught
it. Fixed: `single_mode_hold_INERTIAL` now blocks on sustained `qValid` **and** varying
`ADCS_AC.Inertial.*`, 30 s poll, 45 min ceiling.

#### Second attempt — the real mechanism

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

#### Disposition

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

#### In plain terms

The previous entry is retracted. The step added to slow the vehicle down was itself the cause —
it parks the spacecraft at exactly the rotation rate that keeps the star tracker facing Earth.
Removing it lets the vehicle tumble through the good window, get a fix, and then settle itself.
Runs went from 62 minutes to 12. The entry lists five of its author's own earlier claims as
wrong, each from reading too much into too little data.

⚠ **My previous entry's disposition was wrong and is retracted.** The INERTIAL slice is not
"structurally uncollectable" and does not cost 29–62 h. A run now completes in **12 minutes**
and passes the capture gate.

**First INERTIAL run ever accepted:** `DE-0003.01`, capture **92.4 %**, AC1 alert-eligible
**100 %**, 4,000 frames, 719.6 s wall-clock.

#### The mechanism — three regimes, and the damp aims at the worst one

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

#### Corrections to the record

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

#### In plain terms

Finished: 113 runs, 413,000 frames. The last problem was measuring "was the vehicle under
control?" across the whole file — which also contains start-up and a deliberate tumble — instead
of across the stretch the run actually declares as its sample. Correcting the stretch, rather
than lowering the standard, put all 18 INERTIAL runs at 100 percent. One real exception: the
thruster attack spins the vehicle hard enough to break the hold by physics, which is that
attack's own signature rather than a fault. The intermittent job kills were never explained —
four theories were tested and all were wrong.

**113 accepted runs · 413,472 frames · 19 techniques.** SUNSAFE 95 (19 x 5 instances),
INERTIAL 18, AC1 alert-eligible 97.2 %.

#### The capture gate was measuring the wrong span

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

#### The one genuine holdout

`EX-0012.07` (propulsion) at **77.2 %** is a real result, not a defect. The attack fires
thrusters and spins the vehicle to ~141 deg/s, which breaks the INERTIAL hold by physics — that
is the technique's own footprint. It is the only one of the 19 whose attack destabilises the
attitude it was flying. Recorded as a finding rather than retried: a controlled INERTIAL hold
through a thruster burn is not a thing the vehicle can do.

#### Corrections

The harness kills that punctuated this collection were **not** explained by any of my four
successive theories — manifest memory use, environmental exhaustion, the detached launch, or
commit-limit exhaustion. The last of those was a real measured defect (`Committed_AS` exceeded
`CommitLimit`; raising `vm.overcommit_ratio` 50 -> 90 took headroom from -0.9 GB to +206 GB) and
worth fixing on its own terms, but it did not stop the kills either. I never found their cause.

### 2026-09-19 · ⚠ CORRECTION — the commit-limit "defect" was not one, and the gate never checked footprints

Two corrections to entries above, both raised on owner review.

#### In plain terms

Two things recorded in this ticket turn out to be wrong. The memory setting that was changed
was never actually in force on this machine, so calling it a defect and "fixing" it was a
non-event — which is why it changed nothing. And the collection checked that each attack
*ran*, but never that the telemetry it was supposed to move actually moved, so the corpus was
trained on without that ever being confirmed.

#### 1. `vm.overcommit_ratio` — a knob that was not connected to anything

The 2026-09-13 entry calls commit-limit exhaustion "a real measured defect … worth fixing on
its own terms". ⚠ **It was not a defect.** This machine runs `vm.overcommit_memory = 0`
(heuristic overcommit). `CommitLimit` is only *enforced* under mode **2** (strict); in mode 0
the kernel ignores it entirely and applies a per-allocation heuristic. `Committed_AS`
exceeding `CommitLimit` is therefore a normal reading on this system, not an error state, and
raising the ratio 50 → 90 moved a number nothing consults.

That fully explains why the change did not stop the kills: it could not have. The theory was
not merely unproven, it was inapplicable. **Reverted to 50 on 2026-09-19** at the owner's
direction — the machine is shared across projects and a system-wide setting should not be
carried for a benefit that does not exist.

⚠ Independent confirmation from `AINOS3-101`: every kill during that retrain occurred with the
ratio already at 90, ~5 GB resident, 435 GB free and no cgroup limit — including one that
killed a wrapper whose only work was a `sleep 60` loop. The cause remains unknown, and the
durable mitigation is checkpointing, not system tuning.

#### 2. ⚠ `AC2`'s gate never verified attack FOOTPRINTS — only that the attack ran

The manifest gate rejects on wrong/dropped label, schema mismatch, missing sidecar, failed
attack subprocess, and low controlled fraction. **None of those checks that the telemetry a
technique is supposed to move actually moved.** The corpus was handed to `AINOS3-101` and
trained on with that unverified.

A novel-value check run on 2026-09-19 across all 18 accepted INERTIAL runs finds every
technique does change *something* in-window (38–78 columns), so the catastrophic case — an
attack that never fired, the very defect the 2026-09-10 pilot caught — is ruled out. ⚠ But the
check cannot do more than that, and its own control proves why: the three **probe-only**
techniques, which by definition change no state, score **39 / 45 / 49** novel columns, squarely
inside the range of the real attacks. Free-running fields (GPS position, scheduler counters)
generate novel values continuously, so column novelty cannot distinguish a real footprint from
background churn.

A real check needs a **per-technique expected-footprint assertion** — which field, which
direction — and that knowledge currently lives in the rule-gate rules and
`V5_DETECTOR_COVERAGE.md`, neither of which the collector consults.

**Owner direction (2026-09-19): footprint verification is required before any future corpus is
trained on.** That is new tooling and a new acceptance gate, so it needs its own Jira key
rather than reopening this ticket — recorded here as the origin. Scope: assert each run's
expected footprint from a per-technique table, fail the run in `build_corpus_manifest.py` when
it is absent, and back-fill the check across the `rebuild_2026-09-10` corpus so the
`AINOS3-101` results inherit a verified provenance rather than an assumed one.

### 2026-09-22 · AC7 + AC8 DONE — 76 runs collected, footprints asserted

#### In plain terms

The corpus is collected: every attack in all four flight modes, on the coherent log format,
with a real timestamp on every row. A new check confirms each attack actually moved the
telemetry it was supposed to, rather than merely exiting cleanly — the gap that let the
previous corpus be trained on without anyone knowing whether the attacks did anything.

**`AC7` — 76 runs, 19 techniques x 4 modes, 13.7 h.** Instance-major ordering, one chunk per
technique holding all four modes. Every run: 472 columns, `OnAIR.FrameRecvUTC` on 100 % of
rows, attack window located in telemetry, mode held pre-attack, and
`deinterleave_csv(raw) == native blend` **76/76**.

**`AC8` — `components/onair/attack_footprints.json` + `training/check_footprints.py`.**
19 techniques, each anchored on the command its script SENDS, not on what the corpus shows;
deriving the expectation from the data it validates would be circular, and
`AINOS3-100`'s own 2026-09-19 measurement ruled out a generic novel-value check (the three
probe-only techniques scored 39/45/49 novel columns, inside the range of real attacks).
Result: **75/76 runs corroborate their expected footprint.**

#### ⚠ Three findings from building it, each worth more than the gate

1. **A sampling-rate blind spot.** `DE-0003.01` does NOOP+RESET in **0.7 s** against a ~4 s HK
   cadence, so `CFE_ES.CommandCounter` is flat 0 across all 2,804 frames of the run. That is
   the technique SUCCEEDING — hiding the command is its entire premise — not a failed attack.
2. **A reset is evidence, and an `increase` test can never see it.** `DE-0003.08` drives
   `CFE_EVS_HK.MessageSendCounter` **192 -> 0 -> 2,3,4,5…**. The window max never exceeds the
   baseline max, because destroying that history IS the technique. Assert `reset`.
3. **The gate has a floor** — ⚠ but NOT the one first recorded here. `EX-0012.04` misses its
   footprint in INERTIAL, and the 2026-09-22 entry explained that as an HK-cadence coin flip
   (3.7 s burst vs ~4 s CFE_TBL HK). **REFUTED by instance 2** (2026-09-23): the cell fails
   **2/2** in INERTIAL and passes **6/6** elsewhere, while siblings `EX-0012.03`/`.05` — same
   HK packet, same LOAD+ACTIVATE+RESET — pass **8/8**, including later in the run than `.04`.
   Ruled out: differing commands (attack logs byte-identical), an RTS lock (`NumRtsActive=0`
   in all 8), frozen HK (staleness: 0 stale frames in 5,740). ⚠ **Mechanism UNKNOWN**; needs
   the EVS message text, which `ExcludeColumns` prunes, so it needs a live reproduction.
   ⚠ The general lesson still stands: **a footprint miss means "not corroborated in
   telemetry", NOT "the attack did not run"** — those runs are valid (exit 0, EVS stepped,
   frames correctly labelled).

⚠ `CI.usCmdCnt` and `TO.usCmdCnt` are near-dead (1 change in 2,610 frames) — do not assert on
them; see `AINOS3-72` on the lab-vs-full app re-point.

#### Cells the gates reject, all understood

| cell | gate | why |
|---|---|---|
| `EX-0012.07` / INERTIAL | capture 33 % | thruster burn breaks the star-tracker lock — the technique's own footprint |
| `EX-0014.03` / INERTIAL | capture 71 % | IMU disabled -> attitude solution degrades -> `qValid` follows |
| `EX-0012.04` / INERTIAL | footprint | the sampling floor above; the run itself is sound |

#### One run rejected and quarantined

`EX-0014.03`/SUNSAFE, re-run: an ADCS app counter reset (`ADCS_HK.CommandCount` 236 -> 0, no
processor reset, 26 apps and 38 tasks throughout) left 22 of 891 pre-attack frames reading
`Mode = PASSIVE`. Seen **once in 76 runs**. Quarantined to `data/onair/csv_rejected/` with its
manifest — see `AC9`.

#### Tooling

- `training/merge_chunk_results.py` — joins the 19 chunk results for
  `build_corpus_manifest.py --batch-results`, excluding `*_remainder_results.json` and
  refusing duplicate cells. ⚠ A completed resume leaves its remainder file on disk, and
  globbing `*_results.json` counts those runs twice (observed: 77 runs for a 76-run corpus).
- `training/verify_corpus_chunk.py` — per-run structural checks as chunks land.
- `training/check_footprints.py` — the `AC8` assertion, non-zero exit on any miss.
