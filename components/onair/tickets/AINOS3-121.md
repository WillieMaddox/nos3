---
key: AINOS3-121
slug: if-scoring-audit
type: Spike
epic: AINOS3-79 (detector-rigor)
status: Open
priority: High
estimate: E 5 / T 1.5
opened: 2026-08-27
sprints: [28]
origin: AINOS3-118 (challenge to IF-null conclusions)
---

# if-scoring-audit — Reproducible IF scoring + per-feature sensitivity/calibration audit

**Summary:** Before any design decision rests on an IF **null** ("0 anomalies → gap"), establish that the deployed isolation forest is a trustworthy oracle for that judgement: reproduce its live scores offline, prove per-feature sensitivity with positive controls, and check the operating threshold is calibrated. Today none of these hold, so IF nulls are only valid as *operational coverage facts*, not as *mechanistic/design conclusions*.

## Description

AINOS3-118 repeatedly concluded "the IF does not catch X" from a live 0-anomaly result, and
attached mechanisms ("masked", "high-variance feature absorbed", "flicker-limited"). A challenge
exposed that those mechanistic claims were unearned:

- **Structural check (done, passed):** the features in question (MAG `ADCS_DI.Payload.Mag.bvb`,
  IMU `Imu.wbn`, NOVATEL `d_ECEF*`) ARE used by the deployed SUNSAFE forest (~50-70 splits each
  of 8115). So "the model ignores the feature" is refuted — but usage ≠ response-to-spoof.
- **Reproducibility gap (the blocker):** an offline `decision_function` on a *nominal* frame
  returned −0.0265 (would flag anomaly) while the live plugin scored the same frame **normal**
  (positive ~0.06-0.12). Same model, same call (plugin line 606), different feature vector — the
  live feature construction is stateful (frame-to-frame deltas, nested-list extraction) and a
  batch `build_features` reconstruction does not mirror it. So the positive-control sensitivity
  test **could not be run**, and mechanistic claims about per-feature behaviour are unverified.

This spike makes IF nulls defensible for design use, and is a prerequisite for trusting the
Sprint-29 retrain evaluation.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` **Reproduce live scores offline.** Either have the isolation_forest plugin log its
      actual per-frame feature vector to a side-file, or build a golden-frame fixture, such that
      an offline `decision_function` matches the live `iforest_out` score for the same frame to
      within float tolerance. Without this, nothing else is trustworthy.
- [ ] `AC2` **Per-feature positive controls.** For each feature a live null has been (or will be)
      based on, hold a reproduced nominal vector and sweep that feature across its plausible +
      attack range; record whether the score ever crosses threshold. Classify each feature as
      *responsive* (a null there is meaningful) or *unresponsive* (a null there is a model-blind
      artifact, not a coverage fact). Cover at least: `Imu.wbn`, `Mag.bvb`, `d_ECEF*`, plus one
      known-catchable dynamics feature as a control that MUST respond.
- [ ] `AC3` **Calibration check.** Confirm the deployed per-mode thresholds sit where the claimed
      steady-state FP rate holds (cross-check against the soak-FP evidence); flag any mode whose
      threshold does not.
- [ ] `AC4` **Re-adjudicate the AINOS3-118 gaps.** Using AC1-AC3, mark each recorded IF gap
      (EX-0014.04 position, EX-0014.03 MAG, and any CSS/FSS/ST tested) as *true coverage gap*
      (feature responsive, attack still missed) vs *model-blind* (feature unresponsive → a
      retrain/feature-transform candidate, not a new-detector candidate). Update the vector
      backlog + AINOS3-97 AC6 framing accordingly.
- [ ] `AC5` **Standing rule recorded:** an IF null may back an *operational coverage* statement
      immediately, but may back a *design/mechanistic* conclusion only after AC1-AC2 clear it for
      that feature. Wire a one-line check or doc note so the rule is visible to future work.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
