---
key: AINOS3-126
slug: sbn-adapter-blended-output
type: Story
epic: AINOS3-63 (detector-gates)
status: Backlog
priority: High
estimate: E 5 / T 1.5
opened: 2026-09-19
origin: AINOS3-125 (blended-log-format)
---

# AINOS3-126 — Emit one coherent frame from the SBN double buffer

**Summary:** As a detector owner, I want the live OnAIR frame to carry one coherent set of telemetry values instead of alternating buffer snapshots, so every detector sees each update on the frame it arrives rather than on every other frame, and so the gates can stop compensating for an artifact.

## Description

`AINOS3-125` fixed the recorded corpus offline. This fixes the **live frame**, which
is where every deployed detector actually reads.

The transform is the one already validated offline: keep a reference dict per buffer, write a
field to the output frame only when it changed against **its own buffer's** previous frame,
carry everything else forward. ⚠ A naive single "latest value" dict is WRONG — buffer B's
copy of a field is usually stale, and letting it overwrite A's fresh update reproduces the
flicker exactly.

⚠ **This is a schema-SEMANTICS change and forces an IF retrain.** By the `AINOS3-108` rule
the deployed detector pins the recorded schema; here the column set is unchanged but the
*values* on a given frame change, which is the same hazard by a different route. The
deployed IF and classifier were fitted on interleaved deltas and must be refitted on blended
ones before this can go live.

⚠ **It also invalidates the live-behaviour baselines**, which are currently true records of a
system that really does see interleaved frames: `AINOS3-86`'s 0.00 % controlled-INERTIAL FP,
`AINOS3-90`'s 55.8 incidents/hour, and the Section-A rule-gate validations all describe
pre-change behaviour and need re-measuring after it.

⚠ **The defect originates upstream** (NASA OnAIR, `sbn_adapter` only — `redis_adapter`
blanks its write buffer each message and `csv_parser` has none), so record our divergence
when the patch lands or a future rebase will silently drop it.

## Acceptance criteria

- [ ] `AC1` `sbn_adapter` emits a blended frame by per-buffer change detection; the two reference dicts and the output frame are distinct state, and a stale value never overwrites a fresh one.
- [ ] `AC2` ⚠ **Per-run equivalence: `deinterleave_csv.py(raw) == native blend`.** The adapter emits BOTH streams for a collection run — the untouched interleaved frames (a pure tap on the existing read path, so the raw side stays the same *kind* of data as the pre-existing `csv/`) AND the live blend. For each run, blending the raw stream offline must reproduce the native blend exactly. This is deterministic — both consume the identical recorded frame sequence — so it is a real proof, not a replay approximation. ⚠ Verify it in **all four modes** (the buffer mechanism is mode-agnostic, but each mode exercises different fields at different rates), using the `AINOS3-100 AC7` SUNSAFE-x1 / INERTIAL / BDOT / PASSIVE runs as they are collected.
- [ ] `AC2b` ⚠ The raw tap must not alter the read: an interleaved file from the dual adapter must be the same representation the old adapter produced (same double-buffer semantics), so old and new `csv/` data pool into one corpus. Implement the tap upstream of the blend and leave `get_next()`'s buffer logic untouched.
- [ ] `AC3` The `[0]` sentinel contract preserved exactly as offline: written for never-received fields, never adopted over good telemetry (see `AINOS3-125 AC2` for the four tools that fail silently otherwise).
- [ ] `AC4` ⚠ IF and classifier refitted on blended data and deployed together with the adapter. Deploying the adapter alone leaves both models scoring inputs whose distribution they were never fitted to.
- [ ] `AC5` Deployment follows the `AINOS3-37` discipline: one-line ini/flag flip, one-line rollback, live-verified on a fresh `make launch-quiet`, build tree synced. **Not deploying is a valid outcome.**
- [ ] `AC6` The invalidated live baselines named above re-measured, or explicitly marked pre-change in their tickets.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
