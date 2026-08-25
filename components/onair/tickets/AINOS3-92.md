---
key: AINOS3-92
slug: soak-drift-hz
type: Task
epic: AINOS3-79 (detector-rigor)
status: Done
priority: Medium
opened: 2026-08-11
closed: 2026-08-23
sprints: [27, 28]
---

# AINOS3-92 — `analyze_soak_drift.py` uses the wrong sample rate

**Summary:** As an analyst, I want the drift tool to derive the frame rate from the data, because its hardcoded 4.2 Hz default mislabels every uptime bin by about a third.

## Description

Measured against legs of known wall-clock duration, the true rate is
**~5.6 Hz** (5.36–5.79 across modes), not the 4.2 Hz default. At 4.2 a bin labelled
"T+30–60 min" actually covers roughly T+22–45 min. It does not change any pass/fail verdict —
drift is judged on the trend, not the bin labels — but every published drift table has
mislabelled time axes, and the AINOS3-81 figures were only correct because `--hz 5.6` was
passed explicitly.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` Rate derived from the side file (frame count ÷ elapsed wall-clock) rather than assumed;
      `--hz` retained as an override.
- [x] `AC2` Warn when the derived rate differs from any supplied `--hz` by more than ~10 %.
- [x] `AC3` Any drift table already published with the 4.2 default is re-checked or annotated.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.

### 2026-08-23 · AC1–AC3 DONE — rate derived from MET; the old 4.2 Hz stretched every bin 32 %

**Result:** ✅ DONE (2026-08-23) — **fixed, and the error was larger than the ticket said.**

**The rate is now derived, not assumed.** The side-file carries no clock at all — only
`frame_idx` — so `derive_hz()` reads `CFE_TIME.SecondsMET` from the `csv_out_*` log of the
same session, paired by `(pid, nearest timestamp)`; OnAIR opens the two ~0.5 s apart, so the
pairing is unambiguous. Two properties of that clock drove the implementation: MET is only
~0.25 Hz-granular in the HK packet, so per-sample diffs are useless (median `dt` = 4.0 s →
0.25 Hz) and only the endpoints over a long span are informative; and MET is **non-monotonic**
across the OnAIR double buffer, so the span is `max − min`, not `last − first`.

**Measured, across four 2026-08-15 sessions:** 5.551 · 5.460 · 5.100 · 4.783 Hz. The
hardcoded 4.2 was **24 % low against 5.551**, and the effect on the tool's own output is
worse than the ticket's ~33 %: the same 86.9 h soak reports **5,229 min at the derived rate
and 6,911 min at 4.2** — every uptime bin overstated by **32 %**.

**Guards, because a derived number can be wrong too:** rates outside 1–20 Hz are rejected, as
are MET spans under 60 s (startup jitter dominates) and sessions with no pair or no
`SecondsMET` column. When derivation fails and no `--hz` is given the tool warns on stderr and
falls back to a named `FALLBACK_HZ = 5.5` rather than a silent constant. `--hz` remains an
override and always wins, but is now checked: a > 10 % disagreement prints
`WARNING: --hz 4.2 disagrees with the derived rate 5.551 Hz by 24%`. The resolved rate and its
provenance print in the header and are recorded in the `--json` dump, so any future soak
result carries its own rate.

**Verification:** 10 tests in `training/test_soak_drift.py` covering derive, sub-second pair
skew, no-pair, short-span, missing column, insane rate, loud fallback, and both override
branches — all passing; plus all three paths exercised against the real 1.74 M-frame soak.

⚠ **Every soak number published before today used 4.2 Hz.** Their FP *rates* are unaffected
(a ratio of frame counts), but their **uptime axis is stretched ~32 %** — any claim of the
form "FP was flat through T+6 h" was really measuring T+4.5 h. Re-run `--json` on any archived
side-file before citing its bins.

---

### 2026-08-25 · ⚠ the 5.6 Hz figure is schema-dependent and is now stale (via AINOS3-95)

This ticket's derived **5.6 Hz** was correct for the schema in place when it was measured. It
is not a constant of the system.

Re-derived by AINOS3-95 stage 4 on the settled schema (359 → 451 CSV columns):
**5.87 Hz** from MET, 6.06 /s wall-clock.

⚠ Do **not** attribute the change to the schema. `AINOS3-95` established that OnAIR's loop is
**compute-bound, not arrival-bound** (~23 msg/s in, ~6 frames/s out, no rate limiter in
`sim.py`), so frame rate moves with host load and stack uptime as well as column count, and the
two measurements were taken at different uptimes.

**What to do with this:** treat any published Hz as a measurement with a date and a schema, not
an inherited constant. `components/onair/training/measure_frame_rate.py` (built by AINOS3-95)
re-derives it in ~2 minutes; run it rather than citing 5.6 or 5.87. The uptime-axis correction
this ticket delivered stands — only the constant moved.
