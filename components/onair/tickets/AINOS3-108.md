---
key: AINOS3-108
slug: subscription-hygiene
type: Task
epic: AINOS3-41 (coverage-expansion)
status: Open
priority: Medium
estimate: E 2 / T 0.5
opened: 2026-08-25
sprints: [28]
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

- [ ] `AC1` A per-MID disposition recorded with its evidence — device-disabled, command-produced, or event-driven — not a blanket "dead" verdict.
- [ ] `AC2` `CFE_SB_SUBS` and `SBN` resolved: unsubscribed and their columns removed from the schema, or scheduled. If `SBN` is scheduled instead of dropped, the five-variant payload problem MUST be modelled first.
- [ ] `AC3` `RADIO_DEV` decided on its merits — kept as an event-driven prox-link indicator, or dropped — with the reason recorded.
- [ ] `AC4` `ST_DEV` explicitly left alone here and its resolution deferred to the star-tracker configuration decision (`AINOS3-86` / `AINOS3-91`).
- [ ] `AC5` Post-change subscription count recorded against the 48 cap, with the headroom available to `build-missing-cfs-apps` and `schedule-cfe-diag-packets` stated.
- [ ] `AC6` A live check that no *surviving* subscription became silent as a side effect.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-08-25 · scope corrected before the ticket was ever worked

Written as "drop 4 dead MIDs"; corrected on review when each production path was traced to
source. One of the four must not be dropped, one is a judgement call, and one carries a
payload-overloading hazard that makes the obvious "just schedule it" fix actively dangerous.
The net cap relief drops from 4 slots to 2-3, which does not change the plan it feeds.
