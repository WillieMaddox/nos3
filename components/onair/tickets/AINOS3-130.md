---
key: AINOS3-130
slug: sim-epoch-sweep
type: Spike
epic: AINOS3-98 (corpus-integrity)
status: Parked
priority: High
estimate: E 2 / T 0.5
opened: 2026-09-21
origin: AINOS3-126 (sbn-adapter-blended-output)
---

# AINOS3-130 — Find the orbital phase that minimises time-to-tracker-capture

**Summary:** As a corpus owner, I want to know how the starting orbital phase affects star-tracker capture time and eclipse coverage, so the collection launches from the best phase instead of the one that happens to be in the config — and so the corpus stops sampling a single lighting condition.

⚠ **Retitled 2026-09-21.** The original premise — that the *simulation epoch* selects orbital phase — is REFUTED. See the log.

## Description

Every run this project has ever collected launches from the same instant —
`cfg/InOut/Inp_Sim.txt:16-17`, `10 20 2025 / 17 43 20.00` — confirmed independently by
42's own config and by the recorded GPS time. Two consequences have gone unexamined:

- ⚠ **The INERTIAL capture wait may be an artifact of that one geometry.** Measured
  2026-09-21 on the smoke test: SUNSAFE 457.7 s vs INERTIAL 1087.8 s, a **+10.5 min**
  penalty spent waiting for the star tracker to clear the Earth exclusion cone
  (`qValid` by decile `[10, 0, 24, 100, 100, ...]`). Across the planned 95 INERTIAL runs
  that is **~16.6 h**. Nobody has checked whether another launch phase starts with the
  boresight already clear.
- ⚠ **The corpus has ZERO eclipse variation.** `ADCS_GNC.SunValid`, `Fss.valid` and
  `Css.valid` all flip with orbital lighting — measured shifting between an early and a
  late window of one session — but because every run starts at the same epoch, every run
  samples the same phase. A model trained this way has never seen eclipse and will treat
  it as anomalous.

⚠ **Reducing initial body rates is NOT the lever**, and it is worth stating so the next
person does not try it. `cfg/InOut/SC_NOS3.txt:12-16` already sets `Ang Vel = 0 0 0` and an
identity quaternion. `run_attack.py:243-292` documents why damping made things worse — it
parks the vehicle near the orbital rate (0.05–0.15 deg/s) where body rotation nearly cancels
the orbital sweep, an LVLH lock that leaves the tracker blind for hours and produced
capture of 0–49.8 % across 26 runs. Fast tumble is the mechanism that ACHIEVES capture.
The lever is **where in the orbit the run starts**, not how fast the vehicle is spinning.

## Acceptance criteria

- [ ] `AC1` Time-to-first-`qValid` and time-to-SUSTAINED-capture measured across **≥8 orbital
      phases** — `True Anomaly` in `cfg/build/InOut/Orb_LEO.txt`, stepped over 360° — with
      `single_mode_hold_INERTIAL`, **no attack**. ⚠ **≥3 reps per phase, ranked on the
      MEDIAN**: capture time varies **2.2x (225–498 s) at a FIXED phase**, so a single run
      cannot separate a better phase from a lucky draw.
- [ ] `AC2` Eclipse fraction per phase reported from `ADCS_GNC.SunValid`. ⚠ If no phase
      yields eclipse, the lever is **`RAAN`** (the orbit plane vs the Sun), not True
      Anomaly — at a fixed RAAN an orbit can be permanently sunlit. `--sweep raan` exists
      for this; record which knob was needed.
- [ ] `AC3` A recommended default phase, with its measured capture wait stated against the
      fixed-phase baseline (median **361 s**, ⚠ biased low — 4 of 8 prior runs were censored). ⚠ If no epoch improves on it, that is a valid and
      publishable result — record it rather than leaving the question open.
- [ ] `AC4` `cfg/build/InOut/Orb_LEO.txt` updated to the chosen phase ⚠ (**build**, not
      `cfg/InOut` — see the log), and the value recorded here
      **and** in `AINOS3-100 AC7`, since it changes what the corpus means.
- [ ] `AC5` ⚠ A decision recorded on whether epoch is held CONSTANT across instances or
      VARIED. Varying it would give the corpus eclipse coverage, but LOIO folds would then
      differ in instance **and** orbital phase — confounding two variables in the one metric
      the tier table rests on. Constant-epoch keeps LOIO clean and leaves eclipse coverage to
      a separate slice. State the trade rather than picking silently.
