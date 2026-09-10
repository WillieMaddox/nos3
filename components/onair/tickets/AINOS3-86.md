---
key: AINOS3-86
slug: inertial-false-alarms
type: Story
epic: AINOS3-79 (detector-rigor)
status: Done
priority: High
opened: 2026-08-11
sprints: [27, 28, 29]
---

# AINOS3-86 — Bring INERTIAL's false-alarm rate into the design band

**Summary:** As an operator, I want INERTIAL's nominal false-alarm rate brought under the 1 % design target, because it currently measures **33.6 %** and that makes the mode unusable for detection and un-evaluatable for coverage.

## Description

An escalating history, each measurement larger than the last:

| measurement | conditions | nominal FP |
|---|---|--:|
| published | 35 K frames / 116 min | **0.00 %** |
| AINOS3-81 soak | 60 min hold | 0.54 % operational / **7.5 % raw** |
| steady-flight replication | 12 runs, 600 s hold | **33.6 %** (range 21.1–48.5 %) |

The settling-transient explanation offered for the 8-minute pilot runs is **refuted**: 10
minutes is not enough for the rate to subside, and it lands far above the 60-minute soak.
Every INERTIAL lift measurement sits on this noise floor, so the mode cannot currently be
evaluated for attack detection at all — which is why the replication's INERTIAL column was
discarded.

One contributing cause is known: the threshold is calibrated **in-sample** (AINOS3-80 **F1**)
— INERTIAL's threshold promised 1 % raw FP and the soak delivered 7.5 %. But that does not
explain 33.6 %, so there is a second factor. Candidates, in rough order of suspicion:

1. **Training gap.** INERTIAL has 19,641 training rows from a *single* 116-minute session.
   That may not cover the mode's normal operating range — the same root cause as BDOT's 296
   rows and the missing sun-acquisition examples.
2. **Missing target quaternion.** INERTIAL pointing takes a commanded attitude
   (`GENERIC_ADCS_INERTIAL_QUATERNION_CC`). Absent one, the controller may drive toward a
   default attitude with sustained large control effort — dynamics that legitimately look
   anomalous. None of our scenario tooling ever sends that command.
3. **Genuinely long settling.** The mode may need far more than 10 min, in which case the
   250-frame (~45 s) warmup is wrong for INERTIAL specifically.

