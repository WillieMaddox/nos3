---
key: AINOS3-107
slug: frame-aliasing-semantics
type: Spike
epic: AINOS3-79 (detector-rigor)
status: Open
priority: Medium
estimate: E 3 / T 0.75
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-107 — Frame aliasing and per-frame threshold meaning

**Summary:** 74% of SBN messages never surface as their own frame, so the staleness gate's 'advance interval' measures OnAIR's loop rate rather than the FSW's publish rate.

## Description

Measured in AINOS3-95 stage 0 and confirmed in stage 4: OnAIR receives **~23 messages/s** and
emits **~6 frames/s**. `onair/src/run_scripts/sim.py` has no rate limiter, so the loop is
**compute-bound** — roughly **74% of arriving messages are overwritten in the write buffer
before it is read**.

Two consequences that reach the deployed detectors:

1. The **staleness gate** discovers each counter's steady-state no-advance gap **in frames**.
   Because frames are decoupled from arrivals, that interval describes OnAIR's own processing
   cadence, not the rate at which the FSW publishes. A change in host load or column count
   shifts it without anything on the spacecraft changing.
2. Any threshold expressed **per frame** — rule-gate R2's EVS rate, the consistency-check
   window — inherits the same dependency.

This is pre-existing and not caused by any AINOS3-95 change, but it was never written down.

⚠ It also bounds the cross-MID feature class: differencing two MIDs in one frame compares
values of *different ages*, which is why the naive GPS-vs-MET feature had a 29 s noise floor
and needed a monotonic-envelope treatment.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` The overwrite ratio characterised across at least two host-load conditions, so the variability is quantified rather than a single point estimate.
- [ ] `AC2` A statement, per deployed gate, of whether its thresholds are frame-relative or wall-clock-relative, and which are therefore load-sensitive.
- [ ] `AC3` A recommendation on whether the staleness gate should key on MET-derived elapsed time instead of frame counts.
- [ ] `AC4` A written convention for cross-MID derived features, so the GPS-vs-MET lesson is not re-learned.
- [ ] `AC5` Whether OnAIR should drain the message queue per frame rather than sampling the latest — assessed, with the corpus-fidelity implications stated.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
