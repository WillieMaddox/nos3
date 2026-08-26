---
key: AINOS3-110
slug: build-missing-cfs-apps
type: Epic
epic: —
status: Open
priority: Medium
estimate: E 0 / T 0.0
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-110 — Build the missing stock cFS apps

**Summary:** Build the five stock cFS apps that NOS3 lists as available but neither loads nor builds.

## Description

`cfg/nos3_defs/cpu1_cfe_es_startup.scr` loads — and `sch_def_msgtbl.c` schedules housekeeping
for — five standard NASA cFS apps whose shared objects are **absent from
`fsw/build/exe/cpu1/cf/`** and whose source is not vendored: `cs`, `hk`, `hs`, `md`, `mm`.
They therefore never run.

Found by AINOS3-95, which traced several published out-of-scope verdicts to this single gap
rather than to a design limit. These are stock apps rather than something to invent, which
makes this the largest *and* the most tractable observability item on the board.

`hk` is deliberately excluded: its copy table (`cfg/nos3_defs/tables/hk_cpy_tbl.c`) only
repackages bytes from other apps' HK into combined packets, so it adds no observability we do
not already have directly.

⚠ The main cost is not vendoring the code — it is **authoring each app's configuration tables**
against NOS3's specific app set, since no `cs_*`, `hs_*`, `mm_*` or `md_*` table definitions
exist in `cfg/nos3_defs/tables/`.

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

- [ ] `AC1` Each child ticket lands with its app running, its HK arriving at OnAIR (verified live, not assumed from source), and its columns validated non-constant.
- [ ] `AC2` The out-of-scope verdicts this epic unblocks are re-tested rather than assumed re-openable.
- [ ] `AC3` Subscription cap headroom confirmed before the last app lands.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
