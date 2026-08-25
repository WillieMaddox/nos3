---
key: AINOS3-91
slug: startracker-inert-fields
type: Spike
epic: AINOS3-41 (coverage-expansion)
status: In Progress
priority: Medium
opened: 2026-08-11
sprints: [27, 28]
---

# AINOS3-91 — Star-tracker validity is intermittent and the device is off by default

**Summary:** As a defender, I want to know why the star tracker reports nothing by default and why its validity flag is intermittent once enabled, because an ADCS attitude source that is off or unreliable is both a blind spot and a distortion of every ADCS measurement we have taken.

## Description

⚠ **The premise below was mis-diagnosed; see `AC1` and the log.** Kept as written because it
records what was originally observed and why the spike was opened.

In the 41,434-row weak-class corpus, `ST_DEV.Generic_star_tracker.IsValid`
and `.Q0`–`.Q3` are **constant across every frame**. Found incidentally during the
signal-feasibility ablation, where 15 of 109 added columns were inert — the other ten are
explained (6 `CFE_TBL` known-dormant, 4 `TORQUER`), these five are not. A star tracker
supplies attitude quaternions; if it genuinely produces nothing, any attack on it is
invisible, and the fused `ADCS_DI` view may be carrying the whole attitude signal alone.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

⚠ **Rewritten 2026-08-25.** The original `AC1`-`AC3` forked on "is OnAIR mis-parsing, or does
the sim never populate the fields". The answer is **neither** — see `AC1` — so that fork is
closed and the criteria below are scoped to what the finding left open.

- [x] `AC1` **RESOLVED.** The fields are constant because the **device is disabled by default**
      (`ST.DeviceEnabled = 0`), so MID `0x0936` never transmits — not a parse bug, not an
      unpopulated sim field. Evidence: a 90 s per-MID arrival measurement showing zero packets,
      and a live `GENERIC_STAR_TRACKER_ENABLE` (`0x1935` FC 2) that starts the MID transmitting
      immediately. Recorded in the log below.
- [ ] `AC2` The **intermittency** characterised — with the tracker enabled,
      `ADCS_DI.Payload.St.valid` was true in only **56 of 80** frames. Establish whether that
      ~70 % duty cycle is modelled physics (Earth/sun exclusion, slew-rate limits) or a sim /
      adapter defect. ⚠ 80 frames is too small to conclude from; use a window long enough to see
      the pattern repeat.
- [ ] `AC3` A decision recorded on whether the star tracker should be **enabled by default** in
      the headless launch, with the cost stated either way: every soak to date and the entire
      existing corpus ran with it **disabled**, so enabling it changes the nominal baseline and
      makes prior ADCS-related measurements non-comparable.
- [ ] `AC4` Any technique whose verdict rests on star-tracker telemetry reclassified with the
      **correct reason**. "Disabled by default in this build" is not the same verdict as
      UNSUBSCRIBED or not-modelled, and only the first is re-openable by a command.
- [ ] `AC5` The blast radius on other tickets recorded rather than left implicit — at minimum
      [`AINOS3-86`](AINOS3-86.md) (INERTIAL ran with `qValid = 0`, i.e. **no closed-loop control
      at all**, which may make its 33.6 % false-alarm floor a configuration artifact) and
      [`AINOS3-100`](AINOS3-100.md) `AC4` (the rebuild must collect with the tracker enabled).
- [ ] `AC6` `SPARTA_LOGGING_GAP.md`'s silent-MID list and the coverage overlay updated if any
      verdict moves as a result.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.

### 2026-08-25 · ROOT CAUSE — the fields are not inert; the device is disabled (via AINOS3-95)

Found while validating the AINOS3-95 stage-2a subscription; full detail in
[`AINOS3-95`](AINOS3-95.md) and [`SPARTA_LOGGING_GAP.md`](../SPARTA_LOGGING_GAP.md).

This ticket's premise — "5 `ST_DEV` star-tracker fields constant corpus-wide" — is true but
**mis-diagnosed**. The fields are not inert telemetry:

- A frame-rate measurement over a 90 s window found `ST_DEV` **0x0936 is subscribed but
  never transmits** — one of four such dead subscriptions (with `CFE_SB_SUBS`, `SBN`,
  `RADIO_DEV`).
- The reason is upstream: **`ST.DeviceEnabled = 0`** — the star tracker is disabled in this
  build's default state. `ST.DeviceCount`, `ST.CommandCount` are likewise 0.
- Commanding `GENERIC_STAR_TRACKER_ENABLE` (MID `0x1935`, FC 2) starts 0x0936 transmitting
  immediately and `ADCS_AD.ST.qbn` carries a real, varying quaternion.

So the constant fields are a **configuration state, not a modelling gap**, and no amount of
corpus analysis would have shown that — the evidence is in whether the MID arrives at all.

⚠ Even once enabled, `ADCS_DI.Payload.St.valid` is **1 in only 56 of 80** frames, so
star-tracker validity is intermittent rather than steady. That intermittency is the part
still worth a spike, and it is a different question from the one this ticket asks.

**Recommendation:** re-scope to the intermittency question, or close as answered. Not closed
here — that is the owner's call. ⚠ This also gates [`AINOS3-86`](AINOS3-86.md); see its log.