- [ ] `AC7` ⚠ **Every candidate epoch verified for SUNSAFE and BDOT too, not just INERTIAL
      capture.** Optimising the mode that carries 1/4 of the corpus must not break the other
      three — and SUNSAFE is also what damps the vehicle before an INERTIAL hold, so breaking
      it would break INERTIAL indirectly. Per epoch, record that the commanded mode held and
      body rates stayed bounded.

      ⚠ **Prior evidence says SUNSAFE survives eclipse, but does not settle the case.**
      Measured 2026-09-21 on a 90,001-frame all-SUNSAFE session spanning three full eclipse
      passes (43.8 % of frames with `SunValid=0`): `|w|` stayed within 0.011–0.024 deg/s
      with per-segment drift under ±0.012, and `ADCS_AC.Sunsafe.Tcmd` never froze longer in
      darkness (26–30 frames) than in sunlight (26–35). The control law keeps running; it
      simply has no sun vector to track, which is why its distinct-value count drops 26x.
      That is NOT the `AC_inertial()` free-drift failure.
      ⚠ But that session **entered** eclipse already converged. A run that **launches** in
      darkness starts at `SunValid=0` on frame one and has never had a sun reference — the
      untested case, and precisely what an eclipse-optimal epoch would create.
- [ ] `AC8` A kill-switch result table: each epoch either beats the running best or is
      aborted at it. ⚠ An aborted epoch reads "slower than `<best>`", **not** "never
      captured" — the two must not be conflated in the write-up.
- [ ] `AC6` ⚠ **Every sweep point verified to have actually taken effect**, from telemetry,
      before it is ranked. For a phase sweep that means the first GPS ECEF fix differs
      between points (`--min-separation-km`); for an epoch sweep, `OnAIR.SimTimeUTC`. This AC
      has now caught **two** void sweeps and is the most load-bearing criterion here.
      Original wording: `OnAIR.SimTimeUTC` verified to record the changed epoch correctly — it resolves
      the GPS 10-bit week rollover against this very file, so an epoch change is also the
      first real test of that decode.

## Notes

- Sim time is already recorded per frame as `OnAIR.SimTimeUTC` (`AINOS3-126`), decoded from
  the NOVATEL GPS week/second pair. ⚠ A naive decode of week 341 gives **1986-07-21** rather
  than 2025-10-20 — the 10-bit rollover — and the time of day is correct either way, which is
  what makes that bug survivable. The adapter resolves it against `Inp_Sim.txt`.
- `CFE_TIME.SecondsSTCF` is 0, so cFS carries MET only and cannot supply absolute time.
- Cost ≈ 3 h of stack time, no attacks, one sitting. Against a possible 16.6 h saving on
  INERTIAL alone, plus eclipse coverage that a later re-collect could not add cheaply.
- ⚠ **Sequence this BEFORE the corpus collection restarts.** A result either way changes the
  collection's epoch policy, and re-collecting 380 runs to add eclipse coverage afterwards
  costs far more than the sweep does now.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-09-21 · ⚠ PREMISE REFUTED — epoch does not select orbital phase

#### In plain terms

The idea behind this ticket was that starting the simulation at a different time of day would
start the spacecraft at a different point in its orbit. It does not. The orbit is built from
a fixed set of orbital elements every launch, so the spacecraft always begins in the same
place; changing the clock moves the Sun, not the vehicle. Two full sweeps were run before
this was caught, and both looked entirely plausible while measuring nothing.

**The mechanism.** `cfg/build/InOut/Orb_LEO.txt` initialises the orbit from Keplerian
elements applied at sim start:

```
KEP      !  Use Keplerian elements
52.0     !  Inclination (deg)
180.0    !  Right Ascension of Ascending Node (deg)
0.0      !  Argument of Periapsis (deg)
0.0      !  True Anomaly (deg)      <-- fixed, every launch
```

So the levers are:

| knob | controls |
|---|---|
| `True Anomaly` | WHERE IN THE ORBIT a run starts — the capture lever |
| `RAAN` | the orbit plane vs the Sun — the eclipse lever |
| epoch | Sun position and Earth rotation only — **not** spacecraft phase |

#### The evidence

Sweep of 7 epochs across a full 95 min orbital period, 1 rep each:

- **Eclipse fraction 0.0000 at every point.** A 12 min epoch shift moves the Sun by ~0.03°
  of Earth's annual orbit, so the lighting geometry was effectively identical throughout.
- **1/7 captured (498 s), 6/7 timed out**, with no relation to offset — consistent with the
  known 2.2x fixed-phase noise, not a phase signal.
- ⚠ `AC6` passed at all 7 points: the epoch really was applied. The knob worked; it was the
  wrong knob.

#### ⚠ Two earlier failures, both caught only by a readback

This is the third attempt, and the first two produced plausible-looking tables that were
measuring nothing:

1. **Wrong file.** The harness wrote `cfg/InOut/Inp_Sim.txt`, but `cfg/build/launch.sh:97`
   copies `cfg/build/InOut/` into the sim — `cfg/InOut` is only the source `make config`
   builds from. All 8 runs launched at the unchanged epoch. The table showed
   498/437/285/225 s with a clean downward trend; it was the kill switch ratcheting the
   running minimum over 8 noisy draws.
2. **Timeout recorded as a measurement.** After the capture wait times out the scenario
   still runs its 150 s hold, and the tracker often captures during it — so a tail-sample
   verdict read "captured" and `elapsed - hold` reported the CEILING as a time. Three reps
   logged exactly 559 s. Identical values to the second were the only visible symptom, and
   the owner spotted them.

