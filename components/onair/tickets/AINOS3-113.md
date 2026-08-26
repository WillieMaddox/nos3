---
key: AINOS3-113
slug: build-mm-md-apps
type: Story
epic: AINOS3-110 (build-missing-cfs-apps)
status: Open
priority: Medium
estimate: E 5 / T 2.0
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-113 — Build the MM and MD memory apps

**Summary:** Build MM and MD — the standard cFS answer to 'log the memory register and the new value', which 12 of 13 workbook sheets ask for.

## Description

The workbook's single most-repeated instruction is *"log memory register and new value along
with time tag"*, appearing on **12 of the 13 subsystem sheets**. We answer it today only as
"a command counter incremented" — we never see the register or the value.

MM (Memory Manager) executes commanded peeks, pokes, loads and dumps and reports the last
address, action and byte count; MD (Memory Dwell) periodically samples commanded addresses and
telemeters them. Together they are the standard cFS carrier for that recommendation, and both
are listed in the startup script's disabled block, with scheduled HK and no `.so`.

Unblocks re-assessment of `EX-0012.01` (registers).

⚠⚠ **This ticket has a security trade-off that must be decided explicitly, not inherited from
"build the missing apps".** MM gives an attacker a *supported memory-write path* — which is
why `EX-0012.03` (memory writes) is a SPARTA technique in the first place. Building it adds
observability and attack surface together. That is defensible for a security testbed, and
arguably increases fidelity to real spacecraft, but it should be an explicit decision with the
reasoning recorded.

⚠ **Premise corrected 2026-08-25 (via `AINOS3-102`).** An earlier revision said these apps are
"loaded in `cfe_es_startup.scr` and simply have no `.so`". **Both halves were wrong about the
loading.** `cfe_es_startup.scr` has an end-of-file terminator — cFS stops parsing at the first
`!`, on line 33 of 91 — and `cs`, `hk`, `hs`, `md`, `mm` (with `arducam` and `syn`) appear
**only below it**, so they are **not loaded at all**. Verified: all seven emit zero EVS init
events, while every app above the `!` loads. Entries below the `!` that *do* run are duplicates
of ones listed above.

The script states the design: *"In NOS3, these are moved as part of the `make config` process
depending on what is enabled."* The below-`!` block is the **catalogue of disabled apps**.

**So enabling one needs TWO changes, not one:** build the `.so` **and** move its entry above
the `!` (or make `make config` do so). Budget accordingly — the second half was invisible in
the original scoping.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` The attack-surface trade-off decided explicitly and recorded, BEFORE the app is built.
- [ ] `AC2` `mm` and `md` vendored, built, loading, HK arriving — verified live.
- [ ] `AC3` Dwell tables authored for addresses that are actually security-relevant, not a stock example.
- [ ] `AC4` Columns subscribed and validated non-constant.
- [ ] `AC5` `EX-0012.01` re-assessed; feeds `AINOS3-119`.
- [ ] `AC6` If MM is built, the new attack path is itself added to the attack corpus so we detect what we just enabled.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
