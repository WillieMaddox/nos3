---
key: AINOS3-124
slug: schema-freeze
type: Story
epic: AINOS3-98 (corpus-integrity)
status: Done
priority: High
opened: 2026-09-01
sprints: [29]
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

- [x] `AC1` The current recorded schema inventoried exactly — the column set from `nos3_security_tlm.json` minus the ini prune — with its sha256 as the baseline.
- [x] `AC2` Each pending column-changing item (the table above) adjudicated **build-now** or **defer-to-`schema-vNext`**, with a recorded reason — the app-builds are already decided (CS go / HS·MM no-go, above); `AINOS3-108` MIDs, `AINOS3-109` pruned fields, `AINOS3-102` cam-sim, `AINOS3-120` diag packets, `AINOS3-104` gains remain. Deferred items land on a named `schema-vNext` list in the manifest.
- [x] `AC3` ⚠ **The freeze:** a versioned schema manifest published (frozen column set + sha256) that `AINOS3-100 AC2`'s corpus manifest records against. No change to the recorded schema after this without reopening.
- [x] `AC4` ⚠ **`AINOS3-111` (CS) built and its columns verified reaching OnAIR live BEFORE `AC3`** — this freeze is gated on it (subscribe-and-verify, not source-read). Any other build-now item likewise executed+verified before the freeze, or excluded and deferred.
- [x] `AC5` `AINOS3-108` resolved here (its four MIDs decided at the freeze) and marked unblocked; `AINOS3-100` updated to consume the frozen schema manifest.
- [x] `AC6` The `schema-vNext` deferred list is the single record of what a later schema revision must revisit, with each item's trigger — mirroring the deferred-class register.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

⚠ **Depends on `AINOS3-111` (CS build + live-verify)** — the freeze (`AC3`) cannot publish until CS columns are confirmed reaching OnAIR.

### 2026-09-10 · FROZEN — `schema-v1`, 470 columns

**`recorded_schema_sha256 = ff8a9e294362a02ab71a497c308a85d9f4ca4d42b29fd9401ce06206eccc926e`**

Manifest: [`schema_manifest.json`](../schema_manifest.json). Generated and verified by
`training/schema_audit.py`, built for this ticket.

**The fingerprint problem this had to solve first (`AC1`/`AC3`).** The ticket assumed the
`.meta.json` sidecar's `schema_sha256` was already the mechanism for pinning a schema. It is
not, and its own docstring claimed otherwise: it hashes the tlm metadata **file**, so it moves
on comment churn and — the defect — does **not** move when `ExcludeColumns` moves. A prune is
a real schema change to every downstream consumer, so a corpus pinned to that hash could
silently be pinned to the wrong column set. Added `recorded_schema_sha256` to the sidecar
(`csv_output@1.2`): sha256 over the ordered list of columns **as written**, newline-joined so a
rename cannot collide with a reorder. 4 tests, one of which asserts the defect directly —
`schema_sha256` equal, `recorded_schema_sha256` different, across a prune change.

The manifest's hash is computed from **config** and the sidecar's from the **live CSV header**,
independently. They agree exactly, which is the check that the frozen manifest actually
describes what gets recorded.

**`AC2` — every pending item adjudicated:**

| item | ticket | decision at the freeze |
|---|---|---|
| four silent MIDs | `AINOS3-108` | **build-now, APPLIED** — 9 columns pruned (`CFE_SB_SUBS` 4, `SBN` 2, `RADIO_DEV` 3). `ST_DEV` kept |
| pruned integrity fields | `AINOS3-109` | **already settled, no change** — `BootSource` restored; `CFECoreChecksum` stays pruned (computed once in `CFE_ES_TaskInit`, cannot move even under runtime corruption) |
| cam-sim / payload sims | `AINOS3-102` | **defer → `schema-vNext`** — `arducam` sits below the startup `!` terminator *and* `CAM_EXP` has no `TransmitMsg`; subscribing would record nothing |
| CS checksum app | `AINOS3-111` | **build-now, APPLIED + live-verified** — 28 `CS.*` columns, arriving (sentinel fraction 0.0001) |
| HS app | `AINOS3-112` | **NO-GO → `schema-vNext`** — services a no-op watchdog stub |
| MM / MD | `AINOS3-113` | **NO-GO → `schema-vNext`** — adds a supported attacker memory-write path |
| cFE diagnostic packets | `AINOS3-120` | **defer → `schema-vNext`** — needs FSW scheduler-table work; Low priority |
| ADCS control gains `0x0944` | `AINOS3-104` | **IN, no schema change** — the 25 `ADCS_AC.*` columns are already recorded. `AINOS3-104` is a *detector* ticket over columns we hold, not a schema item |

**`AC4` — the CS gate is cleared.** `AINOS3-111` is Done and its 28 columns are live-verified
in the frozen set — subscribe-and-verify, not source-read. Its own `AC3` measured them
non-constant (cFE-core baseline + sweep counters), so this is not a repeat of the `AINOS3-95`
"recorded ≠ works" trap. No other build-now item was outstanding.

**`AC5` — `AINOS3-108` resolved and unblocked** (see that ticket). The insight that unblocked
it: "removal needs a retrain" is true of the **subscribed** schema and false of the
**recorded** one, and only the recorded one is what a corpus bakes in. Pruning is a CSV-writer
operation; unsubscribing is a model operation. `AINOS3-100` consumes
`schema_manifest.json` — its corpus manifest records `recorded_schema_sha256`, and a
collection run whose sidecar disagrees is a rejected run, not a footnote.

**`AC6` — the `schema-vNext` deferred register** lives in `SCHEMA_VNEXT` in
`training/schema_audit.py` and is copied into every manifest. Five items, each with an explicit
**trigger** rather than a vague "later" — mirroring the deferred-class register. The most
consequential is the `AINOS3-108` unsubscribe, triggered by the next IF retrain.

**Subscribed ≠ recorded ≠ working — now checkable.** `schema_audit.py --require-no-new-silent`
flags any column that is the `[0]` no-data sentinel in 100 % of a session's frames. Before the
prune: 14 such columns over 138,397 frames of the 2026-09-03 session. After, live on a fresh
`make launch-quiet`: **5, all `ST_DEV`, all expected**, over 839 frames. That is the standing
regression check for `AINOS3-100`'s collection runs.

⚠ **`ST_DEV` is in the frozen schema on purpose.** It is silent today because the star tracker
boots disabled, but `AINOS3-86`'s fix is to enable it — a column that may go live mid-sprint
must already be frozen in, or `AINOS3-86` landing would force a re-collect. This is the freeze
earning its keep in the one case that was live at the time it was taken.

