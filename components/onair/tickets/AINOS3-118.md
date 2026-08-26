---
key: AINOS3-118
slug: stix-guided-attack-generation
type: Story
epic: AINOS3-41 (coverage-expansion)
status: In Progress
priority: Medium
estimate: E 5 / T 2.0
opened: 2026-08-26
origin: AINOS3-96 (sparta-stix-ingest)
---

# AINOS3-118 — Generate and repair attack scripts from STIX IOB patterns

**Summary:** Use the IOB patterns as a formal spec to build attacks for uncovered vectors and repair the 18 partial scripts AINOS3-96 found — pattern-guided, not title-guided.

## Description

Every attack script predates the STIX install and was written from technique **titles**. The 855
IOB patterns are a formal spec of what each technique should *produce*, driving both new scripts
and repairs to weak ones — turning the `sparta-attack-script` skill from title-guided to
pattern-guided. Two workstreams, both fed by `AINOS3-116` + `AINOS3-115`:

1. **New attacks for uncovered vectors.** The index lists, per technique, the IOB patterns our
   script does *not* exercise — each a concrete missing vector. Where the pattern's arguments map
   to observables we record, it is buildable now; the owner notes this may make some
   `not-applicable` / `out-of-scope` techniques achievable by naming exactly what a working attack
   must move.
2. **Repair the 18 `partially-implements` scripts** from `AINOS3-96`: EX-0014.03/.04 *disable*
   sensors where the pattern demands *false-data injection*; EX-0014.01 *sets* system time where
   the pattern demands a *spoofed GPS input*. The pattern says what a faithful implementation does.

⚠ **Evaluation-provenance applies without exception.** A regenerated script is not done until
live-validated against the FSW (`/sparta-attack-test`) — the rule that cost this project a full
re-derivation once. A paper match with no footprint is not an attack.

