---
key: AINOS3-108
slug: subscription-hygiene
type: Task
epic: AINOS3-41 (coverage-expansion)
status: Done
priority: Medium
estimate: E 2 / T 0.5
opened: 2026-08-25
sprints: [28, 29]
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# AINOS3-108 — Resolve four silent MID subscriptions

**Summary:** Four subscribed MIDs deliver no telemetry — but each is silent for a different reason, and only two are genuine drop candidates. Resolve each individually and reclaim the cap slots.

## Description

AINOS3-95 stage 0 measured per-MID arrival rates and found **four subscribed MIDs that never
transmit**. An earlier draft of this ticket called them "dead MIDs" and proposed dropping all
four. ⚠ **That framing was wrong** — traced to source, the four have four different causes and
only two are simple removals:

| MID | Why it is silent | Disposition |
|---|---|---|
| `ST_DEV` `0x0936` | The **star tracker is disabled by default** (`ST.DeviceEnabled = 0`). Proven live: sending `GENERIC_STAR_TRACKER_ENABLE` (`0x1935` FC 2) makes it transmit immediately | ⚠ **Do NOT drop** — a configuration question, not a dead MID. Owned by `AINOS3-86` / `AINOS3-91` |
| `RADIO_DEV` `0x0931` | **0 scheduler entries, 0 TO routes.** The radio app publishes it only opportunistically from its proxy task (`generic_radio_app.c:537`), forwarding bytes as they arrive from the prox socket | Judgement call — being usually-silent may be *correct* for an event-driven prox indicator |
| `CFE_SB_SUBS` `0x080D` | **Command-produced** (`CFE_SB_SEND_PREV_SUBS_CC`), **0 scheduler entries** | Drop, or schedule with the deferred diagnostic packets |
| `SBN` `0x08DC` | **Command-produced**, **0 scheduler entries** — SBN HK emits only in response to a command | Drop. ⚠ See the hazard below before considering scheduling |

⚠⚠ **Hazard on `0x08DC`, found while substantiating this ticket.** That single MID carries
**five different payload structs**, selected by which command was sent — `SBN_HK_LEN`,
`SBN_HKNET_LEN`, `SBN_HKPEER_LEN`, `SBN_HKMYSUBS_LEN`, `SBN_HKPEERSUBS_LEN`
(`fsw/apps/sbn/fsw/src/sbn_cmds.c:257-491`). We model it as one fixed `SBN_ModuleStatusTlm_t`
(2 columns). If anyone "fixes" the silence by scheduling SBN HK, **four of the five variants
would be silently mis-parsed** — an intermittent byte-misalignment, much harder to detect than
the fixed one AINOS3-95 hit in stage 2a. This is the strongest argument for **dropping**
`0x08DC` rather than scheduling it.

**Why it is worth doing at all.** Silent subscriptions cost schema columns that are constant by
construction, slots against the `CFE_SBN_CLIENT_MAX_MSG_IDS_PER_PIPE` = 48 cap, and analyst
time — `AINOS3-91` was opened against "5 constant `ST_DEV` fields" when the cause was that the
packet never arrives.

