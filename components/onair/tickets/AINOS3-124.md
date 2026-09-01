---
key: AINOS3-124
slug: schema-freeze
type: Story
epic: AINOS3-98 (corpus-integrity)
status: Backlog
priority: High
opened: 2026-09-01
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-124 — Freeze the recorded telemetry schema

**Summary:** As an ML engineer, I want the recorded telemetry schema settled and versioned before Stage-2 collection, because folding a column into a collection that has not started is free while adding it after is a full recollect — the same "subscribe before you collect" argument the label freeze (`AINOS3-122`) applies to classes, applied to columns.

## Description

The corpus rebuild (`AINOS3-100`) bakes in **two** things at collection time: the class labels and
the **recorded schema** — the exact set of CSV columns, driven by which MIDs are subscribed
(`nos3_security_tlm.json`) minus the CSV prune (`nos3_security.ini` `ExcludeColumns`). `AINOS3-122`
froze the first. **Nothing freezes the second**, and that is the missing half of Sprint-28's
"read the manual before rebuilding" groundwork.

Why it matters, concretely: a column change discovered *after* collection makes the new corpus
obsolete at the schema level on arrival — precedent `AINOS3-70` took the CSV 360 → 382 columns and
needed an `sbn_client.so` rebuild. If a signal we should record is added a week into Stage 2, the
week is wasted.

Right now the schema decisions are **scattered** across open/blocked tickets with no single "the
schema is X, frozen" gate — this ticket is that gate. It mirrors the label freeze exactly:
inventory → adjudicate each pending change → publish a versioned manifest → the collection records
against it.

**The current schema surface:**

- **`nos3_security_tlm.json`** — the subscribed-MID → struct → field map (the columns that exist).
- **`nos3_security.ini` `ExcludeColumns`** — the prune (drops 23 fields, incl. `CFE_ES.CFECoreChecksum`
  and the version/boot constants, before the CSV).
- **the `.meta.json` schema-sha256 sidecar** (CSV format v2) — already the mechanism for pinning a
  schema; this ticket produces the **frozen** sha256 that `AINOS3-100 AC2`'s corpus manifest records.

**Every pending column-changing item must get an explicit build-now vs defer-to-`schema-vNext`
decision — none silently in or out:**

| item | effect on schema | ticket |
|---|---|---|
| four silent MIDs (drop/keep) | **removes** columns | `AINOS3-108` (Blocked) |
| pruned integrity fields (`CFECoreChecksum`) | restores columns | `AINOS3-109` (Done) |
| `cam-sim` / payload sims in the headless launch | **adds** columns | `AINOS3-102` (Done) |
| CS checksum app | **adds** integrity columns | `AINOS3-111` — **GO (prerequisite)** |
| HS health-and-safety app | **adds** columns | `AINOS3-112` — **NO-GO** → `schema-vNext` |
| MM / MD memory apps | **adds** columns | `AINOS3-113` — **NO-GO** → `schema-vNext` |
| cFE diagnostic packets | **adds** columns | `AINOS3-120` |
| ADCS control gains (`0x0944`) | already subscribed — in or out | `AINOS3-104` |

**Go/no-go on the app-builds, decided 2026-09-01 (owner):**

- **CS (`AINOS3-111`) → GO, and a PREREQUISITE of this freeze** — built and its columns
  **live-verified reaching OnAIR before `AC3`**. The corpus has **zero integrity data**; freezing
  without CS guarantees a re-collect the moment it lands. It is the **long pole of Stage 1** — the
  freeze does not publish until it is done. `AINOS3-111` is bumped and sequenced ahead of this ticket.
- **HS (`AINOS3-112`) and MM+MD (`AINOS3-113`) → NO-GO** — deferred to the `schema-vNext` list, not
  built pre-freeze. HS would service a **no-op watchdog stub** (uncertain observable value); MM adds
  a **supported attacker memory-write path** (an attack-surface trade-off, not an automatic build).
  Neither is worth blocking the freeze; each is revisited at the next schema revision with its own
  go/no-go.

⚠ **This unblocks `AINOS3-108`.** It is Blocked on "schema removal needs a retrain — fold into
`AINOS3-101`". That is backwards: the removal belongs to the **freeze** (before collection), not
the retrain (after). Resolving `AINOS3-108`'s four MIDs here, before Stage 2, is what unblocks it.

⚠ **Deferred items are tracked, not dropped.** Anything decided defer-to-`schema-vNext` goes on a
named list in the frozen manifest — the same discipline as the deferred-class register (the
`status` column of `label_set.json`), so a deferred column is revisited, not forgotten.

⚠ **Not fully offline (unlike the label freeze):** `AC1`–`AC3` are desk work, but `AC4` (verifying a
build-now column actually reaches OnAIR live) needs the stack — the `AINOS3-95` "recorded ≠ works"
lesson (CAM/SYN were subscribed but dead; derived CFE_TBL columns were constant-0).

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` The current recorded schema inventoried exactly — the column set from `nos3_security_tlm.json` minus the ini prune — with its sha256 as the baseline.
- [ ] `AC2` Each pending column-changing item (the table above) adjudicated **build-now** or **defer-to-`schema-vNext`**, with a recorded reason — the app-builds are already decided (CS go / HS·MM no-go, above); `AINOS3-108` MIDs, `AINOS3-109` pruned fields, `AINOS3-102` cam-sim, `AINOS3-120` diag packets, `AINOS3-104` gains remain. Deferred items land on a named `schema-vNext` list in the manifest.
- [ ] `AC3` ⚠ **The freeze:** a versioned schema manifest published (frozen column set + sha256) that `AINOS3-100 AC2`'s corpus manifest records against. No change to the recorded schema after this without reopening.
- [ ] `AC4` ⚠ **`AINOS3-111` (CS) built and its columns verified reaching OnAIR live BEFORE `AC3`** — this freeze is gated on it (subscribe-and-verify, not source-read). Any other build-now item likewise executed+verified before the freeze, or excluded and deferred.
- [ ] `AC5` `AINOS3-108` resolved here (its four MIDs decided at the freeze) and marked unblocked; `AINOS3-100` updated to consume the frozen schema manifest.
- [ ] `AC6` The `schema-vNext` deferred list is the single record of what a later schema revision must revisit, with each item's trigger — mirroring the deferred-class register.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

⚠ **Depends on `AINOS3-111` (CS build + live-verify)** — the freeze (`AC3`) cannot publish until CS columns are confirmed reaching OnAIR.
