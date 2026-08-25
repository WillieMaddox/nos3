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
finding is true of the **build**, not the design. `cfe_es_startup.scr` **does** load `hs` and
the scheduler **does** request `HS_SEND_HK_MID` — there is simply no `hs.so`.

HS monitors application liveness (are apps checking in), CPU utilisation, event-message rates,
and **services the watchdog**, acting on failure via app restart or processor reset. Its HK is
the packet the two watchdog verdicts were declared unobservable for want of.

It also addresses the workbook's C&DH row 12 (CPU utilisation abnormally high), which is
currently unanswered.

⚠ The PSP watchdog on pc-linux is a no-op stub, so HS will service a timer that does nothing.
Whether HS's *own* monitor state is still a useful observable — independent of a functioning
timer — must be established rather than assumed.

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
