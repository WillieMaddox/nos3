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

⚠ **`AC1` and `AC4` rewritten 2026-08-25.** They originally read "add `cam-sim` to the headless
launch, or declare the payload out of scope" and "if `cam-sim` is added, re-subscribe
`CAM_HK`" — both of which presumed that starting the simulator would yield useful telemetry.
That was never tested, and static inspection says it would not: see `AC1`.

- [ ] `AC1` Establish whether an imagery payload is **modelled at all here, or only shelled**.
      The evidence to date says shelled, and the ticket should confirm or overturn it rather
      than assume: `CAM_Hk_tlm_t` is **two `uint8` counters** (`CommandCount`,
      `CommandErrorCount`) carrying no simulator data; the scheduler issues **zero** camera
      commands, so both sit at 0 in nominal ops indefinitely; and `CAM_EXP` `0x08C9` — the only
      packet with imagery-ish content (`msg_count`, `length`) — is initialised but **never
      transmitted**. If that holds, starting `cam-sim` headless changes nothing worth having.
- [ ] `AC2` The same question answered for `syn`, which is the clearer case — it has **no
      simulator anywhere** (absent from `launch.sh` and `nos3-simulator.xml`). Either one is
      written, or the app is declared unmodelled and dropped from the headless build so it
      stops loading inert.
- [ ] `AC3` A documented statement of any REMAINING difference between the headless and GUI
      telemetry surfaces, so future coverage claims name which stack they were verified on.
      ⚠ This is the criterion with lasting value: the two stacks not being equivalent is what
      let a coverage claim be verified on the wrong one.
- [ ] `AC4` A recorded **decision on whether `CAM_HK` is worth a schema slot**, on the evidence
      from `AC1` rather than on the fact that it is currently absent. **A documented "not worth
      it" is the expected outcome**, and is a complete answer — the payload rows in
      `SPARTA_LOGGING_GAP.md` then stay `NEEDS_FSW` permanently rather than provisionally.
- [ ] `AC5` If, contrary to `AC1`, the payload does turn out to be modelled: `CAM_HK`
      re-subscribed and **verified arriving live**, not assumed from the launch config.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
