---
key: AINOS3-102
slug: headless-sim-coverage-gap
type: Bug
epic: AINOS3-79 (detector-rigor)
status: Done
priority: High
estimate: E 2 / T 0.5
opened: 2026-08-25
closed: 2026-08-25
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

- [x] `AC1` **ANSWERED — shelled, on the software bus.** See the log entry below.
      The evidence to date says shelled, and the ticket should confirm or overturn it rather
      than assume: `CAM_Hk_tlm_t` is **two `uint8` counters** (`CommandCount`,
      `CommandErrorCount`) carrying no simulator data; the scheduler issues **zero** camera
      commands, so both sit at 0 in nominal ops indefinitely; and `CAM_EXP` `0x08C9` — the only
      packet with imagery-ish content (`msg_count`, `length`) — is initialised but **never
      transmitted**. If that holds, starting `cam-sim` headless changes nothing worth having.
- [x] `AC2` **ANSWERED** — see the log. `syn` needs no simulator (its library is built) but never initialises either, and its device packet is commented out. Originally scoped as — it has **no
      simulator anywhere** (absent from `launch.sh` and `nos3-simulator.xml`). Either one is
      written, or the app is declared unmodelled and dropped from the headless build so it
      stops loading inert.
- [x] `AC3` **ANSWERED** — see the log. A documented statement of any REMAINING difference between the headless and GUI
      telemetry surfaces, so future coverage claims name which stack they were verified on.
      ⚠ This is the criterion with lasting value: the two stacks not being equivalent is what
      let a coverage claim be verified on the wrong one.
- [x] `AC4` **DECIDED — not worth a slot.** See the log. Originally: a recorded decision on whether `CAM_HK` is worth a schema slot, on the evidence
      from `AC1` rather than on the fact that it is currently absent. **A documented "not worth
      it" is the expected outcome**, and is a complete answer — the payload rows in
      `SPARTA_LOGGING_GAP.md` then stay `NEEDS_FSW` permanently rather than provisionally.
- [x] `AC5` **N/A — `AC1` was not overturned.** Originally: if the payload does turn out to be modelled, `CAM_HK`
      re-subscribed and **verified arriving live**, not assumed from the launch config.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-08-25 · AC1 ANSWERED — the imagery payload is shelled, and it is an FSW gap not a launch gap

Traced through `components/arducam/fsw/cfs/src/cam_app.c`. The app is **not** a pure stub —
it really does talk to a simulator and really does read image bytes:

- It initialises hardware interfaces (`CAM_init_i2c`, `CAM_init_spi` at `:409-435`) through
  `hwlib`, i.e. it is wired to `cam-sim`.
- `CAM_HWLIB_READ_PREP_CC` calls `CAM_read_prep((char *)&CAM_AppData.Exp_Pkt.data, …)`
  (`:465`), genuinely reading image data into the experiment packet.
- `Exp_Pkt` is initialised with `CAM_EXP_TLM_MID` at `:200`.

**And then it is never published.** The only `CFE_SB_TransmitMsg` in the entire app is the
housekeeping packet at `:501`. `CAM_PUBLISH_CC` (32) is **defined in `cam_msg.h` and has no
handler** in the command switch — it falls through to the invalid-command-code branch.

So image data is read into a packet that has no code path onto the software bus: not
scheduled, not commanded, not published anywhere. ⚠ **This reframes the whole ticket.** The
original diagnosis — "`cam-sim` is GUI-launch only" — is true but is the *second* problem.
Even with `cam-sim` running headless, `0x08C9` would still never appear, because the FSW never
sends it. Adding the sim to the headless launch would fix nothing on its own.

What `0x08C8` (HK) would carry with the sim running is unchanged from the earlier assessment:
two `uint8` counters, `CommandCount` / `CommandErrorCount`, with **zero** scheduled camera
commands — so constant 0 in nominal ops.

**Bearing on `AC4`:** the expected "not worth a schema slot" outcome is now the evidenced one.
Subscribing `CAM_HK` buys two constant counters; the packet that would carry actual payload
signal cannot be subscribed at all until someone writes a publish path. The
`SPARTA_LOGGING_GAP.md` payload rows stay `NEEDS_FSW`, and the FSW work required is
**larger than a launch-script edit** — it is a missing `TransmitMsg` and a missing command
handler.

### 2026-08-25 · AC2 ANSWERED — neither payload app starts at all; three distinct faults, not one

