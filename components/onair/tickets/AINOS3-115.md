---
key: AINOS3-115
slug: mid-stix-observable-map
type: Spike
epic: AINOS3-41 (coverage-expansion)
status: Open
priority: High
estimate: E 5 / T 1.5
opened: 2026-08-26
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

Suggested shape (`data/sparta/mid_stix_map.json`), one row per (argument → observable):
`{stix_object, stix_property, mid, field, representable, status, evidence, notes}`. `representable`
captures the subtler half of the owner's example: does the field carry the argument in a form that
can hold the required value (a hash string, not just a change flag)? A field that exists but
cannot represent the value is a distinct, important state from "no field at all". Reuse
`sparta_logging_gap.py`'s self-checking discipline: every named field must exist in
`nos3_security_tlm.json` or be explicitly marked unsubscribed, enforced by a check.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` `mid_stix_map.json` with a documented schema, seeded with observables we already record and use (e.g. R15's GPS/CFE_TIME fields → the GNTM-5/6/7/9/10 time arguments), each row verified/unverified with evidence for the verified.
- [ ] `AC2` A checker that fails if a mapped field is absent from `nos3_security_tlm.json` without an explicit unsubscribed marker, so the map cannot drift from the schema.
- [ ] `AC3` All four states representable and used: mapped+verified, mapped+unverified, field-exists-but-cannot-represent-value, no-observable (a coverage gap).
- [ ] `AC4` A reference dump (`--lookup <STIX arg>` and `--lookup <MID>`) so it is the quick reference the owner asked for, not just data.
- [ ] `AC5` Explicitly NOT required complete — initial commit is a seed plus machinery; the count of unmapped arguments is reported as the standing observability-gap metric.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