⚠ **Revised cap arithmetic:** net relief is **2-3 slots, not 4** (`ST_DEV` stays). From 40/48
that still leaves comfortable headroom for the four stage-5 app HK MIDs and the deferred
diagnostic packets **without** an `sbn_client.so` rebuild — so the conclusion that the cap raise
can be dropped from the plan survives, even though the reasoning behind it was wrong.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` A per-MID disposition recorded with its evidence — device-disabled, command-produced, or event-driven — not a blanket "dead" verdict.
- [x] `AC2` `CFE_SB_SUBS` and `SBN` resolved: unsubscribed and their columns removed from the schema, or scheduled. If `SBN` is scheduled instead of dropped, the five-variant payload problem MUST be modelled first.
- [x] `AC3` `RADIO_DEV` decided on its merits — kept as an event-driven prox-link indicator, or dropped — with the reason recorded.
- [x] `AC4` `ST_DEV` explicitly left alone here and its resolution deferred to the star-tracker configuration decision (`AINOS3-86` / `AINOS3-91`).
- [x] `AC5` Post-change subscription count recorded against the 48 cap, with the headroom available to `AINOS3-110` and `AINOS3-120` stated.
- [x] `AC6` A live check that no *surviving* subscription became silent as a side effect.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-08-25 · scope corrected before the ticket was ever worked

#### In plain terms

The ticket was written as "delete four feeds that never send anything". Tracing each one back to
its source changed that: one must be kept, one is a judgement call, and one would be actively
dangerous to switch on, because its single identifier carries five different payload layouts and
four of them would be read as garbage.

Written as "drop 4 dead MIDs"; corrected on review when each production path was traced to
source. One of the four must not be dropped, one is a judgement call, and one carries a
payload-overloading hazard that makes the obvious "just schedule it" fix actively dangerous.
The net cap relief drops from 4 slots to 2-3, which does not change the plan it feeds.

### 2026-08-25 · ⚠ BLOCKED — dropping any column breaks the deployed IF model

#### In plain terms

Deleting the empty columns killed the live detector on the very first frame — it expects exactly
894 inputs, matched by name, and the deleted columns were among them. The detector was down about
four minutes until the change was reverted. The lesson, previously unwritten anywhere: adding a
column is safe, removing one is a retraining job rather than a configuration edit.

`AC1` and `AC3` are answered (below). `AC2` was attempted and **reverted**: the three drops
deploy cleanly and then kill OnAIR on the first frame.

```
ValueError: X has 876 features, but IsolationForest is expecting 894 features as input.
```

**Root cause.** All nine dropped columns are in the deployed model's own feature set —
`iforest_per_mode_v5_invariant_bolstered.pkl` → `schema.scalar_columns` contains every one of
`CFE_SB_SUBS.{PktSegment,TotalSegments,Entries,Entry}`, `RADIO_DEV.{DeviceCounter,DeviceConfig,
ProxSignal}` and `SBN.{ProtocolIdx,ModuleStatus}`. Nine columns × 2 derived features = the 18
missing. The model binds by column **name**, which is why AINOS3-95 could *add* 92 columns
across stages 2a/2b without incident — **adding is safe, removing is a breaking change.**

⚠ The wider rule, which was not written down anywhere before this: **the deployed detector
pins the schema.** Column removal is a model-retrain operation, not a config edit. That
applies to `AINOS3-109` (`AINOS3-109`) too if it ever removes rather than
restores, and it is why this had to be found by running rather than by review.

**Service impact:** OnAIR crash-looped from deploy until revert (~4 min). Reverted with
`git checkout nos3_security_tlm.json`; verified recovered at 451 columns, writing normally.

**Findings that stand regardless (AC1, AC3):**

| MID | Why silent | Disposition |
|---|---|---|
| `CFE_SB_SUBS` `0x080D` | command-produced (`CFE_SB_SEND_PREV_SUBS_CC`), **0 scheduler entries** | drop — at a retrain |
| `SBN` `0x08DC` | command-produced, **0 scheduler entries** | drop — at a retrain. ⚠ never "fix" by scheduling: one MID, **five** payload structs (`sbn_cmds.c:257-491`), so four variants would mis-parse |
| `RADIO_DEV` `0x0931` | 0 scheduler entries, 0 TO routes; published only opportunistically from the radio proxy task (`generic_radio_app.c:537`) | drop — and it is **fully redundant**: `GENERIC_RADIO_Device_HK_tlm_t` inside `RADIO_HK` `0x0930` carries the identical three fields and **does** arrive (measured `0` vs `RADIO_DEV`'s `[0]` sentinel across 21,269 frames) |
| `ST_DEV` `0x0936` | star tracker **disabled by default** (`ST.DeviceEnabled = 0`) | **keep** — configuration, owned by `AINOS3-86`/`AINOS3-91` |

The three structs are annotated `⚠ UNSUBSCRIBED … do not re-add without reading this` in
`message_headers.py`, carrying the SBN five-variant hazard next to the code, so the analysis
is not lost by the revert.

**Recommended re-scope.** Fold the removals into `AINOS3-101` (`AINOS3-101`), which
rebuilds the model anyway — dropping nine constant columns costs nothing there and is
impossible here. This ticket then becomes the *analysis of record* plus a one-line change to
the retrain's column list. ⚠ Net cap relief was never the point: it is 3 slots, and the
arithmetic already showed the remaining MID work fits at 45/48 without them.

### 2026-09-10 · RESOLVED at the schema freeze — pruned, not unsubscribed

#### In plain terms

Unblocked by noticing that two different things had been treated as one. What we listen to feeds
the live detector and cannot change; what we write to the data file feeds future training and is
free to change. Writing stopped for the nine dead columns while the subscriptions stayed, so the
file dropped from 479 to 470 columns with the live detector untouched. The star tracker's five
columns were deliberately kept, because another ticket was about to switch that device on and
they would start carrying real data. A new scanner then confirmed from the data — not from
reading code — that exactly 14 columns are empty in every frame, and no others.

Unblocked by `AINOS3-124` on the observation that the Blocked note had the layering wrong.
"Removal needs a retrain" is true of the **subscribed** schema and false of the **recorded**
one, and only the recorded one is what a corpus bakes in. They are different sets, changed by
different files:

| | set by | who consumes it | can it change now? |
|---|---|---|---|
| **subscribed** schema | `nos3_security_tlm.json` | the live OnAIR frame → every plugin, incl. the deployed IF | ❌ pinned by the IF's `scalar_columns` (by NAME) |
| **recorded** schema | that, minus `nos3_security.ini` `ExcludeColumns` | the CSV → the corpus → every FUTURE model | ✅ free — the prune is applied in the CSV writer only |

`csv_output_plugin.render_reasoning` computes the exclusion mask over its own header list and
writes the masked row; nothing upstream of it sees the prune. So pruning gets the corpus
cleaned **now**, at collection time where `AINOS3-124` needs it, with the live frame — and the
deployed IF's 894 features — untouched.

**Applied:** the 9 columns of `CFE_SB_SUBS` (4), `SBN` (2) and `RADIO_DEV` (3) added to
`ExcludeColumns`. Recorded schema **479 → 470** columns. Subscriptions retained.

**`ST_DEV` deliberately untouched (`AC4`).** Beyond the "configuration, not a dead MID"
argument the ticket already made, there is now a second and stronger one: `AINOS3-86`'s fix is
to **enable the star tracker**, which makes these 5 columns start carrying data. A column that
may go live during the sprint must ALREADY be in the frozen schema — pruning it would turn
`AINOS3-86` landing into a forced re-collect. **Silent is not the same as droppable.**

**Evidence, measured rather than argued (`AC1`, `AC3`, `AC6`).** Built
`training/schema_audit.py`, which reads a recorded session and reports every column that is
the `[0]` no-data sentinel in **100 %** of frames. Over 138,397 frames of the 2026-09-03
session it found **exactly 14** such columns — the 9 above plus `ST_DEV`'s 5 — and nothing
else. That is an independent confirmation of the disposition table from data, not from source
reading, and it is the AC6 regression check going forward (`--require-no-new-silent`).

⚠ A low sentinel fraction is normal, not a defect: any MID slower than the ~5 Hz frame rate
shows sentinel frames between arrivals (`CS` sits at 0.0001). Only 100 % is a finding.

**`AC5` — cap arithmetic.** Unchanged at **40/48 subscribed**, because nothing was
unsubscribed. The 3 slots stay claimed until the next IF retrain; as the ticket already
established, the remaining MID work (`AINOS3-110`, `AINOS3-120`) fits at 45/48 without them,
so nothing is gated on reclaiming them.

**Consequence to carry forward.** The deployed IF can no longer be replayed offline against a
post-freeze CSV without synthesizing the 9 constant columns back — they are in its
`scalar_columns` but no longer in the file. Live scoring is unaffected. The real unsubscribe
is on the `schema-vNext` list with an explicit trigger: **the next IF retrain**, which will be
fitted on the new corpus and therefore will not ask for them.

**Live-verified 2026-09-10** on a fresh `make launch-quiet`: sidecar reports
`kept_columns_count: 470`, OnAIR ran clean with no traceback, and `[iforest]` loaded and
scored normally at `n_raw_features=458` — the crash-loop the August attempt produced does not
occur, confirming the prune/unsubscribe distinction empirically.
