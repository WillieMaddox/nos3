---
key: AINOS3-120
slug: schedule-cfe-diag-packets
type: Story
epic: AINOS3-41 (coverage-expansion)
status: Open
priority: Low
estimate: E 3 / T 1.0
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-120 — Schedule the silent cFE diagnostic packets

**Summary:** Four cFE diagnostic packets are routed but never scheduled, so they never transmit; scheduling them needs FSW table work and index-walking logic.

## Description

`to_config.c` routes `CFE_SB_STATS_TLM` `0x080A`, `CFE_ES_APP_TLM` `0x080B`,
`CFE_TBL_REG_TLM` `0x080C` and `CFE_SB_ONESUB_TLM` `0x080E`, but `sch_def_msgtbl.c` has **zero
scheduler entries** for the commands that produce them, so they never appear periodically.

Deferred from AINOS3-95 stage 2b because, unlike a plain subscribe, they need scheduler-table
edits plus an FSW table rebuild.

⚠ Two of them answer **one item per command**: `CFE_ES_APP_TLM` reports a single application
(`OneAppPacket`, `GetModuleInfo` for one resource id) and `CFE_TBL_REG_TLM` a single table.
Monitoring all ~35 apps continuously therefore needs logic that *walks the index* each cycle,
not a single scheduled command. That is the real cost here.

**Honest value assessment**, recorded so this is not oversold:

- `0x080B` `ES_APP` — the only genuinely new detection signal (per-task `ExecutionCounter`,
  an activity proxy for `EX-0009` code exploitation). ⚠ It is *not* CPU utilisation, which an
  earlier AINOS3-95 draft wrongly claimed.
- `0x080A` `SB_STATS` — per-pipe depths; largely redundant with R6 plus the staleness gate.
- `0x080C` `TBL_REG` — per-table CRC; likely **superseded by `AINOS3-111`**, which is why
  this ticket is sequenced after it.
- `0x080E` `SB_ONESUB` — poor bet: its sibling `0x080D` `ALLSUBS` is already subscribed and
  measured **silent**.

⚠ AINOS3-88 tested "more recorded telemetry" across seven arms and returned a documented NULL,
and sparse one-item-per-command packets are worse feature candidates than the dense HK we
already record. Expect low classification lift.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Re-assess whether each of the four is still worth scheduling AFTER `AINOS3-111` lands — dropping `TBL_REG` as superseded is an acceptable outcome.
- [ ] `AC2` Scheduler-table entries added and the FSW tables rebuilt for whichever survive AC1.
- [ ] `AC3` Index-walking logic for `ES_APP` / `TBL_REG` so more than one app/table is ever observed.
- [ ] `AC4` Packets verified arriving at OnAIR live, and columns validated non-constant.
- [ ] `AC5` The added bus load measured, and the frame-rate baseline re-derived (it moves — see stage 4).

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
