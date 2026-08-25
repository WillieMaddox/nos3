---
key: —
slug: build-mm-md-apps
type: Story
epic: build-missing-cfs-apps
status: Pending Jira key
priority: Medium
estimate: E 5 / T 2.0
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# build-mm-md-apps — Build the MM and MD memory apps

**Summary:** Build MM and MD — the standard cFS answer to 'log the memory register and the new value', which 12 of 13 workbook sheets ask for.

## Description

The workbook's single most-repeated instruction is *"log memory register and new value along
with time tag"*, appearing on **12 of the 13 subsystem sheets**. We answer it today only as
"a command counter incremented" — we never see the register or the value.

MM (Memory Manager) executes commanded peeks, pokes, loads and dumps and reports the last
address, action and byte count; MD (Memory Dwell) periodically samples commanded addresses and
telemeters them. Together they are the standard cFS carrier for that recommendation, and both
are already in the startup script with scheduled HK and no `.so`.

Unblocks re-assessment of `EX-0012.01` (registers).

⚠⚠ **This ticket has a security trade-off that must be decided explicitly, not inherited from
"build the missing apps".** MM gives an attacker a *supported memory-write path* — which is
why `EX-0012.03` (memory writes) is a SPARTA technique in the first place. Building it adds
observability and attack surface together. That is defensible for a security testbed, and
arguably increases fidelity to real spacecraft, but it should be an explicit decision with the
reasoning recorded.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` The attack-surface trade-off decided explicitly and recorded, BEFORE the app is built.
- [ ] `AC2` `mm` and `md` vendored, built, loading, HK arriving — verified live.
- [ ] `AC3` Dwell tables authored for addresses that are actually security-relevant, not a stock example.
- [ ] `AC4` Columns subscribed and validated non-constant.
- [ ] `AC5` `EX-0012.01` re-assessed; feeds `retest-reopened-verdicts`.
- [ ] `AC6` If MM is built, the new attack path is itself added to the attack corpus so we detect what we just enabled.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