⚠ **Large, open-ended** — 18 repairs plus unknown new vectors. Slice per technique/family; this is
an epic seed, not one change.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` A prioritised list of buildable missing vectors (arguments that map to recorded observables), distinct from those needing observability work first.
- [x] `AC2` The EX-0014.01 repair as the first slice and exemplar: a script spoofing the NOVATEL GPS time input (via the `ci_lab` republish path), producing a GPS-time-anomaly footprint EX-0012.12 cannot — live-validated, confirming R15 actually catches it (closing the `AINOS3-96` 'recorded ≠ works' caveat).
- [ ] `AC3` Each repaired/new script live-validated via `/sparta-attack-test`; paper-only matches do not count.
- [ ] `AC4` For scripts that cannot produce their pattern's footprint, a recorded reason (observability gap vs not-modelled), feeding `AINOS3-117`.
- [ ] `AC5` Sliced into reviewable per-technique units.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

⚠ **Depends on** `AINOS3-116` and `AINOS3-115`. AC2 (EX-0014.01) is buildable earlier — its observables are already known.

### 2026-08-26 · Slice 1 (EX-0014.01) — spec derived, mechanism confirmed, LIVE INJECTION BLOCKED

Progress on the first slice, and an honest blocker. ⚠ **AC2 is NOT met** — no live TP claimed.

**Delivered:**

- **The exact spec, parser-derived.** Using the `stix2patterns` library (available; the owner
  flagged it) instead of regex, EX-0014.01's unique IOBs parse to precise comparisons:
  GNTM-5 `sensor-data:timestamp != expected AND time:delta_value != expected`, GNTM-9
  `gnss:delta_time < 0`, GNTM-10 `sensor-data:rewind_detected = true`. The parser cleanly
  separates **selectors** (`=` on a literal, e.g. `sensor_type='gps_time'`) from **measures**
  (`!=`/`<`), which is exactly the AINOS3-116 limitation. So the repair target is unambiguous:
  **move the NOVATEL GPS time itself** (a rewind/discrepancy), NOT the FSW clock — a footprint
  EX-0012.12's `SET_TIME` (which moves STCF, leaving NOVATEL untouched) cannot produce.
- **Mechanism confirmed in source.** `ci_lab_app.c:342-348`: CI_LAB reads any UDP packet on
  :5012 and calls `CFE_SB_TransmitBuffer` — it republishes whatever StreamId it receives. This
  overturns the stale `ex_0014_02_bus_traffic_spoofing.md` ("out of scope"), consistent with
  the AINOS3-95 finding. Confirmed live: a command (CFE_ES NOOP, 0x1806) sent to :5012 IS
  republished and processed.

**⚠ The blocker — CI_LAB republishes commands but injected TELEMETRY does not reach OnAIR.**
Built a byte-exact spoofed NOVATEL device packet (0x0871, 12B tlm header + 74B payload, time
moved forward), flooded it at ~25/s to beat R15's median-5 filter. Decisive test: in an 8 s
window **88 real 0x0871 packets reached OnAIR and the spoofed `Weeks=999` value appeared 0
times** — the injected packet is not forwarded to OnAIR, with no CI_LAB ingest/send error
logged. The command path (0x1806) works via the same port, so CI_LAB is alive and republishing;
something specific to the telemetry packet (CFE_MSG validation of the tlm secondary header, or
SBN not re-forwarding a CI_LAB-origin telemetry MID) drops it before OnAIR. 4 focused attempts;
stopped rather than grind.

**Next steps for this slice (not done here):**

1. Determine why a CI_LAB-republished telemetry MID does not reach OnAIR via SBN when the real
   one does — likely the tlm secondary-header format, or an SBN forward filter on origin.
2. The AINOS3-95 memory records a *working* spoof demo (spoofed IMU_HK seen by OnAIR); recover
   that packet format — it encodes the header this manual attempt is getting wrong.
3. The `/sparta-attack-test` skill may carry a working injection harness; try it before more
   hand-rolling.

**Concrete follow-up for AINOS3-116 (separate):** retrofit `stix_iob_index.py`'s `--coverage` to
use `stix2patterns` instead of regex — it resolves the AND/OR and selector-vs-measure
limitations recorded there. The parser is the right substrate for the whole STIX program.

**No stack state changed** — the injected packets never reached the SB, and no SET_TIME was
fired.

### 2026-08-26 · Slice 1 (EX-0014.01) — UNBLOCKED, AC2 DONE (clean live TP)

The block above was wrong on two points, both now fixed. The mechanism works; **AC2 is met.**

**The two root-cause bugs in the earlier attempt:**

1. **Wrong telemetry-header size.** This NOS3 build uses a **16-byte** cFS telemetry
   header (6 B CCSDS primary + 10 B secondary), so the CCSDS length field is `total-7`.
   The first attempt used a 12-byte header (`\x00*6`) and length `payload+secondary-1` —
   the packet was malformed and CI_LAB/SBN dropped it silently. Verified against the live
   stream: `Message Header ... StreamID: 0x871 ... Length: 0x53` (= 83 = 90-7), and against
   the demonstrated `GENERIC_IMU_Hk` spoof format ([[project_ex0014_02_bus_spoof]]).
2. **A verification artefact, not a real failure.** `sbn_adapter.py:246` prints each
   message's fields, but for NOVATEL the *nested* `Novatel_oem615` struct prints as an
   object repr — `Weeks:` **never appears in stdout**. Grepping stdout for the spoofed
   value could not have found it regardless of success. The correct check is the recorded
   **CSV column**, which expands the nested field.

**Clean, provenance-valid live TP (the actual repaired script, fresh stack):**

- Reset stack (`make stop` + `launch-quiet`); confirmed R15 **= 0** through frame 265.
- Ran `ex_0014_01_time_spoof.py --mechanism gps-spoof --offset 86400` (forge NOVATEL
  0x0871 GPS time +1 day via CI_LAB :5012, flood 120/s to beat R15's median-5).
- **R15 fired at the injection edge**: frame 266 `,0,0` → **267 `R15:gps-time-divergence,1,1`**
  (rising edge) → sustained 183 frames. R15's label maps to **EX-0014.01** (plugin line ~272).
- The spoofed `SecondsIntoWeek=236830` **dominated** the recorded NOVATEL column (111 rows,
  the top value) vs the real ~150324 — the forged GPS time is what OnAIR records.

This is the footprint **EX-0012.12 cannot produce**: `SET_TIME` moves STCF (the FSW clock)
and leaves the NOVATEL receiver untouched; this moves the GPS input itself (the GNTM-5/9/10
IOBs), and the FSW clock is never commanded. Closes the `AINOS3-96` "recorded ≠ works" caveat
for the GPS-time observable — R15 provably catches a real forged-GPS attack.

**The repair, committed:** `ex_0014_01_time_spoof.py` gains a `--mechanism {set-time,gps-spoof}`
switch. `set-time` is the old EX-0012.12-identical path; `gps-spoof` is the new IOB-faithful
mechanism with `build_novatel_device_tlm()` (16-byte header, 74-byte little-endian payload
mirroring `NOVATEL_OEM615_Device_Data_tlm_t`). Self-heals — the real receiver overwrites the
spoof once flooding stops, so no cleanup phase.

**Incident-label note (honest):** R15's running-max envelope stays **latched** after a forward
spoof (by design — the max never comes down), which keeps the incident **open**, so the
aggregator does not flush an `EX-0014.01` incident row without a stack reset. The detector catch
is unambiguous; the incident-flush-under-latch is a separate incident-layer behavior, not part
of this AC.

**AC3** partially satisfied for this one script (live-validated). AC1/AC4/AC5 and the other 17
repairs remain — this slice is the exemplar the rest follow.

### 2026-08-26 · Slice 2 (EX-0014.04 PNT) — repaired to a real position spoof; DETECTOR GAP found (AC4)

Second slice, and a more valuable result than a clean catch: a validated **gap**.

**The repair.** EX-0014.04 previously only *disabled* the receiver (the old "NOS3 can't do RF
GNSS" premise, now overturned by slice 1). Added `--mechanism {disable, pnt-spoof}`: `pnt-spoof`
forges the NOVATEL navigation solution (0x0871 via CI_LAB :5012) with an ECEF offset, the
faithful **GNTM-11** footprint (`gnss:delta_position > expected`). Reuses the slice-1 builder.

**Live-validated that it lands.** Fresh stack (SUNSAFE). The spoofed position dominated the
recorded column — `ECEFX = 2884000` (= 2384000 + 500 km) in **179 of the last 400 rows**. The
injection works exactly like the time spoof.

**But the deployed v5 IF does NOT catch it — validated, not assumed.**

- Static +500 km spoof (20 s, 120/s): **0 IF anomalies**; score 0.057–0.123, all normal
  (threshold −0.000025).
- Continuous walk-off ramp (ECEFX 2.38 M → 4.68 M, +50 km/packet sawtooth → a large delta
  *every* frame): **0 IF anomalies**; score 0.058–0.122.
- No rule-gate rule covers position (R15 is time-only); consistency-check is monotonic-counter
  only. **All four gates miss it.**

This directly contradicts the `features.py` design intent ("PNT spoof jumps out as a large
delta"). NOVATEL ECEF/Vel are delta-only-kept precisely to catch this, yet a 400× nominal
position delta does not move the score. Leading hypothesis: the training corpus carries torn
NOVATEL reads (the same double-buffer tears that pin R15 as an FP), so large ECEF deltas were
learned as "normal" and the feature is desensitized. Alternatives: near-zero position-delta
importance in the SUNSAFE per-mode head, or a normalization that clips the delta.

**Recorded for AC4 / feeds AINOS3-117 + the Sprint-29 retrain:** EX-0014.04 is *buildable and
injectable* but *undetected*. The fix is a retrain action, not an attack-script fix — either
exclude torn NOVATEL reads from training so position-delta stays sensitive, or add a dedicated
position-consistency primitive (per-sample delta_position > physical bound). This is a concrete,
named observability/detector gap, which is exactly the AC4 output.

**Provenance caveat:** measured in SUNSAFE on one stack; the retrain analysis should confirm the
torn-read hypothesis and check the other three per-mode heads.

### 2026-08-26 · Slice 3 (EX-0014.03 Sensor Data) — repaired; MARGINAL IF catch; completes the EX-0014 contrast

Third slice. Repaired EX-0014.03 from sensor-*disable* to a real IMU data fabrication
(`--mechanism sensor-spoof`: inject 0x0926 with an out-of-range `AngularAcc` via CI_LAB :5012,
the DISE-9/11 / SMSR-1 footprint), overturning its "full data fabrication is out of scope" note.

**Propagation confirmed.** The ADCS app copies IMU `AngularAcc` straight into
`ADCS_DI.Payload.Imu.wbn` 1:1 (verified: the two are byte-identical at baseline). `wbn` **is** a
v5 IF feature, so — unlike a masked NOVATEL position — a forged IMU rate reaches the IF. The
spoofed value took `wbn` in 63/300 rows during the ad-hoc probe.

**Marginal but real IF catch — honestly characterised, not oversold.** Baseline 0% anomalies;
during injection the IF score dips clearly negative (−0.0130 to −0.0169, below the −0.000025
threshold) and flags anomaly frames — but only **1–7 frames (~0.6–1.8%)**, a contiguous burst,
not a sustained alert. Cause: the double-buffer flicker means the spoofed `wbn` holds for only a
fraction of frames, so the IF sees brief discontinuities rather than a sustained regime shift.
The dynamics IF is tuned for *sustained* physics perturbations (a thruster firing, a real
tumble), and an injected-telemetry flicker only marginally crosses its threshold. A defensible
TP by provenance (clean baseline, score demonstrably anomalous during the window), but weak.

**The EX-0014 family now tells one coherent detector-coverage story** (all three sub-techniques
repaired + live-validated):

| technique | spoof target | reaches a detector? | result |
|---|---|---|---|
| EX-0014.01 | GPS **time** | rule-gate R15 (time-divergence) | **strong TP** (latched) |
| EX-0014.03 | IMU **rate** (dynamics) | IF via `ADCS_DI.Imu.wbn` | **marginal TP** (1–7 frames) |
| EX-0014.04 | GPS **position** (masked) | none | **gap** (AINOS3-97 AC6) |

**Organising principle for AC1:** a telemetry spoof is IF-detectable only if its target
propagates to a **non-masked, non-desensitised model feature** the IF weights in that mode —
and even then, flicker caps the strength. Directly-recorded-but-non-feature MIDs (IMU_DEV
itself, 0 features) only matter if they propagate (IMU→wbn does; position stays masked). This
is the buildable-vs-detectable filter AC1 needs, now grounded in three live data points.

**AC3:** 3 scripts live-validated (.01/.03/.04). **AC5:** 3 slices done. AC1 groundwork above;
the other ~15 partial-script repairs remain.

### 2026-08-26 · Slice 4 (EX-0012.03/04/05 table-load family) — TRIAGE to AC4 (footprint limit, not a script defect)

Investigated the CFE_TBL LOAD/ACTIVATE partials (EX-0012.03 memory-write, .04 subscriber-remap,
.05 scheduler-edit) — the next apparent repairable family. Result: they are **AC4
footprint-limits**, not repairable script defects, and the detection is already covered.

**What I found (live):**

- Real staged `.tbl` files exist (`/cf/cf_def_config.tbl`, `/cf/sc_rts004.tbl`, …) with real
  registered names (`CF.config_table`, `SC.RTS_TBL004`; convention from `cfs_sc.dox`).
- Pointing the LOAD at a real file, the LOAD **is accepted** (CFE_TBL.CommandCounter increments)
  — but **ACTIVATE always errors** (CommandErrorCounter++), `ValidationCounter` stays 0, and the
  table's `LastUpdateTime` never moves. Same result for an RTS table and the CF config table,
  and with an explicit LOAD→VALIDATE(inactive)→ACTIVATE sequence (exact payloads from
  `cfe_tbl_msgstruct.h`). The externally-injected LOAD is counted but leaves **no committable
  pending buffer**, so nothing swaps. This is a cFE table-load-handshake limitation of external
  UDP injection, not a script bug — three approaches, all the same.
- **Detection is unaffected and already present.** R9 (CFE_TBL-command, PER-0001) fires on
  `CFE_TBL.CommandCounter` — which the scripts' phase-1 CFE_TBL **NOOP** already increments, and
  the accepted LOAD/VALIDATE increment further. R9 fired (13 frames) in every run. So the
  detectable footprint the classifier needs is produced regardless of whether the table commits.

**Reclassification (feeds AC4 + AC1).** These three are not "write a more faithful script"
repairs like EX-0014.x were; the command path and its detection are faithful already, and the
missing piece — a *committed* on-board table change — is not reproducible via external command
injection in NOS3. Recorded as a **footprint limit**: detection covered (R9), full effect not
injectable. The same limit applies to every partial whose "faithful" version depends on a
successful table load — **EX-0012.08** (ADCS gains = gain-table load) and **EX-0008.01/.02**
(time-bombs = ATS/RTS-table load) — so they inherit this classification rather than needing
individual investigation.

This sharpens the AINOS3-96 "18 partials": a chunk of them are **command-path-faithful +
detection-covered, effect-not-injectable** (AC4), distinct from the genuinely-repairable
telemetry-spoof family (EX-0014.x, done). The DE-0003 "conceal activity" seven remain their own
category (intent has near-zero observable by design).
