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

- [ ] `AC1` `cs` vendored, built, loading, and its HK arriving at OnAIR — verified live.
- [ ] `AC2` Checksum tables authored for NOS3's actual app and table set, not a stock example.
- [ ] `AC3` Columns subscribed and validated non-constant, and NOT silently pruned from the CSV.
- [ ] `AC4` A deliberate corruption produces an observable miscompare — the detection demonstrated live, not inferred.
- [ ] `AC5` `CDH-GOLDEN` and the `EX-0004`/`EX-0005` verdicts re-assessed.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-09-01 · BUMPED — schema-freeze (AINOS3-124) prerequisite, the long pole of Stage 1

Owner decided CS is a **GO** before the schema freeze (`AINOS3-124`): freezing the recorded schema
without integrity columns and building CS afterward would force a full re-collect. So CS is
sequenced **ahead of** the freeze — `AINOS3-124 AC4` cannot publish the frozen schema until CS's
columns are built and **live-verified reaching OnAIR**. HS (`AINOS3-112`) and MM/MD (`AINOS3-113`)
were **NO-GO** (deferred to `schema-vNext`). The standing relationship is in the `blocks:`
frontmatter field; slot this into the sprint that precedes the Stage-2 rebuild.

### 2026-09-01 · Survey + feasibility de-risk (before any build)

Established the two things that decide whether this is tractable, and the answer is "yes, but with
a vendoring decision that is the owner's":

**1. There is no nasa-itc CS fork.** NOS3's standard apps are nasa-itc forks (`nasa-itc/SC`, `/LC`,
`/DS`, `/FM`, `/SCH`); `nasa-itc/CS` and `nasa-itc/CFS_CS` **do not exist**. Only mainstream
`nasa/CS` does. So CS cannot follow the established submodule pattern as-is.

**2. ✅ The big compatibility fear is unfounded.** NOS3's cFE is **`draco-rc5`** (modern), and its
nasa-itc DS already uses the **modern** API (`CFE_SB_ValueToMsgId`, `CFE_MSG_Init(CFE_MSG_PTR(...))`,
`*_Payload_t` nesting) — the *same* API mainstream `nasa/CS` uses. So CS is **not** a back-port to
an ancient cFE; it is a modern app on a modern base. DS is the concrete adaptation pattern.

**Concrete build plan (offline Phase A, then build, then live):**

- A1 vendor `nasa/CS` → `fsw/apps/cs`; adapt `mission_build.cmake`/`CMakeLists.txt` to NOS3 (pattern
  DS — expected minimal, both modern).
- A2 author the **four** NOS3 CS tables in `cfg/nos3_defs/tables/` — `cs_apptbl` (which of NOS3's
  ~13 apps + ~12 components to checksum), `cs_tablestbl` (which tables), `cs_eepromtbl`,
  `cs_memorytbl`. **This is the E5 risk** — it must match NOS3's *actual* app/table set (AC2).
- A3 add `cs` to `cfg/nos3_defs/targets.cmake`; move it **above the `!`** in `cpu1_cfe_es_startup.scr`;
  add a `CS_SEND_HK_MID` entry to the `sch` schedule table.
- B full FSW rebuild.
- C OnAIR wiring: `CS_HkPacket_t` struct in `message_headers.py` + `nos3_security_tlm.json` + the
  ini, `sbn_client.so` rebuild.
- D launch, verify CS HK reaches OnAIR (AC1/AC3), demonstrate a corruption→miscompare (AC4).

⚠ **Owner decision at A1 — how to vendor CS, since no nasa-itc fork exists:** (a) plain vendored
copy under `fsw/apps/cs` (simplest, NOS3 can patch freely, not upstream-tracked); (b) submodule
mainstream `nasa/CS` directly (pins upstream, but NOS3 patches have nowhere clean to live); (c)
fork `nasa/CS` into the org and submodule the fork (matches the nasa-itc pattern; needs a fork
only the owner can create). This is the one fork-in-the-road before hours of build work go in.

### 2026-09-01 · CS builds + installs in NOS3 (Phase A+B done)

The hardest integration risk is retired: **CS compiles and installs cleanly in the NOS3 cFS build.**

- Vendored `nasa/CS` **@draco-rc5** (option (a), plain copy) — version-matched to NOS3's cFE
  (`draco-rc5-7`). Mainstream HEAD uses the modern config-module (`generate_configfile_set`) that
  NOS3's build predates; the draco-rc5 tag is the DS-era structure that builds.
