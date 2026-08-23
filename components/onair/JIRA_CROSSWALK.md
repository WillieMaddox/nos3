# OnAIR-Security — Jira ID Crosswalk (durable, cross-sprint)

**The single source of truth mapping local planning slugs ↔ Jira keys.**

Why this file exists: planning docs use **slugs** (`extra-mids`, `rollout-s24`)
as local IDs, but Jira assigns its own sequential keys (e.g. `AINOS3-41`)
regardless of issue type. This table is the bridge between the two namespaces.

How to use it:

- **Enter/maintain Jira keys here, and only here.** This file is canonical. A
  sprint plan's Index may show a *read-only* Jira mirror for convenience (keys are
  immutable, so it can't drift), but keys are only ever added/changed in this file.
- **Append-only + immutable.** Add a row when a ticket is created. Once the
  `slug → Jira key` binding is set it never changes — safe to reference from any
  doc, any sprint, at any future point, even after the ticket is Done/Closed.
- **The `Status` column mirrors Jira, and Jira is the authority.** Format:
  `<Sprint N | Backlog> · <status>`. It drifts easily — nine rows were stale on
  2026-08-19 — so re-sync it whenever tickets move columns, and never infer a
  ticket's status from a sprint-plan document (that misreading is what let
  `AINOS3-30` be reused; see the note at the foot of this file).
- **Slugs go in planning docs; Jira keys go in Jira.** Never paste a slug or an
  old `NOS3-###` draft ID into a Jira summary/description/attachment — use the
  real Jira key there.
- **Recurring work:** the epic slug is stable (`stakeholder-rollout`); each
  occurrence is a new row tagged with the Jira sprint number (`rollout-s24`,
  `rollout-s25`, …), never an arbitrary counter.
- `—` in the Jira column = not yet created / not yet entered.

### Retired `NOS3-###` draft IDs

Early planning used a `NOS3-###` numbering that Jira never issued. Those IDs are
**retired**; the table below is the full map so a stale reference in old code or
docs can be resolved without re-deriving it from work descriptions. Anything
still carrying a `NOS3-###` is a bug — replace it with the key here.

| Retired draft ID | Real Jira key | Work |
|---|---|---|
| `NOS3-301` | **AINOS3-33** | Mode-aware classifier (closed, negative result) |
| `NOS3-302` | **AINOS3-34** | Out-of-fold incident-label accuracy |
| `NOS3-311` | **AINOS3-38** | Per-incident SHAP attribution (offline) |
| `NOS3-312` | **AINOS3-40** | Surface explanations in the incident record + demo |

`NOS3-211` (the coverage-overlay generator) predates the crosswalk and has no
Jira key; it survives only as a provenance comment in `app/gen_nos3_coverage.py`
and `app/nos3_overlay.js`.

## Sprint 26 (planning)

Workstream Sprint 5 (`SPRINT_26_PLAN.md`), theme "Section B Coverage & Close the Trust
Epic". The Section-B detections turn the 2026-07-16 recording-MID pass into validated
detections; the classification-trust carryover (`AINOS3-39`, `AINOS3-37`) closes that
epic. New slugs get Jira keys when the tickets are created — `subscribe-recording-mids`
documents already-done work (create + close it).

