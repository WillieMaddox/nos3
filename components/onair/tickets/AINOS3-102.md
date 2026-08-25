---
key: AINOS3-102
slug: headless-sim-coverage-gap
type: Bug
epic: AINOS3-79 (detector-rigor)
status: Open
priority: High
estimate: E 2 / T 0.5
opened: 2026-08-25
sprints: [28]
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-102 — Payload sims absent from the headless launch

**Summary:** `cam-sim` launches only under the GUI `make launch`, so the imagery payload is invisible to every soak and corpus run; `syn` has no simulator at all.

## Description

Found while verifying AINOS3-95 stage 2b. `CAM_HK` `0x08C8` and `SYN_HK` `0x08FC` were
subscribed, deployed, and delivered **0 packets in 90 s** while `CF` delivered 20.

Root cause is the launch mode, not the flight software:

- **`cam-sim` is started only by the GUI path** — `cfg/build/launch.sh:124` launches it via
  `gnome-terminal`, which `make launch-quiet` never runs. Every soak, every corpus collection
  and every attack validation uses the headless path, so the `arducam` app loads with no
  simulator behind it and emits nothing.
- **`syn` has no simulator anywhere** — absent from `launch.sh` and from
  `cfg/build/sims/nos3-simulator.xml`. The app is permanently inert.

This matters beyond the two apps: it means the *headless* and *GUI* stacks do not expose the
same telemetry surface, so a coverage claim verified in one may be false in the other. The
corpus is built headless, so headless is the surface that counts.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Decide and record: add `cam-sim` to the headless launch, or declare the imagery payload out of scope and remove the app from the headless startup script so it stops loading inert.
- [ ] `AC2` The same decision made explicitly for `syn` — either a simulator is written, or the app is declared unmodelled and dropped from the headless build.
- [ ] `AC3` A documented statement of any REMAINING difference between the headless and GUI telemetry surfaces, so future coverage claims name which stack they were verified on.
- [ ] `AC4` If `cam-sim` is added headless, `CAM_HK` is re-subscribed and verified to arrive; `SPARTA_LOGGING_GAP.md` payload rows move back from `NEEDS_FSW`.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
