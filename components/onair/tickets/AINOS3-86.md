---
key: AINOS3-86
slug: inertial-false-alarms
type: Story
epic: AINOS3-79 (detector-rigor)
status: In Progress
priority: High
opened: 2026-08-11
sprints: [27, 28]
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

- [ ] `AC1` Root cause identified and (1)/(2)/(3) distinguished — e.g. a ≥ 2 h INERTIAL soak run twice,
      with and without a commanded target quaternion, reporting nominal FP against uptime.
- [ ] `AC2` Fix applied to the cause, not the symptom: retrain/recalibrate on a proper INERTIAL
      baseline; or command a quaternion and fix the scenario tooling; or set an INERTIAL-specific
      warmup from the measured settling time.
- [ ] `AC3` INERTIAL nominal FP under the 1 % design target, measured on **held-out** nominal.
- [ ] `AC4` Re-soak to confirm; coverage doc updated with the measured value and its provenance tag.

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

