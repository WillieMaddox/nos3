---
key: AINOS3-119
slug: retest-reopened-verdicts
type: Task
epic: AINOS3-41 (coverage-expansion)
status: Open
priority: Medium
estimate: E 2 / T 0.5
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-119 — Re-test the verdicts the missing apps unblock

**Summary:** Live-retest the three out-of-scope verdicts that become re-openable once the missing cFS apps are built.

## Description

AINOS3-95 `AC4` established that `EX-0012.11`, `DE-0003.11` and `EX-0012.01` are out of scope
for the **build**, not by design — the telemetry the workbook asks for is produced by stock
cFS apps that are loaded in the startup script and simply absent from the build.

Once `AINOS3-112` and `AINOS3-113` land, each verdict must be **re-tested live**, not
flipped on the assumption that the app makes it observable.

⚠ Per this project's evaluation-provenance rule, a verdict may not turn green on the strength
of a document or a source reading. AINOS3-95 produced two direct demonstrations of why: R15
passed a nominal soak, an offline injection and a green test suite while still missing the live
`SET_TIME` it was built for; and CAM/SYN looked correct in source while delivering zero packets
live.

A documented negative — "the app is built and the technique is still not observable" — is an
acceptable and useful outcome.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` An attack script per technique that exercises it against the live FSW.
- [ ] `AC2` Each verdict re-tested live and updated with the measured result, in either direction.
- [ ] `AC3` If detectable, a rule with 0 FP over a nominal soak and a live TP.
- [ ] `AC4` Coverage overlay updated in this ticket.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

⚠ **Gated on** `AINOS3-112` (EX-0012.11, DE-0003.11) and `AINOS3-113` (EX-0012.01).
