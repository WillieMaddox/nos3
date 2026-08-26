---
key: AINOS3-115
slug: mid-stix-observable-map
type: Spike
epic: AINOS3-41 (coverage-expansion)
status: Done
priority: High
estimate: E 5 / T 1.5
opened: 2026-08-26
closed: 2026-08-26
origin: AINOS3-96 (sparta-stix-ingest)
---

# AINOS3-115 — Map NOS3/OnAIR MIDs to STIX pattern arguments

**Summary:** Build a growable, verified/unverified lookup from STIX IOB pattern arguments to NOS3 telemetry fields — the keystone every other STIX use depends on.

## Description

The 855 STIX IOB patterns in `data/sparta/sparta_stix_latest.json` express what each technique
should produce as machine-comparable observables — e.g.
`[file:hashes != 'expected_hash_value' AND file:name = 'data_file']` or
`[x-opencti-memory:write_operation_count > 'threshold']`. Every downstream STIX use
(pattern-based coverage verification, attack generation, the EX-0014.01-class degeneracy break)
depends on translating those pattern arguments into NOS3 telemetry. This ticket builds that
translation as a persistent, growable lookup.

⚠ **Scope reality, from the owner:** the mapping is **not 1-to-1**, many arguments will have
**no** NOS3 observable, and many that do will be hard to find. There are many subscribed *and*
unsubscribed MIDs to consider. The file is **not** expected to be complete initially — it starts
small (the fields we already record with confidence) and accretes. An unmappable pattern argument
is itself a finding — the same observability gap `AINOS3-95` surfaced for the logging workbook.

⚠ **Verified/unverified is mandatory.** This session proved repeatedly that a recorded observable
is not a working one — R15 first watched the wrong clock field, CAM/SYN were subscribed but dead,
derived CFE_TBL columns are constant-0, BootSource is a hardcoded constant. Every mapping row
carries a status: **`verified`** (demonstrated live that the field moves as the argument requires)
or **`unverified`** (plausible, not yet exercised). Unverified is the default; promotion needs
cited evidence.

Suggested shape (`components/onair/mid_stix_map.json`), one row per (argument → observable):
`{stix_object, stix_property, mid, field, representable, status, evidence, notes}`. `representable`
captures the subtler half of the owner's example: does the field carry the argument in a form that
can hold the required value (a hash string, not just a change flag)? A field that exists but
cannot represent the value is a distinct, important state from "no field at all". Reuse
`sparta_logging_gap.py`'s self-checking discipline: every named field must exist in
`nos3_security_tlm.json` or be explicitly marked unsubscribed, enforced by a check.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` `mid_stix_map.json` with a documented schema, seeded with observables we already record and use (e.g. R15's GPS/CFE_TIME fields → the GNTM-5/6/7/9/10 time arguments), each row verified/unverified with evidence for the verified.
- [x] `AC2` A checker that fails if a mapped field is absent from `nos3_security_tlm.json` without an explicit unsubscribed marker, so the map cannot drift from the schema.
- [x] `AC3` All four states representable and used: mapped+verified, mapped+unverified, field-exists-but-cannot-represent-value, no-observable (a coverage gap).
- [x] `AC4` A reference dump (`--lookup <STIX arg>` and `--lookup <MID>`) so it is the quick reference the owner asked for, not just data.
- [x] `AC5` Explicitly NOT required complete — initial commit is a seed plus machinery; the count of unmapped arguments is reported as the standing observability-gap metric.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-08-26 · DONE — seed planted, machinery built; 245/254 arguments are the standing gap

`components/onair/mid_stix_map.json` (12 seed rows) + `training/mid_stix_map.py` (`--check` /
`--report` / `--lookup` / `--args`). No stack needed — pure STIX-vs-schema analysis.

**`AC1` — seeded from evidence, not guesses.** The 254 distinct pattern arguments across the 855
IOB patterns were extracted first (`--args`), then rows written only where there is a defensible
NOS3 mapping. The verified rows each cite a **live-validated rule** — the R15 clock-delta
(SET_TIME) and R16 CFDP-command (NOOP) are the exemplars, exactly the AC1 case.

**`AC2` — the drift check works.** `mid_stix_map.py --check`: every mapped field must exist in
`nos3_security_tlm.json` (or the row is an explicit `no-observable` gap with `mid=null`). 0
errors on the seed. This is what stops the map rotting away from the schema, the same discipline
as `sparta_logging_gap.py`.

**`AC3` — all four states present and reported:**

| state | n | example (from the seed) |
|---|--:|---|
| verified | 4 | `x-opencti-time:delta_value` → `CFE_TIME.SecondsMET` (R15, live SET_TIME) |
| unverified | 4 | `x-opencti-sensor-data:gps_time` → `NOVATEL…SecondsIntoWeek` (R15 reads it, GPS-spoof not run) |
| field-cannot-represent-value | 1 | `file:hashes` → `CFE_ES.CFECoreChecksum` — a uint16 CRC computed once at boot, pruned from the CSV (AINOS3-109). The field exists and *still can't carry the value* |
| no-observable | 3 | `network-traffic:src_ref.value` — anonymous SBN; `process:image_ref` — no introspection; `x-opencti-cryptographic-key` — CryptoLib off-bus |

⚠ The `file:hashes` row is the one that proves the fourth state earns its place: without it the
map would silently record "we have a checksum" and hide that it is unusable.

**`AC4` — lookup works both directions.** `--lookup <STIX arg substring>` and `--lookup <MID or
field>` both resolve, printing the mapping, status, evidence and notes — the quick reference,
not just a data file.

**`AC5` — the gap metric is the headline, and it is honest.** ⚠ **245 of 254 STIX arguments have
no verified NOS3 observable yet.** The seed touches 11 of 66 object types — but those 11 are the
high-frequency ones (network-traffic, process, memory, command-log), so it covers **1006 of
1810 argument-occurrences** while leaving most *distinct* arguments unmapped. That number is the
standing observability-gap metric this ticket exists to expose, and it is expected to shrink as
`AINOS3-116`/`AINOS3-118` verify more rows — the map is seed + machinery, complete for neither
by design.

⚠ **Two structural findings that drop out immediately**, both confirming the AINOS3-95
observability thesis at STIX granularity:

- The single largest STIX object is **`network-traffic` (282 occurrences)** — and it is
  **structurally unobservable** on an anonymous publish/subscribe bus. A large fraction of
  SPARTA's IOB vocabulary assumes packet-level src/dst identity NOS3's cFS bus does not provide.
- **`process` (132)** and **`x-opencti-cryptographic-key` (55)** are the next: no process
  introspection (the apps that would surface it aren't built — `AINOS3-110..113`) and CryptoLib
  has no SB telemetry. Together with network-traffic, ~26% of all argument-occurrences are
  no-observable by construction, before any effort.

**Hand-off:** `AINOS3-116` (IOB index) joins its per-technique reports to this map's states;
`AINOS3-118` promotes `unverified → verified` rows as it live-validates repaired attacks
(the EX-0014.01 GPS-spoof is the first). `mid_stix_map.py --check` should join the standing
check suite.
