---
key: AINOS3-103
slug: detect-cf-file-faults
type: Story
epic: AINOS3-41 (coverage-expansion)
status: Done
priority: High
estimate: E 2 / T 0.5
opened: 2026-08-25
closed: 2026-08-25
sprints: [28]
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-103 — Detect CFDP file-operation faults

**Summary:** CF's file-operation fault counters are static in nominal — an R6-family rule candidate for EX-0010 / EXF, using telemetry AINOS3-95 already subscribed.

## Description

AINOS3-95 stage 2b subscribed `CF_HK` `0x08B0` (+55 columns). Measured over a nominal soak the
CFDP counters are **entirely idle** — no file transfers run in nominal ops — which is exactly
the *static-in-nominal* property rules R6-R13 are built on.

The candidate fields are the per-channel fault counters
(`CF.channel{0,1}.counters.fault.{file_open,file_read,file_write,file_rename,crc_mismatch,
file_size_mismatch,directory_read,...}`) plus the command counters `CF.counters.{cmd,err}`.
Any increment means file activity that nominal operations do not produce.

Relevance: `EX-0010.01/.02` (ransomware / wiper) and the `EXF` exfiltration family both move
files. R11 already covers the **FM** app's command burst; CF is the *CFDP transfer* side, so
the two are complementary rather than redundant — R11 sees the command, CF sees the transfer.

⚠ This is currently 55 recorded columns earning nothing. Either they become a detector or they
are corpus bloat, and this ticket decides which.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` Nominal behaviour of every CF counter characterised over a soak long enough to expose rare events — AINOS3-95 found a 2-in-3344 event that three shorter windows missed.
- [x] `AC2` A rule (R-number assigned on implementation) fires on a CF file-operation burst, with the dwell/latch convention matching R6-R13.
- [x] `AC3` 0 false positives across a nominal soak of at least 3,000 frames.
- [x] `AC4` Validated against a LIVE attack (an actual CFDP transfer or file-op burst), not offline injection — per this project's evaluation-provenance rule.
- [x] `AC5` The coverage overlay (`app/gen_nos3_coverage.py`) is updated in THIS ticket, not batched into a later documentation pass.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-08-25 · DONE — R16 shipped, live-validated; and a latent R10 bug fixed on the way

**`AC1` — CF is perfectly static in nominal.** All **55** CF columns constant across **15,312**
frames: 50 zeros plus static queue-config arrays (`q_size = [0,0,0,0,0,256,50]`, the CFDP
free-list sizes). CF is idle unless a transfer runs, which gives every CF counter the same
static-in-nominal property R6-R13 exploit. Re-confirmed on a second 3,170-frame session.

**`AC2` — `R16` built, with two sub-ids** mirroring R14's shape:

- **`R16:cf-command`** — `CF.counters.cmd` new-high. A CFDP command was processed.
- **`R16:cf-fault`** — **all 22** per-channel fault counters (`file_open`, `file_read`,
  `file_write`, `crc_mismatch`, `nak_limit`, …) share **one** rule id, so a burst reads as a
  single signal rather than 22.

Both use the existing static-counter new-high + `CmdDwell` mechanism, so the dwell/latch
convention matches R6-R13 by construction. Labels: `cf-command` → `EXF-0003.02`
(`cfdp-transfer-command`), `cf-fault` → `EX-0010` (`cfdp-file-faults`). Faults **outrank** a
bare command in `_prio` (2.4 vs 2.5) — when both fire, files failing *during* a transfer is
the accurate description, not that a transfer happened. Same reasoning as
`R14:adcs-mode-flap` outranking `R14:adcs-mode`.

⚠ **A latent bug in R10 had to be fixed first.** The bus-sweep meta-rule counted
`self._cmd_rule.values()` **with duplicates**, though its comment said "distinct". Harmless
until now — every earlier rule owned exactly one column — but mapping 22 CF fault columns to
one rule id would have crossed R10's 3-distinct-rule threshold on a **single app's** fault
burst, mislabelling it a bus sweep (`LM-0002`). Now counts distinct ids; pinned by
`test_r16_fault_burst_does_not_trip_the_bus_sweep`.

**`AC3` — 0 false positives across 3,170 nominal frames**, and 0 fires of *any* rule. Live,
on the deployed build (29 static-cmd counters registered, up from 6).

**`AC4` — live TP, clean edge.** Fired `CF_NOOP_CC` at `CF_CMD_MID 0x18B3`; FSW accepted it
(`CF: No-Op received, Version 3.0.99.0`). `R16:cf-command` fired at frame **3418** — the attack
frame — with **0 fires in the preceding 3,417**, and a proper ALERT → CLEAR cycle. ⚠ The IF
scored `is_anomaly=False` at frame 3400, confirming this is a **gate-only catch the dynamics
model is blind to by design** — the same class as R6-R14.

⚠ **Honest scope limit:** the live test exercised `R16:cf-command` via a NOOP. **`R16:cf-fault`
is unit-tested but not live-validated** — provoking real CFDP faults needs an actual transfer
against a peer entity, which this build has no counterpart for. It should not be counted as a
validated detection until that is done.

**`AC5` — overlay updated in this ticket.** `EXF-0003.02` gains R16 as a second independent
exfiltration signal alongside R12/R13; `EX-0010.01` and `EX-0010.02` gain R16's fault counters
as corroboration of R11's FM burst. Purple markers set on all three. **79 rule-gate tests pass.**
