---
key: —
slug: build-missing-cfs-apps
type: Epic
epic: —
status: Pending Jira key
priority: Medium
estimate: E 0 / T 0.0
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# build-missing-cfs-apps — Build the missing stock cFS apps

**Summary:** Build the five stock cFS apps that cfe_es_startup.scr loads and the build does not provide.

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

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Each child ticket lands with its app running, its HK arriving at OnAIR (verified live, not assumed from source), and its columns validated non-constant.
- [ ] `AC2` The out-of-scope verdicts this epic unblocks are re-tested rather than assumed re-openable.
- [ ] `AC3` Subscription cap headroom confirmed before the last app lands.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
