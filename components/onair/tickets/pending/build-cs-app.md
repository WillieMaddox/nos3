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

⚠ **Premise corrected 2026-08-25 (via `AINOS3-102`).** An earlier revision said these apps are
"loaded in `cfe_es_startup.scr` and simply have no `.so`". **Both halves were wrong about the
loading.** `cfe_es_startup.scr` has an end-of-file terminator — cFS stops parsing at the first
`!`, on line 33 of 91 — and `cs`, `hk`, `hs`, `md`, `mm` (with `arducam` and `syn`) appear
**only below it**, so they are **not loaded at all**. Verified: all seven emit zero EVS init
events, while every app above the `!` loads. Entries below the `!` that *do* run are duplicates
of ones listed above.

The script states the design: *"In NOS3, these are moved as part of the `make config` process
depending on what is enabled."* The below-`!` block is the **catalogue of disabled apps**.

**So enabling one needs TWO changes, not one:** build the `.so` **and** move its entry above
the `!` (or make `make config` do so). Budget accordingly — the second half was invisible in
the original scoping.

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
