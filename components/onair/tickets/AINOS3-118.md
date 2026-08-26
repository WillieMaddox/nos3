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
- [ ] `AC2` The EX-0014.01 repair as the first slice and exemplar: a script spoofing the NOVATEL GPS time input (via the `ci_lab` republish path), producing a GPS-time-anomaly footprint EX-0012.12 cannot — live-validated, confirming R15 actually catches it (closing the `AINOS3-96` 'recorded ≠ works' caveat).
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