| Jira | Slug | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| AINOS3-41 | coverage-expansion | Epic | — | Detection coverage expansion | — |
| AINOS3-70 | subscribe-recording-mids | Task | coverage-expansion | Subscribe the 16 Section-B recording MIDs (pipe cap 32→48; schema 383 cols) | ✅ Done (2026-07-16) |
| AINOS3-71 | detect-wiper-ransomware | Story | coverage-expansion | FM file-operation detector (EX-0010.01/.02) — rule-gate R11 | ✅ Done (2026-07-29) |
| AINOS3-72 | detect-downlink-exfil | Story | coverage-expansion | TO downlink-path detector (EXF-0003.02 / IMP-0006) — rule-gate R12+R13; re-pointed OnAIR to full `to`/`ci` HK | ✅ Done (2026-07-29) |
| AINOS3-73 | detect-fault-mgmt | Task | coverage-expansion | DE-0001 fault-management-disable detection | ○ Stretch |
| AINOS3-74 | watchdog-probe | Spike | coverage-expansion | Watchdog telemetry-packet existence probe | ○ Stretch |
| AINOS3-75 | borderline-footprint-check | Spike | coverage-expansion | Footprint-check EX-0001.02 / EX-0005.01 / DE-0006 | ○ Stretch |
| AINOS3-31 | classification-trust | Epic | — | Classification trust (close the mode gap) | — |
| AINOS3-39 | counter-reliance-audit | Spike | classification-trust | Activity-counter reliance audit — rec: keep v3 | ✅ Done (2026-07-29) |
| AINOS3-37 | selective-mode-hybrid | Story | classification-trust | Selective per-mode hybrid | ○ Stretch |
| AINOS3-42 | stakeholder-rollout | Epic | — | Stakeholder rollout & feedback (recurring) | — |
| AINOS3-76 | rollout-s26 | Task | stakeholder-rollout | Stakeholder rollout — Sprint 26 | Sprint 27 · ✅ Done (2026-08-23) |

## Sprint 25 (prior)

Workstream Sprint 4 (`SPRINT_25_PLAN.md`), theme "Consolidate & Add Signal" —
executes the `next-ml-bet` (`AINOS3-69`) CONSOLIDATE verdict. All committed items
carried over from the Sprint 24 backlog; only `rollout-s25` is new. The two new
keys (`appdata-slot-map → AINOS3-48`, `rollout-s25 → AINOS3-49`) were created in
Jira 2026-07-15 and entered below.

| Jira | Slug | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| AINOS3-41 | coverage-expansion | Epic | — | Detection coverage expansion | — |
| AINOS3-30 | extra-mids | Story | coverage-expansion | Subscribe extra MIDs to recover DEAD classes | Backlog (see note) |
| AINOS3-32 | explainability | Epic | — | Explainability (Phase 7) | — |
| AINOS3-48 | appdata-slot-map | Task | explainability | EVS AppData slot→app reference map | ✅ Done |
| AINOS3-31 | classification-trust | Epic | — | Classification trust (close the mode gap) | — |
| AINOS3-39 | counter-reliance-audit | Spike | classification-trust | Activity-counter reliance audit | ◑ Committed |
| AINOS3-37 | selective-mode-hybrid | Story | classification-trust | Selective per-mode hybrid | ○ Stretch |
| AINOS3-42 | stakeholder-rollout | Epic | — | Stakeholder rollout & feedback (recurring) | — |
| AINOS3-49 | rollout-s25 | Task | stakeholder-rollout | Stakeholder rollout — Sprint 25 | ◑ Committed |

### Backlog / carryover (slugs reserved; file rows here as they're created)

