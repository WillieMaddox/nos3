---
key: AINOS3-115
slug: mid-stix-observable-map
type: Spike
epic: AINOS3-41 (coverage-expansion)
status: In Progress
priority: High
estimate: E 5 / T 1.5
opened: 2026-08-26
reopened: 2026-08-28
sprints: [28]
origin: AINOS3-96 (sparta-stix-ingest)
---

# AINOS3-115 — Map NOS3/OnAIR MIDs to STIX pattern arguments

**Summary:** Triage **all 254** distinct STIX IOB pattern arguments to a terminal observability state against NOS3 telemetry — the keystone map every downstream STIX use (per-technique coverage verification, attack generation, degeneracy-breaking) resolves through, and which is untrustworthy until it is complete rather than seeded.

## Description

The 254 distinct pattern arguments across the 855 IOB patterns
(`data/sparta/sparta_stix_latest.json`, sha256 `f9ce5b05…`) express what each technique should
produce as machine-comparable observables — e.g.
`[file:hashes != 'expected_hash_value' AND file:name = 'data_file']` or
`[x-opencti-memory:write_operation_count > 'threshold']`. Every downstream STIX use depends on
translating those arguments into NOS3 telemetry. This ticket builds that translation as a
persistent map in which **every argument reaches a terminal state**, not a partial seed.

⚠ **Why this is reopened (2026-08-28).** The first pass closed on 2026-08-26 with **12 rows
against the 254-argument vocabulary — 4.7 %** (`mid_stix_map.json`). It satisfied its
as-written AC ("seeded with observables we already record"), and its own log said so honestly —
but a **seed is not the deliverable the downstream work needs**, which was the original intent
(the owner: *"this is exactly the way I intended AINOS3-115 to be originally"*). The prior body
and log are preserved at [`../AINOS3-115-orig.md`](../AINOS3-115-orig.md) and in git.

The consequence of stopping at a seed is precise and load-bearing: every consumer treats an
**un-mapped** argument and a **genuinely-unobservable** one identically, because both surface as
`no-observable` on an incomplete map. That collapses exactly the distinction the map exists to
make —

- `AINOS3-116 --coverage` joins each IOB through this map; on 12 rows almost every IOB reports
  `no-observable`, so the observability report is not yet meaningful.
- `AINOS3-118`'s *"needs observability first"* vector tier is **defined** by this map's
  `no-observable` / `field-cannot-represent-value` states.
- the label-set-freeze degeneracy triage (`AINOS3-116 --degeneracy`) needs the map to tell a
  genuine degeneracy from a merely-unmapped one.

Until the map is complete, none of those can distinguish "we have not looked" from "there is
nothing to see."

⚠ **Scope reality, unchanged from the original and correct:** the mapping is **not 1-to-1**;
many arguments will have **no** NOS3 observable and that is itself a finding (the same
observability gap `AINOS3-95` surfaced for the logging workbook); the four/five states must all
be representable; and **verified/unverified is mandatory** — a recorded observable is not a
working one (R15 first watched the wrong clock field; CAM/SYN were subscribed but dead; derived
CFE_TBL columns are constant-0). `verified` requires cited live evidence; `unverified` is the
default.

One row per (argument → observable):
`{stix_object, stix_property, mid, field, representable, status, evidence, notes}`.
`representable` captures whether the field can *carry* the argument's value (a hash string, not
just a change flag) — "field exists but cannot represent the value" is a distinct, important
state from "no field at all".

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` **All 254 arguments triaged to a terminal state** — no argument left un-adjudicated. Verified rows cite live evidence; unverified is the default; the count reaching each state is reported.
- [ ] `AC2` All five states representable and used: `mapped-verified`, `mapped-unverified`, `field-cannot-represent-value`, `no-observable` (a coverage gap), `not-applicable-to-NOS3`.
- [ ] `AC3` `mid_stix_map.py --check` (the schema-drift guard) is **wired into the standing check suite**, not merely runnable — the loop this ticket's original hand-off named and never closed. A mapped field absent from `nos3_security_tlm.json` without an explicit unsubscribed marker fails the suite.
- [ ] `AC4` The observability-gap metric is the **headline**: *N of 254 arguments have no verified NOS3 observable*, with the by-construction fractions called out (`network-traffic`, `process`, `x-opencti-cryptographic-key`).
- [ ] `AC5` Hand-off stated and consistent: `AINOS3-116 --coverage` joins through the completed map; `AINOS3-118` promotes `unverified → verified` rows as it live-validates; the map is the **authority** for the `AINOS3-118` "needs observability first" tier so that no consumer treats un-mapped as unobservable.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-08-28 · reopened — the seed is not the deliverable

Reopened from Done. The 2026-08-26 pass built the machinery (`mid_stix_map.json` +
`training/mid_stix_map.py` with `--check`/`--report`/`--lookup`/`--args`) and 12 seed rows, and
flagged its own 245/254 gap — but the intended deliverable is the **complete** 254-argument
triage, which the downstream consumers (`AINOS3-116`, `AINOS3-118`, the degeneracy triage) all
resolve through. The original body/log are at `../AINOS3-115-orig.md` and in git; the machinery
is kept, the scope is corrected to completion. ⚠ Jira: this needs moving out of Done by the
owner — the crosswalk mirror is set to reflect the reopen.
