---
key: —
slug: build-cs-app
type: Story
epic: build-missing-cfs-apps
status: Pending Jira key
priority: High
estimate: E 5 / T 2.0
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# build-cs-app — Build the CS checksum app

**Summary:** Build the CS (Checksum) app — the recorded corpus currently contains no integrity data of any kind.

## Description

The single highest-value item in the AINOS3-95 gap analysis. SPARTA's logging workbook asks
for actual-vs-expected checksums or hashes on **six separate rows**, rated **High** on every
one: golden software and firmware images, tables, stored command scripts, configuration
key-value pairs, and boot mechanisms.

Against that, the recorded corpus contains **zero integrity data**. The only checksum we
subscribe, `CFE_ES.CFECoreChecksum`, is pruned from the CSV before it reaches disk (see
`csv-prune-integrity-fields`).

CS computes CRCs over the cFE core image, the OS image, app code segments, tables and
user-defined memory, and telemeters per-area state with miscompare counters plus EVS events on
mismatch. It is a **producer** of security-relevant log data, not a consumer.

Unblocks a re-assessment of `EX-0004`, `EX-0005`, and the `CDH-GOLDEN` recommendation.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` `cs` vendored, built, loading, and its HK arriving at OnAIR — verified live.
- [ ] `AC2` Checksum tables authored for NOS3's actual app and table set, not a stock example.
- [ ] `AC3` Columns subscribed and validated non-constant, and NOT silently pruned from the CSV.
- [ ] `AC4` A deliberate corruption produces an observable miscompare — the detection demonstrated live, not inferred.
- [ ] `AC5` `CDH-GOLDEN` and the `EX-0004`/`EX-0005` verdicts re-assessed.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
