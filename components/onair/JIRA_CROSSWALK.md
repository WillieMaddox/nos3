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
- **Slugs go in planning docs; Jira keys go in Jira.** Never paste a slug or an
  old `NOS3-###` draft ID into a Jira summary/description/attachment — use the
  real Jira key there.
- **Recurring work:** the epic slug is stable (`stakeholder-rollout`); each
  occurrence is a new row tagged with the Jira sprint number (`rollout-s24`,
  `rollout-s25`, …), never an arbitrary counter.
- `—` in the Jira column = not yet created / not yet entered.

## Sprint 25 (current)

Workstream Sprint 4 (`SPRINT_25_PLAN.md`), theme "Consolidate & Add Signal" —
executes the `next-ml-bet` (`NOS3_330`) CONSOLIDATE verdict. All committed items
carried over from the Sprint 24 backlog; only `rollout-s25` is new. The two new
keys (`appdata-slot-map → AINOS3-48`, `rollout-s25 → AINOS3-49`) were created in
Jira 2026-07-15 and entered below.

| Slug | Jira | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| coverage-expansion | AINOS3-41 | Epic | — | Detection coverage expansion | — |
| extra-mids | AINOS3-30 | Story | coverage-expansion | Subscribe extra MIDs to recover DEAD classes | ◑ Committed |
| explainability | AINOS3-32 | Epic | — | Explainability (Phase 7) | — |
| appdata-slot-map | AINOS3-48 | Task | explainability | EVS AppData slot→app reference map | ◑ Committed |
| classification-trust | AINOS3-31 | Epic | — | Classification trust (close the mode gap) | — |
| counter-reliance-audit | AINOS3-39 | Spike | classification-trust | Activity-counter reliance audit | ◑ Committed |
| selective-mode-hybrid | AINOS3-37 | Story | classification-trust | Selective per-mode hybrid | ○ Stretch |
| stakeholder-rollout | AINOS3-42 | Epic | — | Stakeholder rollout & feedback (recurring) | — |
| rollout-s25 | AINOS3-49 | Task | stakeholder-rollout | Stakeholder rollout — Sprint 25 | ◑ Committed |

### Backlog / carryover (slugs reserved; file rows here as they're created)

| Slug | Jira | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| tcn-feature | AINOS3-44 | Story | coverage-expansion | TCN reconstruction-error feature (EX-0008) | Backlog |
| corpus-instance-4 | AINOS3-45 | Task | — | 4th corpus instance | Backlog |
| demo-tier-bc | AINOS3-46 | Story | — | Demo app Tier B/C (live execution / agent) | Backlog |
| foundation-baseline | AINOS3-47 | Story | coverage-expansion | Foundation-model zero-shot baseline | Backlog |
| deepsad-revisit | — | Spike | — | Reopen Phase 5 DeepSAD after AINOS3-30 broadens signal | Backlog |

### Coverage-validation backlog — Section A (in-scope-now techniques)

From [`SPARTA_COVERAGE_TRIAGE.md`](SPARTA_COVERAGE_TRIAGE.md) / [`COVERAGE_VALIDATION_BACKLOG.md`](COVERAGE_VALIDATION_BACKLOG.md). All Tasks under `coverage-expansion` (AINOS3-41). Enter keys as tickets are created.

| Slug | Jira | Type | Epic (parent) | Title (SPARTA) | Status |
|---|---|---|---|---|---|
| validate-pnt-geofence | AINOS3-50 | Task | coverage-expansion | Validate EX-0002 PNT geofencing | Backlog |
| validate-hw-commands | AINOS3-51 | Task | coverage-expansion | Validate EX-0005.02 malicious hardware commands | Backlog |
| validate-safemode-exploit | AINOS3-52 | Task | coverage-expansion | Validate EX-0011 safe-mode exploit | Backlog |
| validate-routing-tables | AINOS3-53 | Task | coverage-expansion | Validate EX-0012.02 internal routing tables | Backlog |
| validate-cdh-subsystem | AINOS3-54 | Task | coverage-expansion | Validate EX-0012.10 C&DH subsystem | Backlog |
| validate-flood-valid | AINOS3-55 | Task | coverage-expansion | Validate EX-0013.01 valid-command flood | Backlog |
| validate-flood-erroneous | AINOS3-56 | Task | coverage-expansion | Validate EX-0013.02 erroneous-input flood | Backlog |
| validate-bus-spoof | AINOS3-57 | Task | coverage-expansion | Validate EX-0014.02 bus traffic spoofing | Backlog |
| validate-inhibit-sc | AINOS3-58 | Task | coverage-expansion | Validate DE-0002.03 inhibit spacecraft functionality | Backlog |
| validate-safemode-evasion | AINOS3-59 | Task | coverage-expansion | Validate DE-0005 safe-mode subversion | Backlog |
| validate-audit-overflow | AINOS3-60 | Task | coverage-expansion | Validate DE-0010 overflow audit log | Backlog |
| validate-memory-compromise | AINOS3-61 | Task | coverage-expansion | Validate PER-0001 memory compromise | Backlog |
| validate-bus-segregation | AINOS3-62 | Task | coverage-expansion | Validate LM-0002 bus-segregation lateral movement | Backlog |