⚠ **Do not fix by tightening the threshold alone.** The ROC sweep showed tightening
INERTIAL to a 0.1 % target drives its false alarms to 0.00 % but **collapses its attack
detection 60×** (12.4 % → 0.2 %). Any threshold change must be paired with an
attack-detection measurement.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` Root cause identified and (1)/(2)/(3) distinguished — e.g. a ≥ 2 h INERTIAL soak run twice,
      with and without a commanded target quaternion, reporting nominal FP against uptime.
- [x] `AC2` Fix applied to the cause, not the symptom: retrain/recalibrate on a proper INERTIAL
      baseline; or command a quaternion and fix the scenario tooling; or set an INERTIAL-specific
      warmup from the measured settling time.
- [x] `AC3` INERTIAL nominal FP under the 1 % design target, measured on **held-out** nominal.
- [x] `AC4` Re-soak to confirm; coverage doc updated with the measured value and its provenance tag.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.

### 2026-08-24 · ROOT CAUSE FOUND — none of the three candidates; INERTIAL never ran closed-loop

`AC1` answered, and the answer is outside the three hypotheses. `AC_inertial()` is gated on
`if (GNC->qValid)` (`components/generic_adcs/fsw/cfs/src/generic_adcs_adac.c:338`);
`GNC->qValid = AD->ST.Valid` (`:215`) traces to the **star tracker**, which boots DISABLED
and which no tooling ever enabled. `qValid` is 0 in every frame ever collected — 1.75 M rows,
May → August, including the frozen `csv_corpus_v3stage`.

Measured consequence in one session: `ADCS_GNC.Tcmd` **frozen at a single value for 1,789
INERTIAL frames** (97 distinct across 464 SUNSAFE frames), `qErr` identically zero, body
rates drifting freely. "Nominal INERTIAL" has been **uncontrolled tumble**, and the 33.6 %
false-alarm rate is the detector correctly flagging unconstrained dynamics.

Candidate (2) is refuted on its own terms: commanding the target quaternion changed nothing,
because the control law is gated on `qValid`, not on whether a target was set.

### 2026-08-24 · fix demonstrated on nominal — 0.13 % operational FP

`GENERIC_STAR_TRACKER_ENABLE_CC` → `ST_DEV.Q0` populated, `IsValid` → 1, `qValid` → 1,
`qErr` non-zero and varying, `Tcmd` unfrozen. 2 h soak, `arm: controlled-inertial`:

| condition | window | raw FP | operational FP |
|---|--:|--:|--:|
| ST off (drift), matched first 120 min | 39,301 frames | 12.05 % | 0.85 % |
| ST off, full 86.9 h | 1,742,104 frames | 5.58 % | 0.40 % |
| **ST on (closed-loop), 118 min** | 41,584 frames | **2.45 %** | **0.13 %** |

Raw FP 4.9× better, operational 6.5× better; no drift (Δ = −0.0034). The published 33.6 %
came from 12 runs at a **600 s hold** — entirely inside the acquisition transient the first
15-minute bin captures (raw 0.1222, collapsing to 0.0000 by T+30).

⚠ **`AC3` and `AC4` are NOT met.** Only the nominal side is measured. Per this ticket's own
warning, a change that suppresses alarms needs an attack-side check first — unmeasured here.
Scoped as a 12-run matched A/B against the existing `batch_steadyflight_replication`
INERTIAL arm: ~3.3 h unattended, ~2 h attended. Note the control arm has little detection to
lose (`EX-0012.07` +0.445 with spread `[-0.07, 0.67, 0.73]`; the other three ≤ +0.09).

Tooling added: `cmd.py` gains `st_enable()` and `adcs_set_inertial_quaternion()` (wire format
verified against `GENERIC_ADCS_CMD.txt` and the packed C struct); `soak_mode.py` gains
`--enable-star-tracker`, `--target-quaternion`, `--identity-quaternion` and records the arm
in its manifest.

**Also resolves `AINOS3-91`** — the corpus-wide inert `ST_DEV` fields have the same root cause.

### 2026-08-25 · PAUSED — attack-side A/B deferred, machine in use

`AC3` and `AC4` remain unmet and the fix stays **undeployed**. The blocker is not
technical: an unrelated benchmark is running on this machine, and bringing the NOS3 stack up
would perturb its wall-clock timings. Resume when the machine is free.

**What resuming looks like** — a 12-run matched A/B against the existing
`batch_steadyflight_replication` INERTIAL arm, which is the control because it ran the same
4 attacks × 3 reps with the star tracker **off**:

- ~3.3 h unattended (12 × 910 s + ~11 resets at ~55 s), ~2 h attended for analysis.
- Requires a tooling change first: `run_attack_batch.py` / `single_mode_hold_INERTIAL` do
  **not** enable the star tracker, so without it the "after" arm would silently reproduce the
  "before" condition. ~45 min including a dry-run.
- ⚠ Read the floor before reading the result. The control arm has little detection to lose —
  `EX-0012.07` mean lift +0.445 with spread `[-0.07, 0.67, 0.73]`; the other three ≤ +0.09. A
  loss is only measurable on `EX-0012.07`; for the rest the honest outcome is a null.
- The more interesting question is whether controlled INERTIAL **gains** detection, which the
  same 12 runs answer at no extra cost.

### 2026-08-25 · ⚠ Possible configuration artifact — read before any tuning (via AINOS3-95)

Found while validating the AINOS3-95 stage-2a subscription of `GENERIC_ADCS_AC_MID`
(`0x0944`), which carries the INERTIAL controller's own gains and error state. Full detail in
[`AINOS3-95`](AINOS3-95.md).

**This ticket's plan already requires enabling the star tracker.** What follows is the
*mechanism* for why, and it raises a prior question the plan does not ask.

`AC_inertial()` is wrapped in `if (GNC->qValid)` (`generic_adcs_adac.c:338`), so the chain is

`ST.DeviceEnabled=0` → `ADCS_DI.Payload.St.valid=0` → `ADCS_GNC.qValid=0` →
**the INERTIAL control law never executes at all.**

Measured on the deployed stack: 124 INERTIAL frames with the star tracker disabled, and every
one of `Inertial.therr / sumtherr / qErr / werr / Tcmd` constant zero. Enable the star tracker
and they come alive.

**⚠ The prior question.** If earlier INERTIAL soaks ran with `qValid = 0`, the vehicle was in
"INERTIAL mode" with **no control law running** — free drift, not a controlled inertial hold.
A **33.6 %** false-alarm rate against uncontrolled drift is very plausibly a **configuration
artifact rather than a detector problem**, and tuning a detector against it would be tuning
against a misconfigured plant.

**And enabling the star tracker is necessary but not sufficient.** With it enabled and the
control law running, the controller **does not converge**:

| quantity | behaviour over the run |
|---|---|
| `\|therr\|` | 1.9944 → 1.9978 — pinned near maximum, not decreasing |
| `qErr[3]` | +0.0749 → +0.0402 — error angle *growing* toward 180° |
| `\|sumtherr\|` | 1.99 → 9.98 — linear, unbounded integrator wind-up |
| `\|Tcmd\|` | 0.0869 → 0.0836 |

Two causes, both configuration rather than control design:

- **`qbn_cmd = [0.5, 0.5, 0.5, 0.5]`** — the default target attitude from `Inp_ADAC.txt`,
  never commanded to anything meaningful (`GENERIC_ADCS_INERTIAL_QUATERNION_CC = 9` exists and
  is unused). The controller is chasing an arbitrary attitude it never reaches.
- **`Ki = [0, 0, 0]`** — the integral gain is zero, so `sumtherr` winds up without ever
  affecting `Tcmd`. The wind-up is recorded but inert.

⚠ `qValid` is also true in only **56 of 80** frames even with the star tracker enabled, so the
control law runs **intermittently**. See [`AINOS3-91`](AINOS3-91.md).

**Recommended sequencing change:** before the 12-run A/B, establish what a *correctly
configured* INERTIAL hold looks like — star tracker enabled, a real commanded quaternion, and
`qValid` steady. Measure the false-alarm rate against that. If it drops, this ticket's premise
changes from "the detector is wrong in INERTIAL" to "INERTIAL was never configured to be
held", which is a different and much cheaper fix.

⚠ Nothing here is a reason to close this ticket — the 33.6 % measurement stands as measured.
It is a reason not to spend the A/B until the plant configuration is settled.

### 2026-09-10 · ⚠ THE PLANNED FIX DOES NOT WORK — enabling the star tracker does not close the loop

Resumed (machine free). Ran the A/B the pause note specified, in miniature first: 180 s
INERTIAL with the ST **off**, then 180 s with the ST **on** plus a commanded target attitude.
The second arm was supposed to show the control law running. **It does not.**

| | ST off (legacy) | ST on + commanded attitude |
|---|--:|--:|
| INERTIAL frames | 1,230 | 723 |
| `ST.DeviceEnabled` | 0 | **1** |
| `ST_DEV.*` arriving | no | **yes** (the MID starts transmitting) |
| `ST_DEV.…IsValid` | — | **0** |
| `ADCS_DI.Payload.St.valid` | 0 | **0** |
| `ADCS_GNC.qValid` | 0/1230 | **0/723** |
| `ADCS_AC.Inertial.{therr,sumtherr,qErr,werr,Tcmd}` | all identically 0 | **all identically 0** |
| `ADCS_GNC.Tcmd` | frozen, 1 distinct value | **frozen, 1 distinct value** |

So enabling the device gets us **one** of the two things it was supposed to: the `ST_DEV` MID
starts transmitting, which independently confirms `AINOS3-91`'s root cause and `AINOS3-108`'s
`ST_DEV` disposition. It does **not** get us `qValid`, and `qValid` is the whole point — it is
what gates `AC_inertial()` (`generic_adcs_adac.c:338`).

**Where the chain breaks, traced end to end.** The break is at the *device validity* flag, one
step earlier than this ticket assumed:

    ST.DeviceEnabled = 1        ✅ commanded, and ST.DeviceCount increments
    ST_DEV…IsValid   = 0        ❌ BREAKS HERE
    ADCS_DI.St.valid = 0
    ADCS_GNC.qValid  = 0
    AC_inertial()               never executes

`generic_star_tracker_hardware_model.cpp:184` sets the wire validity byte straight from the
data point, and `generic_star_tracker_data_point.cpp:47` sets that from 42's
`SC[0].ST[0].Valid`. The sim is a faithful courier — it reports what 42 tells it.

**And 42 has never told it TRUE.** The sim's own debug log, which prints the flag on every
sample: **222/222 `is_valid=0` today, and 42/42 `is_valid=0` on 2026-08-23** — the session the
earlier entry was written from. Across every recorded CSV in `data/onair/csv/`, today's is the
**only** session in which the star tracker was ever enabled at all (1,911 frames), and
`qValid = 1` appears in **zero** rows of any of them.

⚠ **This contradicts the 2026-08-25 entry above** ("Enable the star tracker and they come
alive"; "`qValid` is true in only 56 of 80 frames"). That claim should be treated as
unreproduced until someone can show the measurement path it came from — nothing in the CSV
corpus or the sim logs supports it. Recording the disagreement rather than quietly overwriting
it, per [`feedback-evaluation-provenance`].

**Why this matters more than a failed step.** The pause note's own warning was that without a
tooling change "the *after* arm would silently reproduce the *before* condition." That is
exactly what happens — and it would **not** have been visible from the run's own outputs, since
`ST.DeviceEnabled` reads 1 and the run looks like it configured itself correctly. Committing
the planned 3.3 h × 12-run batch today would have bought 3.3 h of relabelled control data.

**What is NOT yet established: why 42 says invalid.** 42's `StarTrackerModel`
(`42sensors.c:304-342`) clears `Valid` on three exclusion tests, against a `+Z` boresight with
Sun 30° / Earth-limb +10° / Moon 10° cones (`SC_NOS3.txt:248-257`). Evaluated against 42's own
truth telemetry at 2026-09-10 14:46:18 (alt 392 km, limb half-angle 70.4°):

| test | measured | threshold | verdict |
|---|--:|--:|---|
| boresight → Sun | 89.9° | < 30.0° blinds | **passes** |
| boresight → nadir | 87.7° | < 80.4° blinds | **passes** |
| boresight → Moon | not evaluated | < 10.0° blinds | unknown |

So the two dominant tests both pass at the instant checked, yet the flag is false. Either the
Moon test is firing, or 42's `Valid` and the geometry disagree. **That gap is the actual open
question**, and it is a different investigation from the one this ticket was scoped for — do
not guess at it, and do not tune a detector against the current INERTIAL data either way.

⚠ **Consequence for `AINOS3-100`.** The per-mode collection gate is **not** cleared. The sprint
plan's stated fallback applies: collect per-mode where the mode is genuinely controlled and
hold SUNSAFE as the floor, with the INERTIAL slice marked provisional. INERTIAL data collected
today would still be uncontrolled drift wearing the INERTIAL label.

**Tooling landed anyway (and it is what made the null visible):**

- `single_mode_hold_INERTIAL` now enables the star tracker, waits `ST_SETTLE_S` for it to
  publish, and commands a real target attitude before entering the mode — the change the pause
  note asked for. It is correct and still necessary; it is simply not sufficient.
- `single_mode_hold_INERTIAL_uncontrolled` registered as the A/B **control arm**, named rather
  than flagged so a run manifest can never be ambiguous about which arm produced it.
- ⚠ Any INERTIAL run must now assert `qValid == 1` before trusting its data. A run that reports
  `ST.DeviceEnabled = 1` is **not** evidence the loop closed.

### 2026-09-10 · ROOT CAUSE PROVEN — the star tracker is EARTH-OCCULTED, and the target attitude was wrong

The previous entry stopped one layer short. Chased to ground truth; the answer is
geometry, and it is fixable.

**42 clears `ST->Valid` when the boresight is within (Earth-limb + 10 deg) of NADIR**
(`42sensors.c:304-342`). NOS3 flies at 392 km, so the limb half-angle is 70.4 deg and the
Earth exclusion cone is **80.4 deg wide about nadir**. `SC_NOS3.txt:248-257` gives one ST,
boresight `Z_AXIS`, mounting 0/0/0 — so the boresight is body `+Z`.

Evaluated against 42's own truth telemetry for the attitude we were actually holding:

| exclusion test | measured | blinds below | verdict |
|---|--:|--:|---|
| boresight → Sun | 89.9 deg | 30.0 deg | passes |
| boresight → Moon | 95.3 deg | 10.0 deg | passes |
| **boresight → nadir** | **63.0 deg** | **80.4 deg** | ⚠ **BLINDED** |

**The convention was verified, not assumed** — this is the step that makes the verdict
trustworthy. Getting the quaternion sense backwards turns 63.0 deg into 87.7 deg and silently
inverts the answer. 42 builds `CN` (inertial→body) as `Q2C(qn, CN)` (`42dynamics.c:190`,
`dcmkit.c:70`). Reconstructing 42's **own published `svb`** through our implementation of that
convention reproduces it to **0.05 deg**; the transposed convention is off by **40 deg**. Both
are pinned by tests.

**Why the planned fix was insufficient, precisely.** Enabling the star tracker was necessary —
it is what makes `ST_DEV` transmit at all — but the *target attitude* was the other half, and
identity was the wrong choice. At **any fixed inertial attitude** the nadir direction sweeps a
full circle in the body frame once per ~92 min orbit, so the boresight spends part of every
orbit inside the 80.4 deg cone. Propagated for the attitude we held: **blinded ~40 % of the
orbit, in one unbroken ~35-minute stretch.**

⚠ That single fact reconciles the contradiction in the previous entry. The 2026-08-25
observation (`qValid` true in 56/80 frames) caught an exclusion **boundary**; the 2026-09-10
run (0/723) landed **inside the blind stretch**. Both are correct measurements of the same
system at different orbit phases. The earlier entry is not retracted — it is explained.

## The fix — point the boresight along the ORBIT NORMAL

The orbit normal is perpendicular to nadir **by construction**, and stays perpendicular for
the entire orbit. Hold the boresight there and the boresight-to-nadir angle is pinned at
90 deg — a permanent **9.6 deg margin** outside the Earth cone, every orbit, indefinitely. The
Sun margin comes free from the beta angle: 116.6 deg against a 30 deg cone.

**Derived from mission config, not telemetry, and that is deliberate.** The obvious route is
the NOVATEL state vector, but it is ECEF and converting to ECI needs absolute UTC —
which the recorded telemetry cannot supply: `NOVATEL.Novatel_oem615.Weeks` is a
**rollover-truncated** GPS week (the sim keeps the rollover count in a field taken from 42's
`SC[0].GPS[0].Rollover`, which we do not subscribe). Reading `341` as an absolute week places
the epoch in 1986 instead of 2025 and rotates the derived normal by **~90 deg** — found by
measurement, not by review. The orbit plane is instead a *mission parameter*: 42 propagates
from the Keplerian elements in `Orb_LEO.txt` (i = 52 deg, RAAN = 180 deg), which give the
normal in closed form with no time conversion. Cross-checked against `r x v` from 42's truth
state vector at two independent samples: **0.002 deg**.

## ⚠ The bootstrap — and a second, separate defect it exposed

The controller **cannot slew while blinded**, because `qValid` gates the very law that would
move it. So a run starting inside a blind stretch must wait for the orbit to carry the
boresight out of the cone before it can capture.

Commanded live at 15:14Z. `qValid` went true at **T+10 min**, not the T+27 predicted — because
the prediction assumed an inertially-fixed attitude and the vehicle actually carries a body
rate of ~0.5 deg/s, which sweeps the boresight far faster than the orbit does. With `qValid`
true only ~6 % of frames, the control law runs in brief bursts, and the measured effect is
**divergence, not capture**:

| | |w| (deg/s) |
|---|--:|
| at command | 0.64 |
| +30 s | 1.40 |
| +60 s | **2.31** |
| +120 s | 1.68 |

Intermittent torque at a ~6 % duty cycle **pumps energy in**. So an INERTIAL hold cannot be
entered from a tumbling state at all — the rates must be damped first, by a mode that does not
depend on the star tracker. `BDOT` is exactly that (magnetorquer-only, and detumble is its
purpose). Commanded at 15:26Z; result in the next entry.

**Shipped this session:**

- `cmd.orbit_normal_from_config` / `cmd.quat_inertial_hold_target` — the target attitude,
  derived from `Orb_LEO.txt`, with the GPS-rollover trap documented next to the code.
- `single_mode_hold_INERTIAL` now commands the orbit normal instead of identity.
- `scenarios/inertial_capture.py` — asserts capture from telemetry (`qValid` sustained AND the
  control law producing varying output). ⚠ `ST.DeviceEnabled = 1` is NOT evidence the loop
  closed; this is the check that stops a blinded run from ever again being recorded as an
  INERTIAL hold.
- `training/test_inertial_geometry.py` — 8 tests pinning the quaternion convention against
  42's published `svb`, the 63 deg diagnosis, and the never-blinded property of the orbit
  normal (identity's blinded arc is asserted as the contrast).

### 2026-09-10 · ✅ CLOSED-LOOP INERTIAL ACHIEVED AND HELD — live, end to end

`AC1` and `AC2` complete. The first genuinely controlled INERTIAL hold this project has ever
recorded.

**Final state, measured from 42's truth over 3 minutes:**

| quantity | value | required |
|---|--:|--:|
| boresight → orbit normal | **0.4–0.6 deg** | (pointing error) |
| boresight → nadir | **89.4–89.9 deg** | > 80.5 deg (Earth cone) |
| `qValid` | **100 %** | sustained |
| `\|w\|` | 0.23–0.29 deg/s | settled |
| control law | **active** | non-constant `ADCS_AC.Inertial.*` |

The 9.6 deg margin the fix was designed around is exactly what the vehicle now holds, and it
holds it by construction rather than by luck of orbit phase.

## ⚠ The bootstrap needs SUNSAFE, not BDOT — measured, and it overturns the obvious choice

The first attempt used **BDOT** to damp rates, on the reasoning that detumble is its purpose
and it is magnetorquer-only so it works while the star tracker is blinded. **BDOT does not
converge on this vehicle.** Over 4 minutes it limit-cycled between 1.16 and 2.57 deg/s with no
downward trend.

The mechanism is a control-authority mismatch, not a bug. `AC_bdot` is textbook and correctly
signed — `Mcmd = -Kb * bdot / |bvb|` (`generic_adcs_adac.c:219-244`), and the observed
`Mcmd = 38.04` matches `Kb = 200` exactly. But `MaxMcmd` is **1.42**, so the command saturates
**27x over**, and the vehicle is tiny: 4 kg, `I = [0.0067, 0.033, 0.033]` kg·m²
(`SC_NOS3.txt:30-31`). Saturated bang-bang torque against that inertia overshoots every
correction, so it limit-cycles instead of damping. Torquers were verified enabled and actually
applying (`TORQUER.DeviceEnabled = 1`, `SC[0].MTB[0].Mcmd = -1.4200` reaching 42 clipped at the
limit) — BDOT was working exactly as designed and still the wrong tool.

**SUNSAFE is the damping mode.** It uses the sun sensors and reaction wheels — finer authority,
and no star-tracker dependency either. Measured: **1.66 → 0.26 deg/s in 95 seconds.** It is
also what the FSW boots into, and the session log shows it damping 2.09 → 0.32 deg/s in the
first ~50 s unprompted, which is why the vehicle's natural resting rate is ~0.2 deg/s.

## The working sequence

1. **`SET_MODE SUNSAFE`**, wait until `|w|` < ~0.35 deg/s (~95 s from a 1.7 deg/s tumble).
2. **`ST_ENABLE`**, then command the **orbit-normal** target quaternion.
3. **`SET_MODE INERTIAL`**, then **wait for the exclusion window to open** — up to ~35 min,
   because the controller cannot slew while blinded.
4. **Verify capture** with `inertial_capture.py`.

Once captured it holds indefinitely, so a batch of runs on one stack pays the wait **once**.

**The prediction was checked before the run, not after.** With rates damped the attitude is
effectively fixed, so the window is computable: predicted to open at T+3 min from a 73.7 deg
start against an 80.5 deg threshold; `qValid` came true at **T+2.5 min**, then went 33 % → 86 %
→ 96 % → **100 %** as the controller captured, with `|therr|` falling 1.07 → 0.28. The earlier
T+27 prediction failed only because it assumed a fixed attitude while the vehicle was tumbling
at 0.5 deg/s — the model was right, its input was wrong.

⚠ **Steps 1 and 3 are both load-bearing and neither is obvious from the telemetry.** A run that
skips the damp diverges (burst control pumps: 0.64 → 2.31 deg/s in 60 s); a run that skips the
wait records free drift labelled INERTIAL. Both look like healthy runs in their own output.
That is why `inertial_capture.py` exists and why every INERTIAL run must pass it.

## Remaining — `AC3`/`AC4` still open

The false-alarm rate has **not** yet been re-measured. That is the point of the work, and it
now has, for the first time, a genuinely controlled INERTIAL baseline to measure against. ⚠ The
published **33.6 %** describes uncontrolled tumble and should not be compared directly to
anything measured from here — a like-for-like re-measurement on captured INERTIAL is `AC3`.

### 2026-09-10 · ✅ AC3/AC4 — FP re-measured on the controlled baseline, and 33.6 % RECONCILED

**Headline: `0.0000 %` operational and `0.0000 %` raw over 7,230 controlled INERTIAL frames
(19.2 min, zero events).** Artifact:
`data/onair/results/ainos3_86_ac3_controlled_inertial_fp.json`. With zero events in 7,230
frames the 95 % upper bound is **0.04 %**, i.e. 24x inside the 1 % design target.

## ⚠ First: 33.6 % was a RAW figure, and it was never comparable to the 1 % target

Before claiming any improvement, the old number had to be reproduced. Running **the same tool**
over the 15 archived 2026-08-15 replication sessions, restricted to their nominal **pre-attack**
windows (attack-window frames are true positives; counting them as false alarms inflates FP):

| | raw FP (`is_anomaly`) | operational FP (`alert`) | mean `\|w\|` |
|---|--:|--:|--:|
| historical, loop OPEN (15 runs) | **36.2 %** (26.8–60.9) | 1.71 % (1.33–2.19) | 2.46 deg/s |
| published in the coverage doc | **33.6 %** (21.1–48.5) | — | — |
| **new, loop CLOSED** | **0.00 %** | **0.00 %** | 0.26 deg/s |

⚠ **The published 33.6 % is the RAW `is_anomaly` rate, not the operational one.** The
coverage-doc row records it in a column that names neither, sitting next to an AINOS3-81 cell
that explicitly says "0.54 % op / 7.5 % raw" — so it read as though it were the same kind of
number as the 1 % design target. It is not. The operational figure for those same runs was
**1.71 %**: still over target, but 21x smaller than the number the mode was condemned on.

The reconciliation is exact at the score level:

| | p1 | p50 | min | frames below threshold |
|---|--:|--:|--:|--:|
| training (uncontrolled, 19,641 rows) | -0.0000 | +0.1791 | — | — |
| historical loop-OPEN (9,765 nominal frames) | -0.0357 | +0.0058 | -0.0504 | **34.87 %** |
| **new loop-CLOSED** | **+0.0224** | +0.0554 | **+0.0146** | **0.00 %** |

34.87 % below threshold reproduces the published 33.6 % directly. Closing the loop moves the
whole score distribution off the threshold: the **closest single frame** sits
**+0.0146** above it, while the old p1 was **-0.0357** below.

## The 0 % is real, not a suppression artifact

Checked, because a warmup-suppressed detector also reports zero:

- the IF is **actively scoring** — 1,240 distinct scores in a 1,331-frame sample, not frozen;
- the per-mode threshold is live (`-2.2e-05`) and mode routing is on `MODE_INERTIAL`;
- **the same session raises 28 alerts / 495 raw anomalies elsewhere**, so the detector is not muted;
- the window starts 749 frames past the last mode change, well clear of the 250-frame
  mode-switch warmup.

## What this does and does not mean

✅ **INERTIAL is no longer unusable for detection.** The defect was never detector noise — it
was that the mode had never once been flown closed-loop, so every INERTIAL measurement was
taken against uncontrolled tumble at ~2.5 deg/s.

⚠ **The margin is thinner than the headline suggests, and this matters for `AINOS3-100`.**
Controlled flight scores p50 **+0.055** against a training p50 of **+0.179** — comfortably
above threshold, but in the lower tail of a distribution learned from uncontrolled data. The
deployed INERTIAL model is still trained on 19,641 rows of free drift; it passes controlled
flight, it was not fitted to it. **A retrain on a controlled-INERTIAL corpus should restore
headroom, and the corpus rebuild is where that happens.**

⚠ **Not yet re-measured: attack DETECTION in controlled INERTIAL.** Every prior INERTIAL
detection figure sat on the 36 % noise floor and is uninterpretable, but that cuts both ways —
a quiet baseline does not by itself prove the mode detects anything. That is a
`AINOS3-100`/`AINOS3-101` question, not this ticket's.

⚠ **Provenance for anyone citing these numbers:** single session, 19.2 min, one stack, one
orbit phase, `qValid = 100 %` throughout (watchdog-verified). Sample rate **derived** from
`CFE_TIME.SecondsMET` (6.26 Hz), never assumed — per `AINOS3-92`.

**Tooling:** `training/analyze_inertial_fp.py` (gates on `qValid`, not the mode label; pairs
side-file to main log by session timestamp, not mtime — pids recycle across launches and
"newest" silently paired a 2026-08-15 side-file with a 2026-09-10 log; derives Hz from MET) +
`training/test_inertial_fp.py`, 6 tests pinning both guards.
