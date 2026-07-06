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

## Sprint 24 (current)

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
