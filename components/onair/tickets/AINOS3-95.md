---
key: AINOS3-95
slug: sparta-logging-gap-analysis
type: Spike
epic: AINOS3-41 (coverage-expansion)
status: Done
priority: High
opened: 2026-08-11
sprints: [27, 28]
---

# AINOS3-95 — SPARTA logging best practices vs what we record

**Summary:** As a defender, I want SPARTA's *Space Vehicle Logging Best Practices* mapped against the telemetry we actually record, because the binding constraint on this project is **observability** (AINOS3-69) and this is an authoritative, technique-indexed list of what a spacecraft *should* be logging.

## Description

Sourced from SPARTA's Indicators-of-Behavior page
(<https://sparta.aerospace.org/related-work/iob>): a guide PDF plus a **~20-sheet workbook**,
both in `data/sparta/` (git-ignored — Aerospace Corporation's to distribute; re-download from
the IOB page). Two distinct payoffs, and they should not be conflated:

1. **Consistency.** Our logging method changed repeatedly across the project, leaving a mix
   of formats and field sets. The guide gives an external standard to normalise against
   rather than an internally-invented one.
2. **Coverage.** The workbook indexes recommended log sources **by SPARTA technique**. Any
   row naming telemetry we don't currently subscribe to is a concrete observability lead —
   exactly what AINOS3-88 concluded we lack, and it arrives already tied to techniques
   rather than guessed at.

Every sheet must be read. A partial pass would most likely miss the sheets that matter,
since the useful content is the technique↔log-source mapping, not the prose.

**The artifact, measured** (2026-08-23) — `data/sparta/Space_Vehicle_Logging_Best_Practices-Distro_A.xlsx` is **19 sheets but only ~330 data
rows**: 13 subsystem sheets (Propulsion, ADCS, EPS, GN&C, C&DH, TT&C, SMS, TCS, Payload ×5)
at 11–38 rows × 10 cols each, plus `SPARTA_Mapping` — the technique ↔ log-source index —
at 78 rows × 7 cols, and five reference/metadata sheets. Reading it is half a day; the work
is cross-referencing against our 382-column schema. Expect the 5 Payload sheets to be **not
modelled by NOS3**; read them anyway and record that verdict, because "not modelled" is a
legitimate and reusable answer.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` All ~20 sheets reviewed; a one-line purpose recorded for each so the next reader can skip
      to the relevant one.
- [x] `AC2` A gap table: recommended log source → do we record it (yes / inconsistently / no) → which
      MID would carry it if not.
- [x] `AC3` Recommended sources split into **subscribable now** (a MID exists on the bus),
      **needs FSW work**, and **not modelled by NOS3**, with a count for each.
- [x] `AC4` Any technique currently marked out-of-scope/UNSUBSCRIBED in `V5_DETECTOR_COVERAGE.md`
      that the workbook says *is* loggable is flagged explicitly — those are re-openable verdicts.
- [x] `AC5` Feeds AINOS3-69's observability constraint and the AINOS3-45 corpus decision; does **not**
      itself subscribe anything.
- [x] `AC6` *(added 2026-08-25)* The live signal path is measured, not assumed: frame rate vs message
      rate, per-MID arrival rates, and which subscribed MIDs are silent or pruned before the CSV.
- [x] `AC7` *(added 2026-08-25)* The highest-ranked lead is **implemented and validated end-to-end**
      rather than left as a recommendation.
- [x] `AC8` *(added 2026-08-25)* The zero-subscription lead (GPS-vs-FSW time discrepancy) is
      built as a rule with its detection floor measured, not asserted.
- [x] `AC9` *(added 2026-08-25)* Stage-2b subscriptions are driven by what actually reaches OnAIR
      in the headless pipeline, verified live — not by what the source says *should* transmit.
- [x] `AC10` *(added 2026-08-25)* The rate-derived detector thresholds are re-baselined against the
      settled schema, and the soak that does it is long enough to expose rare-event failure modes.
- [x] `AC11` *(added 2026-08-25)* Every coverage verdict this ticket changed or corrected is
      reflected in the stakeholder overlay, and the remaining work is queued as tickets rather
      than left in this ticket's prose.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.

### 2026-08-25 · ready to start — workbook verified readable, inventory taken

`openpyxl` 3.1.5 opens `data/sparta/Space_Vehicle_Logging_Best_Practices-Distro_A.xlsx`
(warns harmlessly about print-area defined names). Verified inventory, so the read can be
planned rather than discovered:

| sheet | rows × cols | note |
|---|---|---|
| `Index & Acronyms` | 52 × 23 | reference |
| `Content of Log Records` | 10 × 5 | reference — what a log record should contain |
| Propulsion · ADCS · EPS · GN&C | 11 / 15 / 15 / 15 × 10 | **`EPS` feeds AINOS3-87; `ADCS`+`GN&C` feed AINOS3-86** |
| C&DH · TT&C | 38 / 31 × 10 | largest subsystem sheets |
| SMS · TCS | 12 / 12 × 10 | |
| Payload — Imagery/RF/OCT/Data Processing/Hosted | 21/34/21/14/14 × 10 | expect **not modelled by NOS3**; read and record that verdict |
| `SPARTA_Mapping` | 79 × 8 | **the technique ↔ log-source index — the point of the artifact** |
| `SPARTA_Mapping_Abstract`, `REF_Info`, `Change_Log` | 6 / 8 / 4 | metadata |

~393 rows across 19 sheets. The read is half a day; the work is cross-referencing against our
382-column schema. `AC4` — techniques currently marked out-of-scope / UNSUBSCRIBED that the
workbook says *are* loggable — is the one criterion that can turn a red cell green, so treat
it as the headline rather than an afterthought.


### 2026-08-25 · DONE — all 5 ACs; 12 subscribable-now leads, 6 re-openable verdicts

Report: [`SPARTA_LOGGING_GAP.md`](../SPARTA_LOGGING_GAP.md). Two committed scripts make it
re-derivable from a fresh download of the (git-ignored) workbook:
`extract_logging_workbook.py` (19 sheets → JSON) and `sparta_logging_gap.py` (the
cross-reference). The mapping is a judgement, encoded the way `gen_nos3_coverage.py` encodes
the coverage matrix, but three properties are machine-checked so it cannot rot silently:
every workbook recommendation claimed exactly once, every named column present in
`nos3_security_tlm.json`, every verdict internally consistent.

**`AC1`** — 19 sheets, 280 data rows, **122 distinct recommendations**, one-line purpose
each. ⚠ The predicted "all 5 Payload sheets not modelled" is **wrong for two of them**: this
build loads and schedules `arducam` (`CAM_HK_TLM` 0x08C8, `CAM_EXP_TLM` 0x08C9) and `syn`
(0x08FC/0x08FD) — small packets, but the static-in-nominal counter shape R6–R13 exploits.

**`AC2`/`AC3`** — 97 canonical rows: **16 recorded · 36 partial · 45 not recorded**. Of the
81 unmet, **42 not modelled by NOS3 · 27 needs-FSW · 12 subscribable now**.

The headline is the *kind* of gap: the workbook is an **event-audit** standard, ours is a
**periodic-sample** recorder. Its most repeated instruction — log the register and the new
value on a config change — we answer with "a counter incremented", which is exactly what the
rule-gate family exploits. Our detector's *shape* is externally validated; its *content* is
not. A second structural limit no MID closes: 15 recommendations ask for a **source
subsystem**, and the cFS Software Bus is anonymous publish/subscribe.

⚠ Also found: `cfe_es_startup.scr` loads and the scheduler requests housekeeping for **`cs`,
`hk`, `hs`, `md`, `mm`** — none of which have a `.so` in `fsw/build/exe/cpu1/cf/`, so they
do not run. That is the largest needs-FSW cluster and the cheapest, since they are stock cFS
apps. `cs` alone would answer the workbook's six **High**-rated integrity/hash rows against
our one recorded checksum.

**`AC4`** — 11 of our 28 out-of-scope/UNSUBSCRIBED techniques carry a named log source in
`SPARTA_Mapping`; **6 are genuinely re-openable**, the rest are honest statements about this
build. Best two:

- **`EX-0001.01`** — our verdict answers a question the standard does not ask. We said
  "replayed commands are byte-identical"; `C&DH` row 13 proposes **counter reconciliation
  against the ground's own count**. We hold every spacecraft-side counter; the missing half
  is a join to COSMOS, not a MID.
- **`EX-0006` / `PER-0004`** — we ruled them out on CryptoLib's *state* being invisible;
  `TT&C` rows 22–24 ask for the **command** (bypass / key-change / disable-encryptor), which
  is the R6–R13 signal. Re-openable as rule candidates, not subscriptions.

`EX-0012.11` / `DE-0003.11` / `EX-0012.01` re-open **only if** someone builds the missing
apps — `AINOS3-74`'s finding was right about the build, and is now stated more precisely
(`hs` *is* loaded and *is* scheduled; there is no `hs.so`). The workbook independently marks
`EX-0010.03`/`.04` data type **`N/A`**, corroborating those two verdicts.

**`AC5`** — nothing subscribed, two hand-offs:

- **`AINOS3-87`**: the `EPS` sheet answers its negative branch. The workbook's named EPS
  signal is **change in power consumption**; `GENERIC_EPS_Hk_tlm_t` carries **five voltages
  and zero currents**. The switch toggle cannot move a consumption feature because the schema
  has none — a structural explanation for the measured −0.4 IF lift, and evidence for the
  "reclassify UNSUBSCRIBED, name the missing field" branch.
- **`AINOS3-86`**: `GENERIC_ADCS_AC_MID` **0x0944** is published, downlinked and
  unsubscribed, and carries the INERTIAL controller's own gains and error state (`Kp`, `Kr`,
  `Ki`, `phiErr_max`, `qbn_cmd`, `therr`, `sumtherr`, `werr`, `qErr`, ~63 scalars). The
  per-mode IF is currently solving an attitude-control problem without the controller's error
  terms. Top-ranked of the 12 leads.

The concrete edit list — which files, which structs, which tables — is
[`SPARTA_LOGGING_GAP.md` § What to add or modify](../SPARTA_LOGGING_GAP.md#what-to-add-or-modify).
⚠ Checked while writing it: `CFE_SBN_CLIENT_MAX_MSG_IDS_PER_PIPE` is **48** and we subscribe
**37**, so all nine candidate MIDs fit without the `sbn_client.so` rebuild `AINOS3-70` needed.

Cheapest find, costing no subscription: the `GN&C` sheet names **time-interval discrepancy**
as a GPS-spoof indicator, and we already record GPS time and FSW time in the same frame
without ever comparing them. A GPS-vs-MET divergence feature is a derived column over data in
hand, targeting `EX-0014.01`/`.04`/`EX-0016`.

### 2026-08-25 · AC6 — the live signal path, measured (stage 0)

`components/onair/training/measure_frame_rate.py`, two independent windows on the deployed
stack. **20.3 msg/s in, 5.5 frames/s out — a 27 % ratio.** `sim.py` has no rate limiter, so
5.5 Hz is the plugin chain's compute ceiling.

⚠ **This reverses the hazard this ticket first published.** More MIDs do **not** raise the
frame rate; the loop is compute-bound, not arrival-bound. The risk inverts — added *columns*
make each frame more expensive and can lower the rate. A re-baseline of `AINOS3-92`'s Hz and
of the rate-derived thresholds (rule-gate **R2**, staleness advance-interval) is still
required, for the opposite reason.

⚠ **73 % of messages never surface as their own frame** — overwritten in the write buffer
before it is read. Pre-existing, but it means the staleness gate's "average advance interval"
measures **OnAIR's loop rate, not the FSW's publish rate**. Deserves its own ticket.

⚠ **Two ways a subscribed column is not a recorded one**, both now hard-checked by
`sparta_logging_gap.py`:

- **4 MIDs subscribed but silent** — `CFE_SB_SUBS`, `SBN`, `RADIO_DEV`, `ST_DEV`.
- **23 of 382 `order` columns never reach the CSV** — the format-v2 prune drops non-numeric
  and static-version fields. Live plugins can read them; nothing trained on the corpus can.

Six gap-table rows moved as a result, two from `PARTIAL` to `NO`. The sharpest: **`CDH-GOLDEN`
→ `NO`.** `CFE_ES.CFECoreChecksum` is pruned, so the recorded corpus holds **no integrity data
of any kind** — the earlier "we record exactly one checksum" was wrong, and this is now the
strongest argument for building the `cs` app. Counts: **16 YES · 34 PARTIAL · 47 NO**.

### 2026-08-25 · AC7 — lead 1 implemented and validated (stage 2a)

`GENERIC_ADCS_AD_MID` **0x0942** and `GENERIC_ADCS_AC_MID` **0x0944** subscribed: **+37 CSV
columns** (382 → 419 in `order`, 359 → 396 in the CSV), 39 of the 48 subscription cap. No
`sbn_client.so` rebuild needed. Both were already on the bus at **1.00 /s** — CC 3-7
(DI/AD/GNC/AC/DO) are all scheduled in `sch_def_msgtbl.c`, so only the subscription was
missing.

⚠ **`order` is not a free-form list — its tail must be the 6 derived `CFE_TBL` columns.** The
CSV writer pairs labels to values *positionally* (`current_buffer[i]`), labels come from
`subsystems` sorted by `order`, and values come from the struct walk, which appends the
derived columns last. Appending the new columns after them shifted every new field. Caught by
validation (a `uint8` showing a 3-double array, `Tcmd*3` showing 4 elements), not by any test.
Fixed by moving the derived columns back to the tail; walk order and header now verified
identical.

**All 37 columns populate, with correct array widths.** In SUNSAFE the active controller's
error state (`Sunsafe.werr`, `Sunsafe.Tcmd`) varies and the gains are constant — which is the
point, since a *gain that moves* is the attack signal the ADCS/GN&C sheets rate High.

**🔑 The finding that matters more than the columns.** In INERTIAL the error state was
**all zero across 124 frames**. Cause, traced to source: `AC_inertial()` is wrapped in
`if (GNC->qValid)` (`generic_adcs_adac.c:338`), and the chain is

`ST.DeviceEnabled=0` → `ADCS_DI.Payload.St.valid=0` → `ADCS_AD.ST.Valid=0` →
`ADCS_GNC.qValid=0` → **the INERTIAL control law never executes at all.**

Commanding `GENERIC_STAR_TRACKER_ENABLE` (0x1935 FC2) flips `qValid` to 1 and the whole error
state comes alive — `therr`, `qErr`, `werr`, `Tcmd` vary, and **`sumtherr` shows real
integrator wind-up (-17.9, +28.3)**, the observable this ticket argued for. Lead 1 is
validated, but **conditionally**: it is worth nothing while the star tracker is disabled.

**Two tickets are affected and neither is mine to close:**

- **`AINOS3-86`** — its A/B design already requires enabling the star tracker; this supplies
  the *mechanism* for why, and raises a prior question its plan does not ask: if INERTIAL
  soaks ran with `qValid=0`, the vehicle was in "INERTIAL mode" with **no control law
  running**, and a 33.6 % false-alarm rate against uncontrolled drift may be a **configuration
  artifact rather than a detector problem**. That should be settled before any tuning.
- **`AINOS3-91`** — "5 constant `ST_DEV` fields" is not inert telemetry. The MID is silent
  because the device is disabled; enabling it starts 0x0936 transmitting.

⚠ **Stack state left dirty.** Mode restored to SUNSAFE, but the **star tracker is now
ENABLED**, which the pre-existing corpus baseline was not. Run `make stop` + `make
launch-quiet` before any soak or measurement.

### 2026-08-25 · AC8 — R15 gps-time-divergence built; the "cheapest lead" was not cheap

The `GN&C` sheet names *"time interval discrepancy"* as a GPS-spoof indicator, and this ticket
promoted it as **the cheapest find — a derived column over data already in hand**. Measured,
that framing was wrong, and the reason is worth more than the rule.

**The naive version is unusable.** On a clean stack the raw per-frame divergence
`GPS − MET` has a **29 s spread** (stdev 5.8). Cause: OnAIR's double buffer corrupts **both**
operands — `NOVATEL.SecondsIntoWeek` steps **backward 58 times** in 3 minutes, and
`CFE_TIME.SecondsMET` oscillates between two values ~4 s apart in adjacent frames. Ruled out
in order: MET staleness does **not** explain it (corr = **−0.055**, and subtracting the
estimated staleness makes the spread marginally *worse*), and splitting frames by row parity
does not separate the buffers (20.3 s / 29.0 s).

⚠ **The general lesson, which outlives this rule:** *any* derived feature that differences
**two different MIDs** inherits both their buffer histories. That is why the only existing
derived features (AINOS3-30's `CFE_TBL` change-detect) are **within-MID**. Cross-MID features
need the monotonic-envelope treatment or they need computing at message-arrival time.

**What works** is the trick the consistency-check gate already uses for counters: compare the
**monotonic envelope** (running max) of each clock instead of the instantaneous values.

| | spread | stdev |
|---|--:|--:|
| raw per-frame difference | 29.0 s | 5.84 |
| running-max envelope | **5.0 s** | **1.19** |

The 5 s residual is a sawtooth whose amplitude is the `CFE_TIME` **arrival period** (~4 s at
0.25 /s) — the MET envelope only steps on a `CFE_TIME` message while GPS updates 3.6 /s.

**Threshold 9.0 s**, ~1.8× the measured floor. Detection floor, established by injecting jumps
into the recorded nominal series: **≥10 s detected, ≤5 s invisible**. Both directions work,
by different mechanisms — a forward jump moves the GPS envelope, a backward jump *freezes* it
while the MET envelope keeps climbing. The ≤5 s blind spot is pinned by a test so it cannot be
quietly overstated later; it is acceptable because the `SET_TIME` attacks this targets
(`EX-0014.01`, `EX-0012.12`) set arbitrary, large times.

**No drift.** Over a 2,273-frame (~7 min) nominal window the quarter means are flat
(−2.167, −2.154, −2.168, −2.162 s) — an earlier apparent +2.75 s drift was sawtooth phase, not
clock drift. Max deviation from the warmup baseline **5.0 s vs the 9.0 s threshold**, so a
fixed threshold does not creep into a false positive.

**Built:** `R15:gps-time-divergence` in the rule-gate plugin, labelled cluster `EX-0014.01` /
`gps-met-divergence`, registered only when all five clock fields are present, and ignoring
`Weeks == 0` (an unacquired receiver, not a clock at the GPS epoch). **9 new tests, 67 pass.**
Deployed and running: **0 fires over 1,589 live frames** (~5 min) on a clean stack — a nominal
false-positive check, not a detection claim.

### 2026-08-25 · AC8 live validation — and the bug the live attack exposed

Fired a real `SET_TIME` (`0x1805` FC 7, `secs=200000000`) against the live FSW. **The first
version of R15 did NOT fire** — and that miss is the whole reason evaluation-provenance is a
rule on this project.

**The bug.** cFE `SET_TIME` adjusts **STCF**, not the free-running **MET**: observed live,
`CFE_TIME.SecondsSTCF` jumped `0 → 199,999,092` while `SecondsMET` kept counting `913 → 917`.
R15 watched `SecondsMET` alone, so it was blind to the exact attack it was built for. The
nominal FP soak passed because STCF is 0 in nominal ops, and the offline injection passed
because it moved the GPS series — neither exercised the STCF path. **A green offline result
and a green nominal soak, and the rule still missed the live attack.**

**The fix.** The FSW clock is **MET + STCF** (what `CFE_TIME_GetTime` returns). R15 now
envelopes `GPS` against `MET + STCF`, which catches all three time-attack vectors — `SET_TIME`
(STCF), `SET_MET` (MET), and GPS spoof (GPS). A regression test feeds the exact live footprint
(STCF steps, MET free-runs). 10 R15 tests, **68 pass**.

**Re-validated on a clean stack** (`make stop` + `launch-quiet`; baseline `STCF=0`, 0 pre-attack
fires past warmup). Fired the same `SET_TIME`; the FSW accepted it (`Set Time -- secs =
200000000`) and:

- **R15 fired at frame 189 — the attack frame — with 0 fires across frames 0-188.** Clean edge,
  no false positives before, 561 consecutive active frames after.
- The alert names the technique: `rule=R15:gps-time-divergence … (EX-0014.01 / EX-0012.12)`,
  cluster `EX-0014.01`.

**AC8 now satisfies evaluation-provenance: a live TP, not a closed-by-construction claim.**

⚠ **Design note / limitation.** The running-max envelope means a *forward* clock jump **latches
the alert until the session resets** — the FSW-clock envelope never comes back down, so the
incident stays open. This is correct for a persistent clock offset (the clock IS wrong until
reboot), but a single latched incident could mask a later, different attack in the same
session. Whether to re-baseline after N frames is a follow-up decision, not fixed here.

⚠ **Stack left with a corrupted clock** (`STCF ≈ 2e8`) by the validation; reset with `make
stop` + `launch-quiet` before further work.

### 2026-08-25 · AC9 — stage 2b: CF subscribed; CAM/SYN proven inert and removed

Original 2b scope was 9 MIDs. Source inspection then live verification cut it to **one**, and
the cuts are the finding.

**Cut from source inspection (before any deploy):**

- `CAM_EXP` `0x08C9` — `Exp_Pkt` is initialised but never `TransmitMsg`'d.
- `SYN_DEV` `0x08FD` — transmit is commented out (`syn_app.c:172`).
- `SB_STATS` `0x080A` — command-produced, **0 scheduler entries**. Same class as the three
  diag packets already deferred; I had wrongly kept it in the "clean" bucket. It needs the FSW
  scheduler rebuild and moves to the deferred pile with `ES_APP`/`TBL_REG`/`SB_ONESUB`.

**Cut from LIVE verification (the point of the step):** `CAM_HK` `0x08C8` and `SYN_HK`
`0x08FC` were subscribed, deployed, and delivered **0 packets in 90 s** while `CF` delivered

20. Root cause traced:
- `cam-sim` launches **only via the GUI `make launch`** (`launch.sh:124`, `gnome-terminal`),
  never via headless `make launch-quiet` — the pipeline that runs every soak and corpus. So the
  arducam app loads but has no sim to talk to and emits no HK.
- `syn` has **no simulator anywhere** — absent from `launch.sh` and `nos3-simulator.xml`. The
  app is permanently inert.

⚠ **This overturns an AINOS3-95 gap-analysis claim.** The AC1/AC3 write-up said NOS3 runs two
payload apps that make `Payload - Imagery` and `Payload - Data Processing` "subscribable now."
In the headless recording pipeline they are **not** — CAM only under the GUI launch, SYN not at
all. `SPARTA_LOGGING_GAP.md` needs that correction (batched with the deferred coverage edits).
General lesson, now proven twice: *scheduled + downlinked + transmitted in source ≠ arriving at
OnAIR* — the sim has to exist in the launch mode you actually run.

**Kept: `CF_HK` `0x08B0`** — pure-software CFDP, no hardware sim, so it runs headless. +55
columns (474 in `order`, 451 in the CSV after the 23-col prune; 40 channels, under the 48 cap
— no `sbn_client.so` rebuild). Layout verified live: `channel0.q_size = [0,0,0,0,0,256,50]`
places the CFDP free-list sizes (256 history-free, 50 free) in exactly the right slots — proof
the nested `_pack_=1` layout is byte-correct, since a misalignment would scramble them.

⚠ **CF is 55 columns that are near-entirely idle in nominal** (no file transfers running):
counters and fault fields all 0, only the static queue-config values non-zero. `audit_dead_columns.py`
will flag them — expected, not a bug. Unlike CAM/SYN this is *quiescent-but-valid*: the fault
counters (`crc_mismatch`, `file_write`, …) are static-in-nominal and would latch under
`EX-0010` (wiper/ransomware) or `EXF` file activity — R6-family rule candidates for a future
sprint. CF earns its place as a dormant detector surface, not as a live feature today.

Net stage-2b outcome: **1 of 9 MIDs subscribed** (CF), 2 proven inert and removed, 6 deferred
or dropped. The value delivered is the *elimination* — 8 MIDs that source alone would have said
were fine, kept out of the corpus.

### 2026-08-25 · AC10 — stage 4 rebaseline, and the R15 false positive it caught

Stage 4's purpose was to re-derive the rate-dependent thresholds after the schema settled
(359 → 451 CSV columns). It did that — and, far more valuable, **the longer soak caught a
false-positive mode in R15 that three earlier validations all missed.**

**⚠ The R15 false positive.** On a 3,344-frame nominal window, R15 fired on **2,420
consecutive frames**. Root cause: **two spurious NOVATEL samples** (`Weeks` 341 → 43387, then
43563, with `SecondsIntoWeek` 150240 → 731) — torn packet reads. The **running-max envelope
latched the garbage permanently**, pushing the divergence 26 billion seconds high and pinning
the rule on for the rest of the session.

The design flaw stated plainly: a running max absorbs *backward* flicker but is **maximally
vulnerable to a single forward outlier**. Every prior R15 validation had passed —
0 FP over 963 frames, 0 FP over 2,273 frames, 0 FP over 1,589 live frames, and a clean live
TP — because none of those windows happened to contain a torn read at ~2-in-3,344. **Rare-event
failure modes need soak length, not more test cases.**

**Fix:** median-filter both clocks over `TimeDivergenceMedianFrames` (default 5, forced odd)
*before* the envelope sees them. An isolated torn read is rejected; a real time shift is
sustained and passes through after ⌈N/2⌉ frames — negligible against the 8-frame `CmdDwell`.
Replayed against the **actual CSV that produced the failure**:

| algorithm | FP frames |
|---|--:|
| raw running max (as deployed) | **3,231 / 3,911** |
| median-3 | 0 |
| median-5 (chosen) | **0** |

⚠ A scoping bug in the first version of that patch (`gps`/`met` unbound when the field-validity
check fails → `NameError` every frame with no GPS fix) was caught before deploy and is pinned
by `test_r15_survives_frames_with_no_gps_fix`. Two regression tests added (torn read, no-fix
frames); **70 rule-gate tests pass.**

**Re-validated live, in order:** 0 R15 fires and **0 fires of ANY rule** across **2,050**
nominal frames on the fixed build; then a live `SET_TIME` fired R15 at frame **2,153** — the
attack frame — with 0 pre-attack fires. The median cost no detection.

**Rebaseline results (the stage's original scope):**

- **Frame rate 6.06 /s wall-clock; 5.87 Hz derived from MET** (the `AINOS3-92` method), vs the
  published **5.6**. ⚠ Do not attribute the change to the schema: message rate rose exactly
  +3.0 /s as expected (`ADCS_AD` + `ADCS_AC` + `CF`, 1.00 /s each), but frame rate is
  **compute-bound and varies with host load and stack uptime**, and the two measurements were
  taken at different uptimes. The honest statement is that **5.6 is stale; 5.87 is current**,
  and any uptime-binned analysis should re-derive rather than inherit either.
- **R2 (`EvsRateThreshold` = 15):** measured max EVS delta **1 per frame** (mean 0.058),
  headroom 14. No retune. ⚠ The known long-uptime RADIO-EVS-spam mode (~61/frame) is unchanged
  by this work and still argues for fresh-launch incident validation.
- **Staleness gate:** self-calibrated correctly on the new schema — 126 counter candidates, of
  which it watches **5 wide liveness counters**, "all live" through frame 3000. CF's 55 idle
  zero-counters are excluded automatically by the `wide(max>256)` filter, so **stage 2b did not
  perturb it**. No retune.

⚠ **Stack left with a corrupted clock** (`STCF ≈ 2e8`) by the TP re-validation; reset before
further work.

### 2026-08-25 · AC11 — coverage corrections applied; 15 tickets queued; CLOSING

**Coverage overlay (`app/gen_nos3_coverage.py`) — 9 techniques changed, overlay regenerated:**

- **2 red → green.** `EX-0012.12` and `EX-0014.01` are now gate-detected by **R15**,
  live-validated against a real `SET_TIME`. ⚠ Applying this exposed a **latent bug in the
  generator**: its `GATE_DETECTED` loop did `if tid in coverage: continue`, silently discarding
  the gate for any technique the classifier already scores. Both of these are scored in
  `ENRICH`, so R15's catch would never have surfaced. A technique can be **both** scored and
  gate-detected; the loop now merges instead of dropping.
- **7 rationale corrections** (`EX-0001.01`, `EX-0006`, `PER-0004`, `EX-0012.11`, `DE-0003.11`,
  `EX-0012.01`, `EX-0012.13`) — the verdicts stand, the stated *reasons* were wrong or narrower
  than the workbook. Purple `UPDATED` markers set on all 9.

**Gap analysis corrected — and the headline number moved: 16/34/47 → `17 YES · 29 PARTIAL ·
51 NO`, subscribable-now `12 → 5`.** Two corrections drove it:

- **Retraction.** The claim that `arducam` and `syn` made the payload sheets "subscribable now"
  is **withdrawn** — both proved inert in the headless pipeline. The ticket's original
  prediction (all 5 payload sheets not modelled) was right after all.
- **Staleness.** Rows citing `0x0944`/`0x0942`/`0x08B0` as future leads now reflect that stages
  2a/2b **subscribed** them. `GEN-CTRLLOGIC` moves to **YES** — the ADCS gains are recorded —
  with the honest caveat that **nothing rules on them yet**.

**Remaining work: 15 tickets in `tickets/pending/`**, in execution order —
`headless-sim-coverage-gap`, `detect-cf-file-faults`, `detect-adcs-gain-change`,
`test-encryption-bypass-observability`, `r15-latch-policy`, `frame-aliasing-semantics`,
`subscription-hygiene`, `csv-prune-integrity-fields`, `build-missing-cfs-apps` (epic) +
`build-cs-app` / `build-hs-app` / `build-mm-md-apps`, `schedule-cfe-diag-packets`,
`retest-reopened-verdicts`, `ground-counter-reconciliation`. **E ≈ 45 · T ≈ 12.5.** Run
`check_ticket_docs.py --pending` for the Jira-creation queue.

**Related tickets updated:** `AINOS3-86` (INERTIAL may be a configuration artifact),
`AINOS3-91` (ST_DEV silent because the device is disabled), `AINOS3-87` (negative branch
answered; missing field named), `AINOS3-92` (5.6 Hz stale → 5.87, and schema-dependent).

### What this ticket actually delivered, honestly

The spike was scoped to *read a workbook and write a gap analysis*. It did that — but the
durable value turned out to be **four corrections to things we believed**, three of which were
this project's own published claims:

1. `EX-0001.01` / `EX-0006` / `PER-0004` were ruled out for reasons that answer questions
   SPARTA does not ask.
2. The watchdog/register verdicts are **build** gaps, not design limits — the apps are loaded
   and scheduled, just not compiled.
3. The corpus contains **no integrity data at all**; the one checksum we subscribe is pruned
   before it reaches disk.
4. `AINOS3-91`'s "inert star-tracker fields" and `AINOS3-86`'s INERTIAL false-alarm floor both
   trace to **configuration** (device disabled, `qValid` gating the control law), not detector
   quality.

⚠ And the method that produced them is worth more than the findings: **every claim that
survived was one that had been checked live.** Source inspection passed CAM/SYN; a green test
suite, a nominal soak and an offline injection all passed R15 while it was watching the wrong
clock field, and later while a torn read could latch it on. Three separate times, the live
check was the only thing that caught the error.

**Status: DONE.** ACs 1-11 satisfied.

### 2026-08-25 · ⚠ correction to the AC9 entry above — `cam-sim` is not GUI-only

The stage-2b entry above attributes CAM's silence to *"`cam-sim` launches only via the GUI
`make launch` (`launch.sh:124`)"*. **That is wrong**, and `AINOS3-102` established why: the
headless path runs `scripts/fsw/launch_sat_quiet.sh`, not `launch.sh`, and it **does** start
`cam-sim` (line 136). The sim starts, reads `nos3-simulator.xml`, finds
**`<active>false</active>`** for `camsim`, and exits; `DFLAGS` carries `--rm`, so the container
is auto-removed leaving no trace and no logs.

Left above rather than edited, since this log is append-only and the wrong inference is part
of the record. **The AC9 conclusion is unaffected** — CAM and SYN were correctly removed from
the schema, and remain so: `AINOS3-102` decided against subscribing `CAM_HK` on the separate
and still-valid ground that it carries two `uint8` counters with zero scheduled commands, and
that `CAM_EXP` has no publish path at all.

⚠ The generalisation in that entry — *scheduled + downlinked + transmitted in source does not
mean arriving at OnAIR* — stands, and is if anything stronger: the sim was launched and still
produced nothing. Full detail in [`AINOS3-102`](AINOS3-102.md).
