---
key: —
slug: build-hs-app
type: Story
epic: build-missing-cfs-apps
status: Pending Jira key
priority: Medium
estimate: E 5 / T 2.0
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# build-hs-app — Build the HS health and safety app

**Summary:** Build the HS (Health & Safety) app — the missing piece behind the EX-0012.11 / DE-0003.11 watchdog verdicts.

## Description

AINOS3-74 ruled `EX-0012.11` (modify watchdog) and `DE-0003.11` (watchdog state for evasion)
out of scope because no watchdog or health telemetry exists. AINOS3-95 sharpened that: the
finding is true of the **build**, not the design. the scheduler **does** request `HS_SEND_HK_MID`, and `hs` is listed in
`cfe_es_startup.scr` — but below its `!` terminator, so it is never loaded, and there is no
`hs.so` either.

HS monitors application liveness (are apps checking in), CPU utilisation, event-message rates,
and **services the watchdog**, acting on failure via app restart or processor reset. Its HK is
the packet the two watchdog verdicts were declared unobservable for want of.

It also addresses the workbook's C&DH row 12 (CPU utilisation abnormally high), which is
currently unanswered.

⚠ The PSP watchdog on pc-linux is a no-op stub, so HS will service a timer that does nothing.
Whether HS's *own* monitor state is still a useful observable — independent of a functioning
timer — must be established rather than assumed.

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

- [ ] `AC1` `hs` vendored, built, loading, HK arriving at OnAIR — verified live.
- [ ] `AC2` Application-monitor and event-monitor tables authored for NOS3's app set.
- [ ] `AC3` Established whether HS monitor state is meaningful given the PSP watchdog stub — a documented negative is a valid outcome.
- [ ] `AC4` Columns subscribed and validated non-constant.
- [ ] `AC5` Feeds `retest-reopened-verdicts` for EX-0012.11 / DE-0003.11.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
