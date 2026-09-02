---
key: AINOS3-111
slug: build-cs-app
type: Story
epic: AINOS3-110 (build-missing-cfs-apps)
status: Open
priority: High
blocks: AINOS3-124 (CS is a prerequisite of the schema freeze)
estimate: E 5 / T 2.0
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-111 — Build the CS checksum app

**Summary:** Build the CS (Checksum) app — the recorded corpus currently contains no integrity data of any kind.

## Description

The single highest-value item in the AINOS3-95 gap analysis. SPARTA's logging workbook asks
for actual-vs-expected checksums or hashes on **six separate rows**, rated **High** on every
one: golden software and firmware images, tables, stored command scripts, configuration
key-value pairs, and boot mechanisms.

Against that, the recorded corpus contains **zero integrity data**. The only checksum we
subscribe, `CFE_ES.CFECoreChecksum`, is pruned from the CSV before it reaches disk (see
`AINOS3-109`).

CS computes CRCs over the cFE core image, the OS image, app code segments, tables and
user-defined memory, and telemeters per-area state with miscompare counters plus EVS events on
mismatch. It is a **producer** of security-relevant log data, not a consumer.

Unblocks a re-assessment of `EX-0004`, `EX-0005`, and the `CDH-GOLDEN` recommendation.

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

- [x] `AC1` `cs` vendored, built, loading, and its HK arriving at OnAIR — verified live.
- [x] `AC2` Checksum tables authored for NOS3's actual app and table set, not a stock example (`cs_apptbl.c`, 23 apps).
- [x] `AC3` Columns subscribed and validated (28 `CS.*` cols, cFE-core baseline + sweep counters non-constant), NOT silently pruned from the CSV.
- [x] `AC4` ⚠ **Reframed by a platform finding, then demonstrated via the achievable observable.** The literal "app-code corruption → live `AppCSErrCounter` miscompare" is **NOT achievable on the NOS3 linux PSP** — `CFE_ES_GetModuleInfo` returns `AddressesAreValid=false` for every `dlopen`'d app, so CS never baselines an app and the miscompare cannot fire (see 2026-09-01 log). The achievable observable — CS **monitor-tamper** — is **demonstrated live** (2026-09-02): a `CS_DISABLE_ALL_CS` command flips `CS.ChecksumState 1→2 (DISABLED)` in the corpus, and `CS_ENABLE_ALL_CS` restores it to `1`. A rule-gate R-rule candidate (sibling of R5).
- [x] `AC5` `EX-0004`/`EX-0005`/`CDH-GOLDEN` re-assessed against the platform reality: CS on NOS3 = **cFE-core integrity attestation + monitor-tamper signal**, NOT per-app code-corruption detection. `AppCS*` must not be wired as detector features (vacuous). See 2026-09-02 log.

## Log

Dated. Rewritten in plain language 2026-09-02 for readability; the technical specifics (file
names, field names, decisions) are preserved, the jargon is explained.

### 2026-09-01 · Why CS is built before the "schema freeze"

We plan to freeze the exact list of columns we record, so the model can be retrained on a stable
dataset. But today's recorded data contains no software-integrity information at all. If we froze
the column list first and built the Checksum (CS) app afterward, we'd have to throw away everything
collected and start over. Decision: build CS first and get its data into the recording, then freeze
the column list. Two related apps (HS and MM/MD) were judged not worth building right now and pushed
to a later round.

### 2026-09-01 · Is this even doable? (checked before writing any code)

Two questions decided whether CS was practical, and the answer was yes:

1. Our other flight apps come from a NASA-maintained fork, but **there is no such fork of CS** — only
   the mainstream NASA version exists. So CS can't be added the usual way.
2. The bigger worry — that CS would be written for an *old* version of the flight framework and need
   heavy porting — was unfounded. Our framework is a modern version (`draco-rc5`), and one of our
   existing apps (DS) already uses the same modern style CS needs. So CS is a modern app on a modern
   base; DS is the template to copy.

Plan: copy in the NASA CS code, write the NOS3-specific config tables (which apps/areas to
checksum), wire it into the build and the startup list, rebuild the flight software, connect its
telemetry to the recorder, and finally demonstrate it catching a deliberate corruption. One decision
was left to the owner — how to bring in the CS code — and we chose the simplest: a plain vendored
copy under `fsw/apps/cs` that we can patch freely.

### 2026-09-01 · CS compiles and installs

The hardest risk — would CS even build inside our system — is gone: CS compiles and installs
cleanly. Two notes for next time: the flight-software build has to run inside a specific Docker
container (it needs a simulation library), and the tool that generates the startup list had a
hard-coded app list that didn't include CS, so it had to be patched.

