---
key: AINOS3-105
slug: test-encryption-bypass-observability
type: Story
epic: AINOS3-41 (coverage-expansion)
status: Open
priority: Medium
estimate: E 3 / T 1.0
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-105 — Are encryptor bypass commands observable?

**Summary:** EX-0006 and PER-0004 were ruled out on CryptoLib state being invisible, but the workbook asks for the COMMAND — which we already record.

## Description

AINOS3-95 `AC4` found that two published out-of-scope verdicts answer a question SPARTA does
not ask.

Our rationale for `EX-0006` (disable/bypass encryption) and `PER-0004` (replace cryptographic
keys) was that the encryptor's *state* lives inside CryptoLib, a `CFE_LIB` with zero Software
Bus telemetry. That remains true.

The workbook (`TT&C` rows 22-24) asks for something different and rates it **High**: *"any
received bypass commands"*, *"any received key change commands"*, *"disable encryptor"* — log
and alert **under all circumstances**. A command arriving at CI is precisely the
static-in-nominal counter signal that rules R6-R13 are built on (`CI.usCmdCnt`,
`CI.usCmdErrCnt`, `RADIO_HK.ForwardCount/ForwardErrorCount` are all recorded today).

So the re-open is a **rule candidate, not a subscription**. ⚠ The known limitation is that our
command telemetry is aggregate counters with no opcode, so a rule can detect *a* command
without proving *which* — the ticket must establish whether that is sufficient or whether it
produces an unacceptable false-positive rate against routine commanding.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Establish whether `CI.usCmdCnt` is genuinely static in nominal ops, or whether routine commanding moves it (which would make a bare new-high rule unusable).
- [ ] `AC2` An attack script that issues a CryptoLib bypass / key-change / disable-encryptor command against the live FSW.
- [ ] `AC3` Determine whether the command is distinguishable from routine commanding; if not, say so and reclassify honestly rather than shipping a rule that cannot separate them.
- [ ] `AC4` If a rule is viable: 0 FP over a nominal soak, plus a live TP.
- [ ] `AC5` `EX-0006` and `PER-0004` verdicts updated either way — a documented negative is a valid outcome.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