- `cs` added to `MISSION_GLOBAL_APPLIST` (`targets.cmake`).
- ⚠ **`configure.py` had a hardcoded startup-app list without cs** — patched to read
  `applications/cs/enable` (guarded for SC configs lacking `<cs>`) and move the cs line above the
  `!`. Matched on the **unique `CS_AppMain`** token, not `CS,` (which collides with `ADCS,`).
- `cs` enabled in `sc-mission-config.xml`.
- ⚠ Build gotcha recorded: the FSW build **must run in the `ivvitc/nos3-64` container** (needs
  NOSENGINE) via `make fsw`, not host `make build-fsw`; and the container `docker run -it` needs a
  TTY, so a non-interactive build must drop `-t` (`docker run --rm -i ... build-fsw`).

Result: `fsw/build/exe/cpu1/cf/cs.so` (158 KB) + `cs_{app,tables,eeprom,memory}tbl.tbl` installed;
cs sits **above the `!`** (line 12) in the installed `cfe_es_startup.scr`. Built with the app's
**default** tables (empty app table) — proving integration; the NOS3-specific tables (AC2) are next.

**Remaining:** launch + verify cs LOADS live (AC1) → OnAIR wiring for CS HK (AC1/AC3) → author NOS3
`cs_*` tables (AC2) → corruption→miscompare demo (AC4) → re-assess EX-0004/EX-0005/CDH-GOLDEN (AC5).

### 2026-09-01 · ✅ CS LOADS LIVE (AC1 first half — verified, not inferred)

Launched (`make launch-quiet`; GSW already up). `sc01-nos-fsw` cFS log:

```
CFE_ES_ParseFileEntry: Loading file: /cf/cs.so, APP: CS
EVS 42/1/CS 1: CS Initialized. Version 2.5.99.0
CS Apps Table verification results: good = 0, bad = 0, unused = 24
```

CS loads and initializes cleanly. Its four tables verify with **0 valid entries** — expected, the
app-default tables are empty; the NOS3-specific tables (AC2) will populate them. ⚠ An
`undefined symbol: SBN_TCP_Ops` line appears for cs.so **and** `generic_adcs.so` (and every app) —
a pre-existing SBN optional-ops probe, unrelated to CS.

**AC1 first half DONE.** Remaining: CS HK → OnAIR (AC1 second half + AC3), author NOS3 `cs_*`
tables (AC2), corruption→miscompare demo (AC4), EX-0004/EX-0005/CDH-GOLDEN re-assessment (AC5).

### 2026-09-01 · AC2 tables authored + CS HK scheduled (FSW side complete)

- **`cfg/nos3_defs/tables/cs_apptbl.c`** authored — checksums **23 NOS3 apps** (SCH CI TO CS CF DS
  FM LC SBN SC ADCS CSS EPS FSS NAV IMU MGR MAG RADIO RW ST THRUSTER TORQUER; idle lab stubs and
  the SAMPLE demo omitted; cFE core covered separately by `CS_CFECORE_CHECKSUM`). Build confirms
  the cFS MISSION_DEFS override works: *"Using file: cfg/build/nos3_defs/tables/cs_apptbl.c"*, and
  `xxd` of the installed `.tbl` shows `State=0x01 (ENABLED)` + the app names.
- **CS HK scheduled** — enabled the commented `CS_SEND_HK_MID` message (`sch_def_msgtbl.c` msg #6)
  and the `CS HK Request` activity (`sch_def_schtbl.c` slot #4, `SCH_DISABLED`→`SCH_ENABLED`). ⚠
  Build gotcha: `sch_def_msgtbl.c` never `#include`d `cs_msgids.h` (the CS line was commented) —
  added it.
- ⚠ **The init `good=0` app-table event is a red herring** — it fires once during CS registration
  (the empty default image, before `CFE_TBL_Load` reads the file). CS has been quiet since (0
  recurring "No valid entries" warnings), i.e. it loaded the 23-app file and is checksumming. The
  per-app state is confirmable only via CS HK → the OnAIR wiring (next).

FSW side of AINOS3-111 is complete: CS builds, loads, checksums the NOS3 apps, and is scheduled to
transmit HK (`CS_HK_TLM_MID 0x08A4`). **Remaining: OnAIR wiring** (subscribe 0x08A4, `CS_HkPacket`
struct, schema, ini, `sbn_client.so` rebuild) for AC1-2nd-half/AC3, then the corruption→miscompare
demo (AC4) and EX-0004/EX-0005/CDH-GOLDEN re-assessment (AC5).