| Jira | Slug | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| AINOS3-44 | tcn-feature | Story | coverage-expansion | TCN reconstruction-error feature (EX-0008) | Backlog |
| AINOS3-45 | corpus-instance-4 | Task | — | 4th corpus instance | Backlog |
| AINOS3-46 | demo-tier-bc | Story | — | Demo app Tier B/C (live execution / agent) | Backlog |
| AINOS3-47 | foundation-baseline | Story | coverage-expansion | Foundation-model zero-shot baseline | Backlog |
| AINOS3-68 | deepsad-revisit | Spike | — | Reopen Phase 5 DeepSAD after AINOS3-30 broadens signal | Backlog |
| AINOS3-79 | detector-rigor | Epic | — | Detector hardening & measurement honesty | Sprint 27 |
| AINOS3-77 | mode-transition-rule | Task | coverage-expansion | R14: flag ADCS mode-force (SET_MODE) IF blind spot | Sprint 27 · ✅ Done |
| AINOS3-78 | cluster-345-regression | Spike | coverage-expansion | Diagnose hybrid EX-0012.{03,04,05} label regression | Sprint 27 · ✅ Done |
| AINOS3-80 | metric-provenance-audit | Spike | detector-rigor | Sweep reported metrics for in-sample optimism | Sprint 27 · ✅ Done |
| AINOS3-81 | hybrid-drift-soak | Task | detector-rigor | Long soak: live hybrid + calibration hold, no drift | Sprint 27 · ✅ Done |
| AINOS3-82 | benchmark-fayyaz | Spike | detector-rigor | Compare vs Fayyaz CuCD-ID NOS3/cFS dataset (Data in Brief 2026) | Sprint 27 · ✅ Done |
| AINOS3-83 | ci-command-feature | Task | coverage-expansion | Full-`ci` HK (0x0884) command-ingest detector | Backlog (was S27 stretch) |
| AINOS3-84 | drop-bus-activity-retrain | Task | classification-trust | AINOS3-39 follow-up: retrain dropping harmful bus-activity features | Backlog |
| AINOS3-85 | actuator-saturation-fidelity | Spike | — | Injection that reaches actuator saturation (recovery-boundary test) | Backlog |
| AINOS3-86 | inertial-false-alarms | Story | detector-rigor | Bring INERTIAL's false-alarm rate into the design band (measured 33.6%) | Backlog |
| AINOS3-87 | detect-eps-switch | Story | coverage-expansion | EX-0012.09 EPS switch toggle is undetected (nothing catches it in steady flight) | Backlog |
| AINOS3-89 | catch-rate-provenance-gap | Spike | detector-rigor | Published per-technique catch rates disagree with measurement in both directions (EX-0014.04 98% vs 7.4%) | Backlog |
| AINOS3-90 | verify-nominal-incident-filter | Task | detector-rigor | Is `cluster=nominal` filtered from the operator view? Decides if INERTIAL's 71 false incidents/hr are visible | Backlog |
| AINOS3-91 | startracker-inert-fields | Spike | coverage-expansion | 5 ST_DEV star-tracker fields constant corpus-wide — ADCS sensor reporting nothing | Backlog |
| AINOS3-92 | soak-drift-hz | Task | detector-rigor | analyze_soak_drift.py --hz default wrong (4.2 vs ~5.6) — uptime bins off ~33% | Backlog |
| AINOS3-93 | overlay-column-scope-mismatch | Bug | detector-rigor | Overlay shows Catch (SUNSAFE-only) beside Incidents (zero SUNSAFE) as if comparable — invites false conclusions | Backlog |
| AINOS3-94 | coverage-table-schema | Spike | detector-rigor | Redesign the coverage table schema: mode as an axis, per-cell provenance, split detection/attribution/naming (9 defects in one sprint) | Backlog |
| AINOS3-95 | sparta-logging-gap-analysis | Spike | coverage-expansion | Gap-analyse SPARTA's Space Vehicle Logging Best Practices (~20-sheet workbook) against our recorded telemetry | Backlog |
| AINOS3-96 | sparta-stix-ingest | Spike | coverage-expansion | Ingest the SPARTA STIX 2.1 dataset; validate existing attack scripts against it and map unimplemented techniques | Backlog |
| AINOS3-97 | quarantine-stale-corpus | Task | detector-rigor | Inventory data/onair/csv (30 GB, 1,465 entries), map artifact->corpus dependencies, quarantine superseded collections | Backlog |
| AINOS3-88 | signal-feasibility | Story | coverage-expansion | Ablate recorded Section-B MIDs for weak-class discrimination (split from AINOS3-30, 2026-08-19) | Sprint 27 · ✅ Done |

### Coverage-validation — Section A (in-scope-now techniques) · ✅ ALL 13 VALIDATED (2026-07-17)

From [`SPARTA_COVERAGE_TRIAGE.md`](SPARTA_COVERAGE_TRIAGE.md) / [`COVERAGE_VALIDATION_BACKLOG.md`](COVERAGE_VALIDATION_BACKLOG.md). All Tasks under `coverage-expansion` (AINOS3-41), delivered as unplanned mid-Sprint-25 work. All 13 validated live and **assigned to Sprint 25 + Done in Jira (2026-07-22)**.

