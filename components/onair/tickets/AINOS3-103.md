---
key: AINOS3-103
slug: detect-cf-file-faults
type: Story
epic: AINOS3-41 (coverage-expansion)
status: Open
priority: High
estimate: E 2 / T 0.5
opened: 2026-08-25
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

- [ ] `AC1` Nominal behaviour of every CF counter characterised over a soak long enough to expose rare events — AINOS3-95 found a 2-in-3344 event that three shorter windows missed.
- [ ] `AC2` A rule (R-number assigned on implementation) fires on a CF file-operation burst, with the dwell/latch convention matching R6-R13.
- [ ] `AC3` 0 false positives across a nominal soak of at least 3,000 frames.
- [ ] `AC4` Validated against a LIVE attack (an actual CFDP transfer or file-op burst), not offline injection — per this project's evaluation-provenance rule.
- [ ] `AC5` The coverage overlay (`app/gen_nos3_coverage.py`) is updated in THIS ticket, not batched into a later documentation pass.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
