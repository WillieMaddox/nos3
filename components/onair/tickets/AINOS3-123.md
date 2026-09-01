---
key: AINOS3-123
slug: per-subsystem-consistency-primitive
type: Story
epic: AINOS3-63 (detector-gates)
status: Backlog
priority: High
estimate: E 5 / T 2.0
opened: 2026-08-29
origin: AINOS3-121 (if-scoring-audit)
---

# AINOS3-123 — Per-subsystem consistency gate

**Summary:** As a defender, I want a per-subsystem range/plausibility gate running beside the IF, because `AINOS3-121` proved the deployed isolation forest misses **any** spoof confined to one subsystem's telemetry (position / MAG / IMU) in **all four modes at any magnitude** — a true coverage gap no attack script or retrain closes, only a targeted primitive.

## Description

`AINOS3-121` established, with a reproducible offline harness (exact live-score match) and
per-mode positive controls, that a spoof confined to a **single subsystem's** telemetry
(NOVATEL position `d_ECEF*`, MAG `ADCS_DI.Payload.Mag.bvb`, IMU `Imu.wbn`) is **undetected by
the deployed IF in all four ADCS modes, at any magnitude** — and that this is a **true coverage
gap**, not a model-blind artifact: the features are used and the model detects broad anomalies,
but a 1 %-FP threshold sits in the extreme low tail of a concentrated nominal distribution, so no
small feature-subset carries enough score weight to cross. `AINOS3-118` live-validated the
matching attacks (EX-0014.04 position spoof; EX-0014.03 MAG; EX-0014.03 IMU marginal).

The fix `AINOS3-121` named is a **per-subsystem detection primitive — a range/consistency check
— not more spoof scripts and not a feature un-mask.** This ticket owns that primitive.

⚠ **Re-homed here 2026-08-29.** It was previously "tracked on `AINOS3-118`", a Story about
*generating attack scripts*. Building a detector inside an attack-generation Story is scope drift
this project's ticket conventions reject. It belongs under the detector-gates epic (`AINOS3-63`),
a **fourth-class** sibling of the rule-gate (`AINOS3-64`), consistency-check (`AINOS3-65`) and
staleness-check (`AINOS3-66`) — each of which was built for exactly this reason: an attack class
the deployed IF is structurally blind to.

⚠ **This is a coverage gap the IF cannot be tuned into catching** (`AINOS3-121` proved the
threshold mechanism), so a complementary gate is the *only* route — the same conclusion that
justified the other three gates. It is distinct from them: rule-gate watches discrete
flag/counter/state changes, consistency-check watches monotonic counters, staleness-check watches
frozen streams — none checks whether a *continuous sensor value* is physically plausible or
mutually consistent, which is what a single-subsystem spoof violates.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` A per-subsystem gate that flags an implausible or mutually-inconsistent sensor value on the confirmed-gap subsystems: NOVATEL position (`d_ECEF*`), MAG (`bvb`), IMU (`wbn`). Range/plausibility and cross-field consistency are both in scope; the specific check per subsystem is recorded with its rationale.
- [ ] `AC2` 0 false positives over a nominal soak of at least 3,000 frames including at least one mode transition — the bar the other three gates met. ⚠ Watch the double-buffer flicker that cost the consistency-check 83 % FP (`AINOS3-65`); a window-min / name-filter is likely needed.
- [ ] `AC3` A live TP against the `AINOS3-118`-validated attacks: EX-0014.04 position spoof and EX-0014.03 MAG, run against the live FSW, parsed with `csv.DictReader`.
- [ ] `AC4` CSS / FSS / ST assessed on the same basis — `AINOS3-118` predicted they read the same 0 % until this primitive exists; confirm and cover or record why not (⚠ ST is off by default — `AINOS3-91`).
- [ ] `AC5` Deployed through the `AINOS3-37` discipline: plugin synced to the build tree (`fsw/build/exe/cpu1/cf/onair/`), ini one-line enable + one-line rollback, live-verified, incident wiring as for the other gates. Not deploying is a valid outcome if AC2 cannot be met.
- [ ] `AC6` ⚠ BDOT is excluded from the coverage claim — `AINOS3-121` flagged its positive control as inert (1 % posctl), so a null there means nothing; do not assert BDOT coverage from this gate.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-08-29 · created — re-homed from AINOS3-118

Split out of `AINOS3-118` during the Phase-4 rollback: `AINOS3-121` concluded the PNT/MAG/IMU
gap fix is a per-subsystem primitive, but it was being tracked inside an attack-generation Story.
Created here under `AINOS3-63` so the detector build has a proper home. The `AINOS3-121` harness
(`if_audit.py`) and the `AINOS3-118` live-validated spoofs are the inputs; nothing here re-opens
those — they are the evidence this gap is real and worth a gate.
