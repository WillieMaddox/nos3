---
key: AINOS3-109
slug: csv-prune-integrity-fields
type: Spike
epic: AINOS3-98 (corpus-integrity)
status: Done
priority: Medium
estimate: E 2 / T 0.5
opened: 2026-08-25
closed: 2026-08-25
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

⚠ Interacts with `AINOS3-111`: CS will produce many integrity columns, and the same
static-therefore-prunable reasoning would discard them.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` Every entry in `ExcludeColumns` classified as: non-numeric (correct), static-and-uninformative (correct), or static-BUT-security-relevant (wrong).
- [x] `AC2` `CFE_ES.CFECoreChecksum` restored to the CSV, or a documented reason it should not be.
- [x] `AC3` Whether the AINOS3-30 derived `CFE_TBL` change-detect columns actually substitute for the pruned name fields — they were measured constant-0, which suggests not.
- [x] `AC4` A stated rule for future columns, so `AINOS3-111`'s output is not pruned by the same reasoning.
- [x] `AC5` `SPARTA_LOGGING_GAP.md` `CDH-GOLDEN` re-assessed if the checksum returns.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-08-25 · DONE — one column wrongly pruned, and the prune list is a detection decision

**`AC1` — all 23 classified.** The "non-numeric" justification covers only **7** of them
(`CFE_EVS.Message`, `PacketID.AppName`, and the five `CFE_TBL` name fields). The other **16
are numeric**, excluded for being static. Traced to source, that splits cleanly:

| class | n | verdict |
|---|--:|---|
| non-numeric (`c_char` arrays) | 7 | correctly excluded |
| **static BY CONSTRUCTION** — the value cannot vary on this build | **16** | correctly excluded |

⚠ **Corrected below** — an earlier revision of this entry split the second row 15/1 and called
`CFE_ES.BootSource` "wrongly excluded". That was itself wrong. All 23 exclusions are correct.

**`AC2` — `CFECoreChecksum` should NOT be restored, and the reason matters more than the
verdict.** It is computed once in `CFE_ES_TaskInit` (`cfe_es_task.c:366`) and **never
recomputed**. So it cannot move within a session *even if an attacker corrupts the cFE text
segment at runtime*. Restoring it would add a guaranteed-constant column.

⚠ This corrects `AINOS3-95`. That ticket concluded "the corpus holds no integrity data because
the checksum is pruned" — right in conclusion, wrong in reason. Un-pruning it would change
nothing. The real gap is that **nothing recomputes integrity at runtime at all**, which is
exactly the capability the CS app provides. `AINOS3-111` is a **stronger** case than the
earlier framing implied, not a weaker one.

**The one wrongly-excluded column: `CFE_ES.BootSource` — removed from the list.** It is
refreshed **every housekeeping cycle** in `CFE_ES_HousekeepingCmd` (`cfe_es_task.c:476`), in
the same block as `ResetType`, `ResetSubtype`, `ProcessorResets` and `MaxProcessorResets` —
**all four of which we already record**. It was grouped with the version constants and
excluded as if it were one. It changes if the vehicle boots from a different source, which is
the `EX-0004` / `PER-0001` persistence signal. Verified live: CSV **451 → 452 columns**,
`CFE_ES.BootSource = 1` alongside `ResetType = 2`, OnAIR healthy.

**`AC3` — the derived `CFE_TBL` columns do NOT substitute for the pruned name fields.** All
six are constant `0` across 21,269 nominal rows. ⚠ But that is *expected*: they fire on a
table-name change, which nominal ops never produce. `AINOS3-30` found them constant in the
attack corpus too and concluded the source fields are static-after-boot. So they are dormant
rather than broken, and confirming the derivation actually works needs an attack that really
loads a table (`PER-0001`) — **not done here, and not assumed.**

**`AC4` — the rule, now written into `nos3_security.ini` beside the list.** The finding that
justifies it: **none of the 23 excluded columns appear in the deployed model's
`scalar_columns`.** Training reads the CSV, so **a column pruned here is excluded from every
future model as well.** `ExcludeColumns` is not a cosmetic corpus setting — it is a
detection-capability decision, made once and invisibly. The rule recorded:

> Prune only what can never carry signal, and state which reason applies: **(a)** non-numeric,
> or **(b)** static by construction — set once at init and never recomputed. ⚠ *"Looks static
> in the data"* is **not** sufficient; that is exactly how `BootSource` was lost.

This also protects `AINOS3-111`: CS emits per-area checksums that will look static in
nominal, and reason (b) does not apply to them — they are recomputed every cycle, which is
their entire point.

**`AC5` — `CDH-GOLDEN` re-assessed: stays `NO`**, with the reason corrected in
`SPARTA_LOGGING_GAP.md` from "the checksum is pruned" to "the only checksum is computed once
at boot and can never move; there is no runtime integrity recomputation at all."

### 2026-08-25 · ⚠ SELF-CORRECTION — `BootSource` was NOT wrongly pruned; reverted

The entry above claimed `CFE_ES.BootSource` was the one genuinely mis-pruned column, on the
grounds that `CFE_ES_HousekeepingCmd` **refreshes it every cycle** (`cfe_es_task.c:476`),
unlike the version constants set once in `TaskInit`. It was un-pruned and verified live
(CSV 451 → 452, `BootSource = 1`).

**That reasoning was wrong, and the value can never move.** `BootSource` is the `ModeId`
argument to `CFE_ES_Main`, and the nos-linux PSP that NOS3 runs passes a **hardcoded literal**:

```c
CFE_PSP_MAIN_FUNCTION(reset_type, reset_subtype, 1, CFE_PSP_NONVOL_STARTUP_FILE);
                                   /* cfe_psp_start.c:445 */
```

So `BootSource ≡ 1` on this platform. Being *refreshed* each cycle is not the same as being
*able to change* — it is re-read every cycle from a variable assigned once from a constant. It
belongs in the static-by-construction bucket with the other 15. **Reverted to the prune list;
all 23 exclusions are correct.**

⚠ **The instructive part is the shape of the mistake.** `AC4`'s rule says *"looks static in the
data" is not sufficient to prune*. I applied its mirror image — treating *"the code refreshes
it"* as sufficient to **un**-prune — without checking whether the source value can vary. Same
failure mode, opposite direction: reasoning from **mechanism** instead of from whether the
**value** can actually move. `AC4` is amended accordingly, in the ini and here:

> The test is whether the **value** can vary on this build — not whether the code touches it
> each cycle, and not whether it happens to look constant in one corpus. Both are proxies, and
> both mislead.

⚠ It also nearly cost something real. `AINOS3-108` established the same day that columns are
**commitments**: adding one is safe, removing it later is a **retrain**. An inert column shipped
here would have been cheap to revert today and expensive after the next retrain.

**Unaffected:** the `CFECoreChecksum` finding (`AC2`), the discovery that pruning silently gates
every future model (`AC4`), the derived-`CFE_TBL` result (`AC3`), and `CDH-GOLDEN` staying `NO`
(`AC5`). Those stand.

**One forward note, now in the ini:** on a PSP with real boot banks (e.g. `mcp750-vxworks`)
`BootSource` becomes a genuine `EX-0004` / `PER-0001` signal. Revisit if NOS3 ever targets one.