Checked which apps actually initialise in the running FSW: **30 apps emit EVS init events, and
neither `SYN` nor `CAM` is among them.** No load error is logged either — they fail silently
before reaching their own init event. Everything below sits *behind* that.

Peeling the layers apart, because the ticket's original one-line diagnosis ("cam-sim is
GUI-launch only") turned out to be the outermost of three:

1. **Neither app initialises.** Not a launch-mode issue — `syn` needs no simulator container
   at all and still does not start.
2. **Neither publishes its payload packet, even if it did start.** `CAM`'s `Exp_Pkt` is
   populated with real image bytes and never transmitted, and `CAM_PUBLISH_CC` (32) is defined
   with **no handler**. `SYN`'s device packet is worse — its `CFE_MSG_Init` is **commented
   out** (`syn_app.c:170-172`), so `0x08FD` is never even initialised.
3. **What remains is two `uint8` counters each**, with zero scheduled commands to move them.

⚠ `syn` is *not* the simpler case I called it earlier. It has **no simulator interface by
design** — no hwlib, no i2c/spi, no socket — because SYNOPSIS is an on-board data-processing
library, and **`libsynopsis.so` is built and present**. The app calls
`itc_app_get_memory_requiremennt()`, `itc_setup_ptasds()` and `itc_app_init()` — real work,
not a stub. So "write a simulator for syn" was the wrong framing: there is nothing to
simulate, and the gap is that the app does not run and does not publish.

**Both `AC1` and `AC2` therefore land on the same answer**: the payload apps are shelled *at
the telemetry layer*, and the fault is in the FSW, not the launch script. Adding `cam-sim` to
the headless launch — the change this ticket was opened to make — would fix none of the three
layers.

### 2026-08-25 · AC3 — the headless/GUI difference, and what it is worth

The measurable difference is narrower than feared: `cam-sim` is the only simulator started by
`make launch` (`launch.sh:124`, `gnome-terminal`) and not by `make launch-quiet`. But per
`AC1`, its absence is not what makes the imagery payload invisible — the missing publish path
is. **No telemetry currently reaching OnAIR under the GUI launch is absent under the headless
launch**, because the packet that would differ is never sent under either.

⚠ The lasting point stands and is why `AC3` was worth keeping: the two stacks are **not
guaranteed equivalent**, and a coverage claim verified on one may be false on the other. That
is how the retracted "payload sheets are subscribable now" claim happened. Future coverage
claims should name the stack they were verified on; today that is `make launch-quiet`, which
is what every soak and corpus collection uses.

### 2026-08-25 · AC4 DECIDED — `CAM_HK` is not worth a schema slot; AC5 N/A; ticket DONE

**Decision: do not subscribe `CAM_HK` `0x08C8`.** On the `AC1`/`AC2` evidence this is not a
close call:

- The app does not initialise, so the packet does not flow at all today.
- If it did, it carries **two `uint8` counters** with **zero** scheduled camera commands —
  constant 0 in nominal ops.
- The packet that would carry actual payload signal, `CAM_EXP` `0x08C9`, has **no publish path
  in the FSW** and so cannot be subscribed at any price.

⚠ And subscribing it is not free. `AINOS3-108` established today that the deployed IsolationForest
binds its feature set by column **name**: adding columns is safe, but every added column is one
the next model inherits, and removing one later is a **retrain**, not a config edit. Spending
two slots on constant-zero counters is a commitment, not an experiment.

`AC5` is **N/A**: it was the contingency for `AC1` being overturned, and `AC1` held.

**`SPARTA_LOGGING_GAP.md` payload rows stay `NEEDS_FSW`** — now permanently rather than
provisionally, and with the FSW work correctly characterised. It is **not** a launch-script
edit: it is an app that does not start, a missing `TransmitMsg`, and a missing command handler.

**What this ticket actually established.** It was opened to fix a launch-script omission. That
omission is real but was the outermost of three faults, and the least important:

1. neither payload app initialises at all;
2. neither publishes its payload packet even if it did;
3. `cam-sim` is GUI-launch only.

Fixing (3) alone — the entire original scope — would have changed nothing observable, and we
would have concluded the payload was covered. ⚠ The general lesson is the same one that
retracted the "payload sheets are subscribable now" claim: **verify a telemetry path end to end
against a running stack before treating its absence as a configuration problem.**

**Follow-on, not done here:** if imagery-payload coverage is ever wanted, the work is a
`syn`/`arducam` app-startup fix plus a publish path for `0x08C9` — FSW work of a different
size to this ticket, and worth its own item if the SPARTA Payload sheets ever become a
priority.