### Detector gates (parallel to the IF) — mid-sprint 25 (slugs reserved; create tickets)

Four complementary runtime detector gates built during the Section-A validation
campaign (2026-07-16), each catching an attack class the deployed v5 IF structurally
misses (state-change / spoof / telemetry-freeze). Proposed as a dedicated epic
`detector-gates`; alternatively park all four under `coverage-expansion` (AINOS3-41).
`—` = ticket not yet created / key not yet entered.

| Slug | Jira | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| detector-gates | — | Epic | — | Complementary detector gates (parallel to the IF) | — |
| rule-gate-detector | — | Story | detector-gates | Rule-gate: parallel state-change detector (R1–R5) + incident wiring | ✅ Done, deployed |
| consistency-gate | — | Story | detector-gates | Consistency-check: per-sample bus-spoof detector | ✅ Done, deployed |
| staleness-gate | — | Story | detector-gates | Staleness-check: telemetry-denial / frozen-stream detector | ✅ Done, deployed |
| sb-command-rule | — | Task | detector-gates | Rule-gate R6: CFE_SB routing/subscription command rule | ✅ Done, deployed |

## Sprint 24 (prior)

| Slug | Jira | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| classification-trust | AINOS3-31 | Epic | — | Classification trust (close the mode gap) | — |
| mode-aware-classifier | AINOS3-33 | Story | classification-trust | Mode-aware classifier | ✅ Closed (neg. result) |
| oof-label-accuracy | AINOS3-34 | Task | classification-trust | Out-of-fold incident-label accuracy | ✅ Done |
| warmup-tuning | AINOS3-35 | Task | classification-trust | Mode-switch warmup tuning | ✅ Done + deployed |
| mode-lock-artifact | AINOS3-36 | Bug | classification-trust | "FSW idle mode-lock" CSV-parsing artifact | ✅ Resolved |
| selective-mode-hybrid | AINOS3-37 | Story | classification-trust | Selective per-mode hybrid | Backlog |
| counter-reliance-audit | AINOS3-39 | Spike | classification-trust | Activity-counter reliance audit | Backlog |
| explainability | AINOS3-32 | Epic | — | Explainability (Phase 7 start) | — |
| shap-attribution | AINOS3-38 | Story | explainability | Per-incident SHAP attribution (offline) | ✅ Done |
| surface-explanations | AINOS3-40 | Story | explainability | Surface explanations in incident + demo | ✅ Done |
| coverage-expansion | AINOS3-41 | Epic | — | Detection coverage expansion | — |
| extra-mids | AINOS3-30 | Story | coverage-expansion | Subscribe extra MIDs to recover DEAD classes | Backlog |
| next-ml-bet | — | Spike | — | Next big-ML bet (Phase 5/6 vs consolidate) | ✅ Done |
| stakeholder-rollout | AINOS3-42 | Epic | — | Stakeholder rollout & feedback (recurring) | — |
| rollout-s24 | AINOS3-43 | Task | stakeholder-rollout | Stakeholder rollout — Sprint 24 | Ready |

### Backlog / carryover (slugs reserved; file rows here as they're created)

| Slug | Jira | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| tcn-feature | AINOS3-44 | Story | coverage-expansion | TCN reconstruction-error feature (EX-0008) | Backlog |
| corpus-instance-4 | AINOS3-45 | Task | — | 4th corpus instance | Backlog |
| demo-tier-bc | AINOS3-46 | Story | — | Demo app Tier B/C (live execution / agent) | Backlog |
| foundation-baseline | AINOS3-47 | Story | coverage-expansion | Foundation-model zero-shot baseline | Backlog |
| appdata-slot-map | AINOS3-48 | Task | explainability | EVS AppData slot→app reference map (enables counter-reliance-audit) | Backlog |

## Sprint 23 (prior)

Workstream Sprint 2 (`SPRINT_23_PLAN.md`), shipped 2026-06. Keys entered + doc body
swept to keys 2026-07-06 (`sunsafe-pivot` has no key → stays a slug). The carryover
items (`extra-mids`, `tcn-feature`, `corpus-instance-4`, `demo-tier-bc`) advanced to
Sprint 24 and are listed above.

| Slug | Jira | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| incident-alerting | AINOS3-24 | Epic | — | Incident-level security alerting | — |
| one-alert-per-attack | AINOS3-25 | Story | incident-alerting | One alert per attack | ✅ Done |
| cluster-reporting-wiring | AINOS3-26 | Task | incident-alerting | Wire cluster reporting into the plugin | ✅ Done |
| incident-corpus-rescore | AINOS3-27 | Task | incident-alerting | Incident-granularity corpus re-score | ✅ Done |
| sparta-demo-app | AINOS3-28 | Epic | — | SPARTA demo app | — |
| demo-tier-a | AINOS3-29 | Story | sparta-demo-app | Demo app Tier A with real results | ✅ Done |
| sunsafe-pivot | — | Spike | — | SUNSAFE-only pivot decision | ✅ Resolved |
