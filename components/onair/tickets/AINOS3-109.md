---
key: AINOS3-109
slug: csv-prune-integrity-fields
type: Spike
epic: AINOS3-98 (corpus-integrity)
status: Open
priority: Medium
estimate: E 2 / T 0.5
opened: 2026-08-25
sprints: [28]
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-109 — The CSV prune drops security-relevant fields

**Summary:** The CSV prune excludes CFE_ES.CFECoreChecksum because it is static — but a core checksum that stops being static is exactly the attack signal.

## Description

`nos3_security.ini`'s `ExcludeColumns` drops 23 of the 382 schema columns from the CSV. They
are still parsed into the frame, so a live plugin can read them, but **nothing trained on the
corpus can ever use them**.

The list was built to remove non-numeric and static-version fields, which is reasonable for
most of it. But it also contains **`CFE_ES.CFECoreChecksum`**, excluded on the grounds that it
is static — and a core checksum ceasing to be static is precisely the footprint of `EX-0004`
(boot memory) and `EX-0005` (golden-image corruption). We are excluding a column *for the very
property that makes it a detector*.

This is why `SPARTA_LOGGING_GAP.md` records `CDH-GOLDEN` as **NO**: the recorded corpus
contains no integrity data of any kind, and the one checksum we do subscribe is pruned before
it reaches disk.

Also in scope: the `CFE_TBL.Last*` name fields, pruned as non-numeric. The AINOS3-30 derived
change-detect columns exist to replace them and were measured constant-0, so the substitution
may not be working.

⚠ Interacts with `build-cs-app`: CS will produce many integrity columns, and the same
static-therefore-prunable reasoning would discard them.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Every entry in `ExcludeColumns` classified as: non-numeric (correct), static-and-uninformative (correct), or static-BUT-security-relevant (wrong).
- [ ] `AC2` `CFE_ES.CFECoreChecksum` restored to the CSV, or a documented reason it should not be.
- [ ] `AC3` Whether the AINOS3-30 derived `CFE_TBL` change-detect columns actually substitute for the pruned name fields — they were measured constant-0, which suggests not.
- [ ] `AC4` A stated rule for future columns, so `build-cs-app`'s output is not pruned by the same reasoning.
- [ ] `AC5` `SPARTA_LOGGING_GAP.md` `CDH-GOLDEN` re-assessed if the checksum returns.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
