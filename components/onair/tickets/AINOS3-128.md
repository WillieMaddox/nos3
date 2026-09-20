---
key: AINOS3-128
slug: interleaved-claim-audit
type: Spike
epic: AINOS3-79 (detector-rigor)
status: Backlog
priority: High
estimate: E 3 / T 1.0
opened: 2026-09-19
origin: AINOS3-125 (blended-log-format)
---

# AINOS3-128 — Re-derive the conclusions that rest on interleaved deltas

**Summary:** As a detector owner, I want every published conclusion that was computed from lag-1 deltas re-derived or retired, so the project stops reasoning from numbers measured on a representation we now know was defective.

## Description

`AINOS3-125` established that every recorded CSV was two interleaved buffer
snapshots, and that lag-1 deltas — what every model consumes — carried **4–6× the noise** of
same-buffer deltas on 49 of 454 non-constant columns.

⚠ **The damage is narrower than "everything is suspect", and the distinction is what makes
this tractable.** There are two kinds of claim:

- **Claims about the DEPLOYED system's behaviour remain true.** The fielded detectors really
  do see interleaved frames, so `AINOS3-86`'s 0.00 % controlled-INERTIAL FP, `AINOS3-90`'s
  55.8 incidents/hour and the Section-A rule-gate validations are accurate records of the
  system as it runs. They expire only when `AINOS3-126` lands.
- **Claims about what is LEARNABLE from the data are suspect**, because they were computed
  on the degraded representation.

⚠ Note the asymmetry for **null** results: a null measured on noisy features is weak
evidence of a null. `AINOS3-88`'s NO-GO and `AINOS3-99`'s limit deserve more scepticism than
a positive result of the same vintage would.

Candidates, highest risk first:

| Claim | Why suspect |
|---|---|
| `AINOS3-39` generic-counter reliance is a "mix"; drop-all costs ~3 pts | **Highest** — counters ARE the alternating fields |
| `AINOS3-99` fold spread is a footprint-reproducibility limit | Whole premise is delta-derived per-run variance |
| `AINOS3-37` hybrid per-mode gains +.058 / +.061 | Delta-based LOIO |
| `AINOS3-34` OOF incident-label accuracy 42.3 % | Delta-based |
| `AINOS3-88` Sprint-27 signal-feasibility NULL | A null on degraded features |
| v5 IF 61 % SUNSAFE corruption TP @ 1 % FP | Delta-driven detector |
| `AINOS3-121` IF is broad-anomaly-only | **Probably survives** — the blended A/B barely moved IF recall (0.0086 → 0.0149) |

## Acceptance criteria

- [ ] `AC1` Every claim above given a verdict: re-derived on blended data, retired, or explicitly marked "measured on interleaved, still true of the deployed system".
- [ ] `AC2` ⚠ `AINOS3-39` re-run first — it is the one whose subject matter (generic counters) coincides exactly with the affected columns, and its conclusion currently shapes retrain policy.
- [ ] `AC3` The two-kinds-of-claim distinction recorded in `V5_DETECTOR_COVERAGE.md` so future readers can tell a deployed-behaviour number from a learnability number without re-deriving this analysis.
- [ ] `AC4` ⚠ Nulls re-tested rather than inherited: a NO-GO measured on 4–6× noisier features is not a NO-GO.
- [ ] `AC5` Any claim that cannot be re-derived (source data archived or superseded) marked unverifiable rather than quietly retained — the `AINOS3-80` failure mode.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