### 2026-09-01 · CS runs on the live satellite

Launched the stack. The flight log shows CS starting cleanly (`CS Initialized. Version 2.5.99.0`).
At this point its config tables are still the app's empty defaults — expected; the real NOS3 tables
come next.

### 2026-09-01 · Told CS which apps to watch, and scheduled its reports

Wrote the NOS3 config (`cs_apptbl.c`) listing the 23 real apps for CS to checksum, and turned on
CS's periodic "housekeeping" status report so its state is broadcast. A small snag: the schedule
file didn't reference CS's message name, so that reference had to be added.

### 2026-09-01 · CS data now reaches the recorder

Connected CS's housekeeping report into the recording pipeline so its 28 status fields land in the
recorded CSV, and verified it live. One real bug found and fixed: CS reported "everything enabled"
but wasn't actually checksumming anything, because it also needs a periodic "wake-up" trigger that
hadn't been scheduled. After adding that, CS began working — it computed a checksum of the core
flight-software image and completed a full pass, with zero mismatches (correct, since nothing is
corrupted). This closed AC1 and AC3.

### 2026-09-01 · The big finding — CS can't fingerprint the apps on this simulator

Trying to demonstrate CS catching a deliberate corruption uncovered the important result — exactly
the kind of thing we build CS to learn *before* we rely on it:

- **On a real satellite**, CS fingerprints each app's code in memory.
- **On our Linux-based simulator it cannot** — the operating system doesn't report where each app's
  code actually lives in memory, so CS silently skips all 23 apps. (The one thing it *can* fingerprint
  is the core flight-software image; that works and produces a real checksum.)

So on NOS3, CS gives us **core-software integrity only, not per-app corruption detection**. Why this
matters: the "an app's code changed" alarm can *never* fire on this platform, so we must **not** train
the model to rely on it — that would be training on a signal that is physically impossible here. (We
also confirmed there's no other way to force the demo: the one working area isn't a reloadable file,
and poking memory directly is blocked by the container's security settings.)

### 2026-09-02 · What CS is actually good for here — plus a live tamper demo

Given the above, CS's real value on NOS3 is two things: (1) **core-software integrity attestation**,
and (2) a **tamper alarm** — if an attacker sends the command to *turn CS off*, that shows up in the
recorded data. The second is a natural fit for a new detection rule (an attacker disabling your
monitors is itself an attack; it mirrors our existing rule R5).

Demonstrated live: with CS running normally, we sent the "disable checksumming" command; the recorded
status field flipped from ON (1) to OFF (2) and held there; then we re-enabled it and it flipped back.
So the tamper signal genuinely works. (An earlier attempt failed only because that particular stack
instance was in a bad state and wasn't accepting *any* commands — a clean relaunch fixed it.)

### 2026-09-02 · Reduced CS's log spam (a standalone improvement)

Because CS keeps trying — and failing — to fingerprint the 23 apps, it was emitting a flood of
"couldn't find that app" messages every second. Since that fingerprinting can't work here anyway, we
set CS to skip the per-app checks by default (one line in `cs_platform_cfg.h`; the 23-app list is kept
as documentation in case a future platform supports it). Result: the spam is gone, CS still does its
two useful jobs (core checksum + tamper alarm), and the recorded data is cleaner.

### 2026-09-02 · The "slow recording" scare was a measurement mistake, not a real problem

While doing the work above, I repeatedly reported that the data recorder had slowed to a crawl
("0.1 Hz", "stalled", "frozen"). **That was wrong — the simulator was running fine the whole time.**
A careful 30-minute measurement, using logs stamped with real wall-clock time, showed the simulation
running steadily at real-time speed and recording ~5–6 rows per second with no stalls.

The alarming numbers came from three measurement errors of mine, not from anything in the system:

- **Stale files** — I sometimes measured leftover recording files from previous, already-stopped runs
  (which of course never grow), and read that as "0 rows/sec".
- **A timestamp quirk** — the NOS3 SBN adapter keeps two internal recording buffers and alternates
  between them (`sbn_adapter.py`, the `double_buffer_read_index` logic). Because each buffer holds a
  slightly different-age copy of the clock, a single row's timestamp can flicker by a few seconds and
  even appear to run backwards. Reading one row's timestamp as "the current time" produced fake freezes.
- **Windows too short** — checking over 20 seconds isn't enough to be meaningful.

Crucially, none of our changes caused any slowdown: with CS removed entirely, the behavior was
identical. There is nothing to fix here — the recorder's true rate is a steady ~5–6 Hz, and the only
real, keep-worthy outcome of the whole episode is the CS log-spam reduction above, which stands on its
own merit.