| Jira | Slug | Type | Epic (parent) | Title (SPARTA) | Status |
|---|---|---|---|---|---|
| AINOS3-50 | validate-pnt-geofence | Task | coverage-expansion | Validate EX-0002 PNT geofencing | ✅ Done |
| AINOS3-51 | validate-hw-commands | Task | coverage-expansion | Validate EX-0005.02 malicious hardware commands | ✅ Done |
| AINOS3-52 | validate-safemode-exploit | Task | coverage-expansion | Validate EX-0011 safe-mode exploit | ✅ Done |
| AINOS3-53 | validate-routing-tables | Task | coverage-expansion | Validate EX-0012.02 internal routing tables | ✅ Done |
| AINOS3-54 | validate-cdh-subsystem | Task | coverage-expansion | Validate EX-0012.10 C&DH subsystem | ✅ Done |
| AINOS3-55 | validate-flood-valid | Task | coverage-expansion | Validate EX-0013.01 valid-command flood | ✅ Done |
| AINOS3-56 | validate-flood-erroneous | Task | coverage-expansion | Validate EX-0013.02 erroneous-input flood | ✅ Done |
| AINOS3-57 | validate-bus-spoof | Task | coverage-expansion | Validate EX-0014.02 bus traffic spoofing | ✅ Done |
| AINOS3-58 | validate-inhibit-sc | Task | coverage-expansion | Validate DE-0002.03 inhibit spacecraft functionality | ✅ Done |
| AINOS3-59 | validate-safemode-evasion | Task | coverage-expansion | Validate DE-0005 safe-mode subversion | ✅ Done |
| AINOS3-60 | validate-audit-overflow | Task | coverage-expansion | Validate DE-0010 overflow audit log | ✅ Done |
| AINOS3-61 | validate-memory-compromise | Task | coverage-expansion | Validate PER-0001 memory compromise | ✅ Done |
| AINOS3-62 | validate-bus-segregation | Task | coverage-expansion | Validate LM-0002 bus-segregation lateral movement | ✅ Done |

### Detector gates (parallel to the IF) — mid-sprint 25

Four complementary runtime detector gates built during the Section-A validation
campaign (2026-07-16), each catching an attack class the deployed v5 IF structurally
misses (state-change / spoof / telemetry-freeze). Created as a dedicated epic
`detector-gates` (**AINOS3-63**) with the four child tickets **AINOS3-64…67**;
detailed ticket writeups (Summary/Description/AC + actuals) are in
[`SPRINT_25_PLAN.md`](SPRINT_25_PLAN.md).

| Jira | Slug | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| AINOS3-63 | detector-gates | Epic | — | Complementary detector gates (parallel to the IF) | — |
| AINOS3-64 | rule-gate-detector | Story | detector-gates | Rule-gate: parallel state-change detector (R1–R5) + incident wiring | ✅ Done, deployed |
| AINOS3-65 | consistency-gate | Story | detector-gates | Consistency-check: per-sample bus-spoof detector | ✅ Done, deployed |
| AINOS3-66 | staleness-gate | Story | detector-gates | Staleness-check: telemetry-denial / frozen-stream detector | ✅ Done, deployed |
| AINOS3-67 | sb-command-rule | Task | detector-gates | Rule-gate R6: CFE_SB routing/subscription command rule | ✅ Done, deployed |

## Sprint 24 (prior)

