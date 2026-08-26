# AINOS3-118 · Prioritised Attack-Vector Backlog (AC1)

The single prioritised list of attack vectors, classified **buildable** vs **needs
observability first**, and — for the buildable ones — whether they **reach a detector**.
Grounded in the live validation of the EX-0014 family (slices 1-3) and the mechanical
observable/feature/rule inventory, not prose judgement.

## Method

A vector is decided on two independent axes.

- **Buildable** — its on-wire footprint maps to a telemetry MID OnAIR records, so it can be
  produced. External injection is via CI_LAB's UDP ingest (:5012), which republishes any MID
  onto the Software Bus (validated slices 1-3). Command-path techniques are buildable by
  definition (the command bus is external).
- **Detectable** — the produced observable reaches a gate:
  - **IF** if the spoofed field is a **non-masked model feature**, or **propagates** into one.
    Attitude sensors (IMU/MAG/CSS/FSS/ST) fuse into `ADCS_DI.Payload.<sensor>.*`, which ARE
    features — validated: a forged IMU `AngularAcc` lands in `ADCS_DI.Payload.Imu.wbn` 1:1.
    GPS position does **not** (`ADCS_DI.Gps` has 0 features) and its `NOVATEL.*` columns are
    delta-only **masked**, so it is IF-invisible.
  - **rule-gate** if a rule watches that MID's counter/flag/state (R1-R16).
  - **consistency / staleness** for monotonic-counter and frozen-stream footprints.

⚠ **Detectable ≠ strongly detected.** Even a propagating sensor spoof is only *marginally*
caught — the double-buffer flicker holds the feature for a fraction of frames, so the dynamics
IF sees brief discontinuities, not a sustained regime shift (IMU: 1-7 anomaly frames). A
recorded observable is also not a verified one until fired live (the AINOS3-96 caveat).

## Detectability matrix (40 subscribed MIDs)

The backbone. "IF" = spoof reaches the isolation forest (directly or via ADCS_DI fusion);
"rule" = a rule-gate rule covers it; masked = delta-only (raw value invariant).

| MID | channel | IF path | rule-gate | spoof verdict |
|---|---|---|---|---|
| 0x0871 | NOVATEL (device) | masked; no ADCS_DI fusion | R15 (time only) | **time→R15**, **position→GAP** |
| 0x0926 | IMU_DEV | → ADCS_DI.Imu (14 feat) | R1 on IMU.DeviceEnabled | **rate→IF (marginal)** |
| 0x092B | MAG_DEV | → ADCS_DI.Mag (7 feat) | R1 | buildable → IF (untested) |
| 0x0911 | CSS_DEV | → ADCS_DI.Css (34 feat) | R1 | buildable → IF (untested) |
| 0x0921 | FSS_DEV | → ADCS_DI.Fss (8 feat) | R1 | buildable → IF (untested) |
| 0x0935 | ST_DEV | → ADCS_DI.St (9 feat) | R1 | buildable → IF (untested) |
| 0x08EA | THRUSTER | direct feature | R1 | buildable → IF |
| 0x0993 | RW | direct feature | R1 | buildable → IF |
| 0x0804 | CFE_TBL | masked | R9 | command-path only (table commit not injectable) |
| 0x0805 | CFE_TIME | masked | R15 | time set → R15 |
| 0x0803/0801/0800 | CFE_SB/EVS_HK/ES | feature | R6/R7/R8 | counter spoof → rule |
| 0x0880/088A/08A7/08B0 | TO/FM/LC/CF | record-only | R12-13/R11/R5/R16 | change → rule |

Full per-MID feature/mask/rule breakdown is regenerable from `nos3_security_tlm.json` +
the model schema + the rule map (see the session log in `tickets/AINOS3-118.md`).

## Tier 1 — buildable AND reaches a detector (do next)

Highest leverage: each reuses the **validated** inject-and-propagate mechanism and adds
live-verified coverage cheaply.

- **Attitude-sensor spoof family — MAG / CSS / FSS / ST** (extends the validated EX-0014.03
  IMU case). Each raw device MID (0x092B / 0x0911 / 0x0921 / 0x0935) fuses into its
  `ADCS_DI.Payload.<sensor>.*` features, so a forged reading reaches the IF exactly as IMU
  did. Expected: marginal IF catch (flicker-limited). One `--mechanism sensor-spoof` slice per
  sensor; MAG first (magnetometer most directly drives attitude determination).
- **Actuator spoof — RW / THRUSTER** (0x0993 / 0x08EA are direct IF features). A forged wheel
  speed / thruster state inconsistent with commanded torque is a dynamics contradiction the IF
  should weight; distinct from the sensor path.

## Tier 2 — buildable but currently UNDETECTED (build to document the gap)

Value is in proving and bounding the blind spot, feeding the retrain / rule work.

- **NOVATEL position spoof (EX-0014.04)** — DONE (slice 2). Injectable, dominates the recorded
  column, **0 gates catch it** (masked + no ADCS_DI fusion). Fix filed: AINOS3-97 AC6
  (torn-read training filter) or a position-consistency primitive.
- **Any recording-only MID with no rule and no ADCS_DI fusion** — e.g. TORQUER (0x093A),
  DS (0x08B8). A spoof lands in the CSV but no gate sees it. Build only to document; each is a
  candidate rule-gate rule, not a detection win yet.

## Not buildable now (with reason — feeds AC4)

- **Footprint-limit — table-commit techniques** (EX-0012.03/04/05/08, EX-0008.01/02). The
  LOAD/ACTIVATE command path and its detection (R9) are faithful, but a *committed* table swap
  is not reproducible via external injection (ACTIVATE errors, no pending buffer — slice 4).
  Detection covered; effect not injectable.
- **Deprecated — IMP-0001/2/3/5/6.** Retired in SPARTA v4.0; needs a relabel to the v4
  successors (IMP-0007/8/9), not a script. → AINOS3-101.
- **Intent-gap — DE-0003 ×7** (conceal command counters / quiet windows). The SPARTA intent is
  concealment, whose faithful footprint genuinely IS a counter reset / probe — there is no
  richer observable to build. → AC4, not repairable.
- **Needs observability first — unsubscribed / unrepresentable.** Vectors whose IOB arguments
  map to a MID OnAIR does not subscribe, or a field that cannot carry the value
  (`mid_stix_map.py` state `no-observable` / `field-cannot-represent-value`). These gate on a
  subscription or schema change before any script.

## Priority rationale

Ordered by **leverage over the retrain/coverage destination**, not by cost. Tier 1 converts the
one proven mechanism (inject → ADCS_DI fusion → IF) into several live-verified detections for
near-zero marginal effort. Tier 2's single most valuable item (the position gap) is already
banked and routed to the retrain. Everything else is classification, relabel, or an
observability prerequisite — none of it is "write a better attack script".