**The standing lesson, and why `AC6` was promoted.** In all three cases the failure was a
config write that silently did nothing, and in all three the results table looked fine. A
sweep must verify from TELEMETRY that each point actually took effect before ranking it —
recorded epoch for an epoch sweep, first GPS ECEF fix for a phase sweep. Nothing else in the
pipeline catches this.

#### What survives

- The 2.2x fixed-phase capture variance (225–498 s), which is why `AC1` now requires reps.
- The build-path fix, verified: `AC6` OK at all 7 points of the last sweep.
- Correct timeout labelling.
- `training/scenarios/epoch_sweep.py` now takes `--sweep anomaly|raan|epoch`, defaulting to
  `anomaly`, with a phase readback gate (`--min-separation-km`) that voids any point starting
  where an earlier one did. `epoch` is kept only to reproduce this null.

### 2026-09-21 · PARKED — mechanism found and working, but no actionable answer

#### In plain terms

We can now move the spacecraft to any point in its orbit and measure what happens, and doing
so revealed something worth having: part of the orbit is in darkness, which no run this
project has ever collected. What it did not reveal is a starting point that reliably makes
the star tracker lock on faster. The same phase can lock in four minutes or not at all, so
telling a good phase from a lucky run needs many more runs than the answer is worth right
now. Parked in favour of collecting the corpus.

#### ✅ What was established

**The mechanism works**, verified geometrically rather than assumed:

```
orbit radius              6778 km   (400 km altitude ✓)
adjacent 45° separation   5198 km
expected 2·r·sin(22.5°)   5187 km   — matches to 0.2 %
```

**`AC2` is ANSWERED, and the lever was not the one predicted.** `True Anomaly` — not `RAAN` —
controls eclipse here. Measured across 360° in 45° steps:

| True Anomaly | eclipse fraction | capture (1 rep) |
|--:|--:|--:|
| 0° | 0.00 | 255 s |
| 45° | 0.00 | TIMEOUT |
| 90° | 0.00 | 285 s |
| 135° | **1.00** | 255 s |
| 180° | **1.00** | TIMEOUT |
| 225° | **0.82** | TIMEOUT |
| 270° | 0.00 | 285 s |
| 315° | 0.00 | TIMEOUT |

⚠ Eclipse and capture are **independent**: 135° is fully eclipsed and captured fast; 180° is
fully eclipsed and timed out. So a phase can be chosen for one without forfeiting the other.

⚠ The corpus currently has **zero** eclipse coverage — every run to date launches at
`TA = 0`, which is sunlit. These sweep runs are the only eclipse-bearing telemetry the
project holds, kept in `data/onair/csv_sweep_artifacts/`.

#### ⚠ Why `AC1`/`AC3` could not be answered

**Capture time varies ~2.2x at a FIXED phase** — 225, 285, 437, 498 s measured over 8 runs at
`TA = 0`, with 4 more censored. Against that spread, 8 phases x 1 rep cannot distinguish a
better phase from a lucky draw, and the owner's judgement (2026-09-21) was that the reps
needed to resolve it cost more stack time than the wait they would save. Captures do cluster
tightly at 255/285 s (30 s apart = `CAPTURE_POLL_S`) against timeouts >382 s, which hints the
split is bimodal rather than continuous — worth a look if this is ever revived.

#### ⚠ Three void sweeps, and the lesson that outlived them

Every one produced a plausible-looking table while measuring nothing:

1. **Wrong file** — wrote `cfg/InOut/Inp_Sim.txt`; `cfg/build/launch.sh:97` copies
   `cfg/build/InOut/`. All 8 runs ran at one epoch; the "clean downward trend" was the kill
   switch ratcheting a running minimum over noisy draws.
2. **Timeout as measurement** — after the wait times out the scenario still runs its 150 s
   hold, the tracker often captures during it, and `elapsed - hold` then reported the
   CEILING. Three reps logged exactly 559 s; identical values were the only symptom.
3. **Wrong knob** — epoch moves the Sun and Earth rotation, not spacecraft phase, because
   `Orb_LEO.txt` initialises from Keplerian elements at sim start.

And a fourth, self-inflicted, during the fix: `write_epoch(when, path=INP_SIM)` bound its
default at DEFINITION time, so a sandboxed test's monkeypatch did nothing and the test
rewrote the live `cfg/build/InOut/Inp_Sim.txt`. Paths are now resolved at call time, with a
test asserting the real tree is byte-identical after a run.

**The durable lesson:** a config-driven sweep must verify FROM TELEMETRY that each point took
effect before ranking it. Nothing else in this pipeline catches a write that silently goes
nowhere. That is why `AC6` was promoted from bookkeeping to the most load-bearing criterion
here, and it is the only reason any of the four were caught.

#### To revive

`epoch_sweep.py --sweep anomaly|raan|epoch` with the phase gate, kill switch and 9 tests
(`training/test_epoch_sweep.py`) are all in place. Needs ~5+ reps per phase; budget from the
2.2x spread, not from the 1-rep shakedown.