| Jira | Slug | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| AINOS3-31 | classification-trust | Epic | — | Classification trust (close the mode gap) | — |
| AINOS3-33 | mode-aware-classifier | Story | classification-trust | Mode-aware classifier | ✅ Closed (neg. result) |
| AINOS3-34 | oof-label-accuracy | Task | classification-trust | Out-of-fold incident-label accuracy | ✅ Done |
| AINOS3-35 | warmup-tuning | Task | classification-trust | Mode-switch warmup tuning | ✅ Done + deployed |
| AINOS3-36 | mode-lock-artifact | Bug | classification-trust | "FSW idle mode-lock" CSV-parsing artifact | ✅ Resolved |
| AINOS3-37 | selective-mode-hybrid | Story | classification-trust | Selective per-mode hybrid | Backlog |
| AINOS3-39 | counter-reliance-audit | Spike | classification-trust | Activity-counter reliance audit | Backlog |
| AINOS3-32 | explainability | Epic | — | Explainability (Phase 7 start) | — |
| AINOS3-38 | shap-attribution | Story | explainability | Per-incident SHAP attribution (offline) | ✅ Done |
| AINOS3-40 | surface-explanations | Story | explainability | Surface explanations in incident + demo | ✅ Done |
| AINOS3-41 | coverage-expansion | Epic | — | Detection coverage expansion | — |
| AINOS3-30 | extra-mids | Story | coverage-expansion | Subscribe extra MIDs to recover DEAD classes | Backlog (see note) |
| AINOS3-69 | next-ml-bet | Spike | — | Next big-ML bet (Phase 5/6 vs consolidate) | ✅ Done |
| AINOS3-42 | stakeholder-rollout | Epic | — | Stakeholder rollout & feedback (recurring) | — |
| AINOS3-43 | rollout-s24 | Task | stakeholder-rollout | Stakeholder rollout — Sprint 24 | Ready |

### Backlog / carryover (slugs reserved; file rows here as they're created)

| Jira | Slug | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| AINOS3-44 | tcn-feature | Story | coverage-expansion | TCN reconstruction-error feature (EX-0008) | Backlog |
| AINOS3-45 | corpus-instance-4 | Task | — | 4th corpus instance | Backlog |
| AINOS3-46 | demo-tier-bc | Story | — | Demo app Tier B/C (live execution / agent) | Backlog |
| AINOS3-47 | foundation-baseline | Story | coverage-expansion | Foundation-model zero-shot baseline | Backlog |
| AINOS3-48 | appdata-slot-map | Task | explainability | EVS AppData slot→app reference map (enables counter-reliance-audit) | Backlog |

## Sprint 23 (prior)

Workstream Sprint 2 (`SPRINT_23_PLAN.md`), shipped 2026-06. Keys entered + doc body
swept to keys 2026-07-06 (`sunsafe-pivot` has no key → stays a slug). The carryover
items (`extra-mids`, `tcn-feature`, `corpus-instance-4`, `demo-tier-bc`) advanced to
Sprint 24 and are listed above.

| Jira | Slug | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| AINOS3-24 | incident-alerting | Epic | — | Incident-level security alerting | — |
| AINOS3-25 | one-alert-per-attack | Story | incident-alerting | One alert per attack | ✅ Done |
| AINOS3-26 | cluster-reporting-wiring | Task | incident-alerting | Wire cluster reporting into the plugin | ✅ Done |
| AINOS3-27 | incident-corpus-rescore | Task | incident-alerting | Incident-granularity corpus re-score | ✅ Done |
| AINOS3-28 | sparta-demo-app | Epic | — | SPARTA demo app | — |
| AINOS3-29 | demo-tier-a | Story | sparta-demo-app | Demo app Tier A with real results | ✅ Done |
| — | sunsafe-pivot | Spike | — | SUNSAFE-only pivot decision | ✅ Resolved |

---

## ⚠ AINOS3-30 — key reuse, split 2026-08-19

`AINOS3-30` (`extra-mids`, *"Subscribe extra MIDs to recover DEAD classes"*) **is OPEN in
Jira and has never been closed.** `SPRINT_25_PLAN.md` describes it as "✅ CLOSED, NULL result,
DORMANT" — that refers to the Sprint-25 *investigation* being wound up, **not** to the Jira
issue, and it is misleading. Corrected there too.

Sprint 27 then reused the key for materially different work — collect a 359-column
weak-class corpus and ablate five candidate feature blocks (E 5 / T 1.5, vs the original
E 8 / T 2.5). That violated this file's immutability rule: a key is bound to one slug and one
scope, permanently.

**Resolution:** the Sprint-27 work is split out under the new slug **`signal-feasibility`**
and needs its own Jira key. `AINOS3-30` reverts to its original scope and stays **open**;
nothing done in Sprint 27 should be used to close it.

**Do not close AINOS3-30 against the Sprint-27 results.** They answer a different question.
