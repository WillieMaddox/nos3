---
key: AINOS3-127
slug: gate-retune-blended
type: Story
epic: AINOS3-63 (detector-gates)
status: Backlog
priority: Medium
estimate: E 5 / T 1.5
opened: 2026-09-19
origin: AINOS3-125 (blended-log-format)
---

# AINOS3-127 — Remove the flicker suppression the gates no longer need

**Summary:** As a detector owner, I want the three rule gates re-tuned once the live frame is coherent, so the desensitising workarounds they carry for the double buffer can be removed and the sensitivity they were costing us is recovered.

## Description

All three gates carry workarounds that exist **only** because of the double buffer, and every
one is a desensitiser:

- `consistency_check` — rolling-window-min plus `Margin` (default 4) instead of the natural
  `new < prev`, because per-frame reads alternate. It cannot see a back-step smaller than the
  window minimum minus 4. Without the workaround a naive check gave 83 % FP.
- `staleness_check` — tracks max-ADVANCEMENT rather than constancy, because a frozen counter
  oscillates between two buffer values. On a coherent stream a frozen field is genuinely
  constant, so the check becomes immediate instead of needing ~30–50 s to infer an advance
  interval.
- `rule_gate` — leaky-integrator flicker tolerance on R1/R5, a `ClearLevel` hysteresis sized
  for every-other-frame flicker, mode-switch oscillation tolerance, and a median-over-N filter
  on the time envelope because `CFE_TIME.SecondsMET` alternates between values ~4 s apart.

⚠ **Gated on `AINOS3-126`.** Until the live frame is coherent these
workarounds are load-bearing and removing them reintroduces the FP they were built to stop.

⚠ **The offline A/B could not answer this and should not be cited as if it had.** Replaying
the real plugins over blended CSVs moved rule_gate by +0.006 (noise) and left
`consistency_check` and `staleness_check` at exactly 0.0000 in both arms — because the attacks
they exist for, `EX-0014.02` (bus spoof) and `EX-0012.02` (route severing), are **absent from
the `AINOS3-100` corpus**. Their zero is "no applicable attack", not "no change".

## Acceptance criteria

- [ ] `AC1` ⚠ `EX-0014.02` and `EX-0012.02` collected first, or two of the three gates cannot be evaluated at all. Feeds `AINOS3-100 AC7`.
- [ ] `AC2` Each workaround identified above either removed or justified as still needed, with the FP/detection cost of removal measured rather than argued.
- [ ] `AC3` `consistency_check` re-tuned toward `new < prev` and the `Margin` reduced or dropped; the resulting FP measured over a nominal soak, not assumed.
- [ ] `AC4` `staleness_check` detection latency re-measured — the ~30–50 s floor is a property of the flicker workaround and should fall substantially.
- [ ] `AC5` All rule_gate rules R1–R15 re-validated live; any that only ever fired because of flicker tolerance is retired rather than carried.
- [ ] `AC6` ⚠ The Section-A 13-technique validation re-run. Those verdicts are records of the pre-change system and do not automatically carry.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
