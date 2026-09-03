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
- **Recurring work:** the epic slug is stable (`stakeholder-rollout`); each
  occurrence is a new row tagged with the Jira sprint number (`rollout-s24`,
  `rollout-s25`, …), never an arbitrary counter.
- `—` in the Jira column = not yet created / not yet entered. **Leave `Status` blank for
  those rows** — the dash already says it, and duplicating the fact in two cells means two
  places to remember to edit when the key arrives.
- **A keyed row with a blank `Status` means `Backlog`.** So creating the ticket is a
  *one-cell* edit: paste the key, leave `Status` alone. Fill `Status` only when the ticket
  moves somewhere more specific than the backlog (`Sprint 28 · ◑ Committed`, `✅ Done`).

## The map

**One row per slug. This is the only table in this file.**

Before 2026-08-25 the mapping was spread across per-sprint and per-backlog tables, which held
**124 rows for 94 bindings** — and the copies had drifted: 15 slugs disagreed with themselves
about `Status` and 10 about `Title`, always because a ticket moved into a sprint and the
backlog copy was left to rot. Sprint membership already lives in the `Status` cell, so the
sprint tables were duplicating what the row already said. They are gone; the narrative for
each sprint stays below, where it belongs.

`check_crosswalk.py --strict` enforces the one-row rule, so a second copy cannot reappear.

Sorted by key; unkeyed slugs (`—`) last.

| Jira | Slug | Type | Epic (parent) | Title | Status |
|---|---|---|---|---|---|
| AINOS3-24 | incident-alerting | Epic | — | Incident-level security alerting | — |
| AINOS3-25 | one-alert-per-attack | Story | incident-alerting | One alert per attack | ✅ Done |
| AINOS3-26 | cluster-reporting-wiring | Task | incident-alerting | Wire cluster reporting into the plugin | ✅ Done |
| AINOS3-27 | incident-corpus-rescore | Task | incident-alerting | Incident-granularity corpus re-score | ✅ Done |
| AINOS3-28 | sparta-demo-app | Epic | — | SPARTA demo app | — |
| AINOS3-29 | demo-tier-a | Story | sparta-demo-app | Demo app Tier A with real results | ✅ Done |
| AINOS3-30 | extra-mids | Story | coverage-expansion | Subscribe extra MIDs to recover DEAD classes | Backlog (see note) |
| AINOS3-31 | classification-trust | Epic | — | Classification trust (close the mode gap) | — |
| AINOS3-32 | explainability | Epic | — | Explainability | — |
| AINOS3-33 | mode-aware-classifier | Story | classification-trust | Mode-aware classifier | ✅ Closed (neg. result) |
| AINOS3-34 | oof-label-accuracy | Task | classification-trust | Out-of-fold incident-label accuracy | ✅ Done |
| AINOS3-35 | warmup-tuning | Task | classification-trust | Mode-switch warmup tuning | ✅ Done + deployed |
| AINOS3-36 | mode-lock-artifact | Bug | classification-trust | "FSW idle mode-lock" CSV-parsing artifact | ✅ Resolved |
| AINOS3-37 | selective-mode-hybrid | Story | classification-trust | Selective per-mode hybrid | Sprint 26 · ✅ Done |
| AINOS3-38 | shap-attribution | Story | explainability | Per-incident SHAP attribution (offline) | ✅ Done |
| AINOS3-39 | counter-reliance-audit | Spike | classification-trust | Activity-counter reliance audit | ✅ Done (2026-07-29) |
| AINOS3-40 | surface-explanations | Story | explainability | Surface explanations in incident + demo | ✅ Done |
| AINOS3-41 | coverage-expansion | Epic | — | Detection coverage expansion | — |
| AINOS3-42 | stakeholder-rollout | Epic | — | Stakeholder rollout & feedback (recurring) | — |
| AINOS3-43 | rollout-s24 | Task | stakeholder-rollout | Stakeholder rollout — Sprint 24 | Ready |
| AINOS3-44 | tcn-feature | Story | coverage-expansion | TCN reconstruction-error feature (EX-0008) | Backlog |
| AINOS3-45 | corpus-instance-4 | Task | — | 4th corpus instance | ✖ Closed 2026-08-23 — superseded by AINOS3-100 |
| AINOS3-46 | demo-tier-bc | Story | — | Demo app Tier B/C (live execution / agent) | Backlog |
| AINOS3-47 | foundation-baseline | Story | coverage-expansion | Foundation-model zero-shot baseline | Backlog |
| AINOS3-48 | appdata-slot-map | Task | explainability | EVS AppData slot→app reference map | ✅ Done |
| AINOS3-49 | rollout-s25 | Task | stakeholder-rollout | Stakeholder rollout — Sprint 25 | ◑ Committed |
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
| AINOS3-63 | detector-gates | Epic | — | Complementary detector gates (parallel to the IF) | — |
| AINOS3-64 | rule-gate-detector | Story | detector-gates | Rule-gate: parallel state-change detector (R1–R5) + incident wiring | ✅ Done, deployed |
| AINOS3-65 | consistency-gate | Story | detector-gates | Consistency-check: per-sample bus-spoof detector | ✅ Done, deployed |
| AINOS3-66 | staleness-gate | Story | detector-gates | Staleness-check: telemetry-denial / frozen-stream detector | ✅ Done, deployed |
| AINOS3-67 | sb-command-rule | Task | detector-gates | Rule-gate R6: CFE_SB routing/subscription command rule | ✅ Done, deployed |
| AINOS3-68 | deepsad-revisit | Spike | — | Reopen Phase 5 (DeepSAD / VAE) feasibility | ⛔ Blocked (gated on AINOS3-30) |
| AINOS3-69 | next-ml-bet | Spike | — | Next big-ML bet (Phase 5/6 vs consolidate) | ✅ Done |
| AINOS3-70 | subscribe-recording-mids | Task | coverage-expansion | Subscribe the 16 Section-B recording MIDs (pipe cap 32→48; schema 383 cols) | ✅ Done (2026-07-16) |
| AINOS3-71 | detect-wiper-ransomware | Story | coverage-expansion | FM file-operation detector (EX-0010.01/.02) — rule-gate R11 | ✅ Done (2026-07-29) |
| AINOS3-72 | detect-downlink-exfil | Story | coverage-expansion | TO downlink-path detector (EXF-0003.02 / IMP-0006) — rule-gate R12+R13; re-pointed OnAIR to full `to`/`ci` HK | ✅ Done (2026-07-29) |
| AINOS3-73 | detect-fault-mgmt | Task | coverage-expansion | DE-0001 fault-management-disable detection | ○ Stretch |
| AINOS3-74 | watchdog-probe | Spike | coverage-expansion | Watchdog telemetry-packet existence probe | ○ Stretch |
| AINOS3-75 | borderline-footprint-check | Spike | coverage-expansion | Footprint-check EX-0001.02 / EX-0005.01 / DE-0006 | ○ Stretch |
| AINOS3-76 | rollout-s26 | Task | stakeholder-rollout | Stakeholder rollout — Sprint 26 | Sprint 27 · ✅ Done (2026-08-23) |
| AINOS3-77 | mode-transition-rule | Task | coverage-expansion | R14: flag ADCS mode-force (SET_MODE) IF blind spot | Sprint 27 · ✅ Done |
| AINOS3-78 | cluster-345-regression | Spike | coverage-expansion | Diagnose hybrid EX-0012.{03,04,05} label regression | Sprint 27 · ✅ Done |
| AINOS3-79 | detector-rigor | Epic | — | Detector hardening & measurement honesty | Open |
| AINOS3-80 | metric-provenance-audit | Spike | detector-rigor | Sweep reported metrics for in-sample optimism | Sprint 27 · ✅ Done |
| AINOS3-81 | hybrid-drift-soak | Task | detector-rigor | Long soak: live hybrid + calibration hold, no drift | Sprint 27 · ✅ Done |
| AINOS3-82 | benchmark-fayyaz | Spike | detector-rigor | Compare vs Fayyaz CuCD-ID NOS3/cFS dataset (Data in Brief 2026) | Sprint 27 · ✅ Done |
| AINOS3-83 | ci-command-feature | Task | coverage-expansion | Full-`ci` HK (0x0884) command-ingest detector | Backlog (was S27 stretch) |
| AINOS3-84 | drop-bus-activity-retrain | Task | classification-trust | Retrain dropping harmful bus-activity features | Backlog (fold into retrain-clean-corpus, never its own cycle) |
| AINOS3-85 | actuator-saturation-fidelity | Spike | — | Reach actuator saturation for the recovery-boundary test | Backlog |
| AINOS3-86 | inertial-false-alarms | Story | detector-rigor | Bring INERTIAL's false-alarm rate into the design band | Sprint 28 · ⏸️ Paused |
| AINOS3-87 | detect-eps-switch | Story | coverage-expansion | EX-0012.09 EPS switch toggle is undetected | Sprint 28 · ✅ Done |
| AINOS3-88 | signal-feasibility | Story | coverage-expansion | Ablate recorded Section-B MIDs for weak-class discrimination (split from AINOS3-30, 2026-08-19) | Sprint 27 · ✅ Done |
| AINOS3-89 | catch-rate-provenance-gap | Spike | detector-rigor | Published catch rates disagree with measurement | Backlog |
| AINOS3-90 | verify-nominal-incident-filter | Task | detector-rigor | Is `cluster=nominal` filtered from the operator view? | Sprint 28 · ✅ Done |
| AINOS3-91 | startracker-inert-fields | Spike | coverage-expansion | Star-tracker validity is intermittent and the device is off by default | Sprint 28 · ▶️ In Progress (stretch) |
| AINOS3-92 | soak-drift-hz | Task | detector-rigor | `analyze_soak_drift.py` uses the wrong sample rate | Sprint 28 · ✅ Done |
| AINOS3-93 | overlay-column-scope-mismatch | Bug | detector-rigor | `Catch` and `Incidents` are not comparable | Sprint 28 · ◑ Committed (stretch) |
| AINOS3-94 | coverage-table-schema | Spike | detector-rigor | Redesign the coverage-table schema | Backlog |
| AINOS3-95 | sparta-logging-gap-analysis | Spike | coverage-expansion | SPARTA logging best practices vs what we record | Sprint 28 · ✅ Done |
| AINOS3-96 | sparta-stix-ingest | Spike | coverage-expansion | Use the SPARTA STIX 2.1 dataset as ground truth | Sprint 28 · ✅ Done |
| AINOS3-97 | quarantine-stale-corpus | Task | corpus-integrity | Separate live corpus data from superseded | Sprint 28 · ◑ Committed (reparented from detector-rigor 2026-08-23) |
| AINOS3-98 | corpus-integrity | Epic | — | Corpus integrity — the corpus as a first-class, versioned artifact | — |
| AINOS3-99 | fold-variance-triage | Spike | corpus-integrity | Explain the per-instance F1 spread holding the tier column down | Sprint 28 · ✅ Done |
| AINOS3-100 | corpus-rebuild-steadyflight | Story | corpus-integrity | Recollect the classified attack set under the steady-flight protocol | Backlog (Sprint 29 target) |
| AINOS3-101 | retrain-clean-corpus | Story | corpus-integrity | Retrain + re-derive tiers on the clean corpus — is `ROBUST` reachable? | Backlog (Sprint 29 target) |
| AINOS3-102 | headless-sim-coverage-gap | Bug | detector-rigor | Payload sims absent from the headless launch | Sprint 28 · ✅ Done |
| AINOS3-103 | detect-cf-file-faults | Story | coverage-expansion | Detect CFDP file-operation faults | Sprint 28 · ✅ Done |
| AINOS3-104 | detect-adcs-gain-change | Story | coverage-expansion | Detect ADCS control-gain changes | Backlog |
| AINOS3-105 | test-encryption-bypass-observability | Story | coverage-expansion | Are encryptor bypass commands observable? | Backlog |
| AINOS3-106 | r15-latch-policy | Task | detector-rigor | R15 latch policy after a clock jump | Backlog |
| AINOS3-107 | frame-aliasing-semantics | Spike | detector-rigor | Frame aliasing and per-frame threshold meaning | Backlog |
| AINOS3-108 | subscription-hygiene | Task | coverage-expansion | Resolve four silent MID subscriptions | Sprint 28 · ⛔ Blocked (schema removal needs a retrain — fold into AINOS3-101) |
| AINOS3-109 | csv-prune-integrity-fields | Spike | corpus-integrity | The CSV prune drops security-relevant fields | Sprint 28 · ✅ Done |
| AINOS3-110 | build-missing-cfs-apps | Epic | — | Build the missing stock cFS apps | Backlog |
| AINOS3-111 | build-cs-app | Story | build-missing-cfs-apps | Build the CS checksum app | Sprint 28 · ✅ Done |
| AINOS3-112 | build-hs-app | Story | build-missing-cfs-apps | Build the HS health and safety app | Backlog |
| AINOS3-113 | build-mm-md-apps | Story | build-missing-cfs-apps | Build the MM and MD memory apps | Backlog |
| AINOS3-114 | ground-counter-reconciliation | Story | coverage-expansion | Reconcile ground and spacecraft command counters | Backlog |
| AINOS3-115 | mid-stix-observable-map | Spike | coverage-expansion | Map NOS3/OnAIR MIDs to STIX pattern arguments | Sprint 28 · ▶️ In Progress (reopened) |
| AINOS3-116 | stix-iob-pattern-index | Spike | coverage-expansion | Query the local STIX IOB↔technique↔pattern graph | Sprint 28 · ▶️ In Progress (reopened) |
| AINOS3-117 | coverage-triage-stix-v4 | Spike | coverage-expansion | Triage the SPARTA v4.0 techniques absent from our v3 matrix | Backlog |
| AINOS3-118 | stix-guided-attack-generation | Story | coverage-expansion | Generate and repair attack scripts from STIX IOB patterns | Sprint 28 · ▶️ In Progress |
| AINOS3-119 | retest-reopened-verdicts | Task | coverage-expansion | Re-test the verdicts the missing apps unblock | Backlog |
| AINOS3-120 | schedule-cfe-diag-packets | Story | coverage-expansion | Schedule the silent cFE diagnostic packets | Backlog |
| AINOS3-121 | if-scoring-audit | Spike | detector-rigor | Reproducible IF scoring + per-feature sensitivity/calibration audit | Sprint 28 · ✅ Done |
| AINOS3-122 | label-set-freeze | Story | corpus-integrity | Freeze the class label set | Sprint 28 · ◑ Committed |
| AINOS3-123 | per-subsystem-consistency-primitive | Story | detector-gates | Per-subsystem consistency gate | Backlog |
| AINOS3-124 | schema-freeze | Story | corpus-integrity | Freeze the recorded telemetry schema | Backlog |

## Sprint 28 (planning)

Workstream Sprint 7 (`SPRINT_28_PLAN.md`), theme "Read the Manual Before Rebuilding"
(2026-08-23 → 2026-09-06). Sprint 27 established that **corpus size and quality**, not
feature design, are the binding constraint (`AINOS3-88` NULL) and that 83 % of attack frames
sat inside the detector's blind window. The corpus rebuild was planned for this sprint and
then **deliberately re-ordered behind the two SPARTA spikes**: `AINOS3-96` gates the *label
set* (our scripts' technique claims are the classifier's classes) and `AINOS3-95` gates the
*schema* (subscribe before collecting, not after). The rebuild moves to Sprint 29, built on
verified labels and a settled schema.

Keys for the four new slugs were created and entered **2026-08-23**: `corpus-integrity`
(AINOS3-98), `fold-variance-triage` (AINOS3-99), `corpus-rebuild-steadyflight` (AINOS3-100)
and `retrain-clean-corpus` (AINOS3-101). The last two are the **Sprint 29** spine, created
early so the deferral is tracked on the board rather than in a plan document.

### AINOS3-95 / AINOS3-96 backlog — slugs reserved, awaiting Jira keys (2026-08-25/26)

Fifteen tickets produced by `AINOS3-95` (`sparta-logging-gap-analysis`) when it closed. **No
Jira keys yet** — `—` per this file's convention. Bodies are written and live in
`tickets/pending/<slug>.md`; run
`python3 components/onair/training/check_ticket_docs.py --pending` for a paste-ready
Summary/Type/Description queue, and each file prints its own `git mv` + `sed` promotion line.

⚠ **Rows below are slug reservations, not evidence a ticket exists.** Fill the Jira column as
each is created, then promote the file out of `tickets/pending/`.

Listed in **execution order** (dependency-ordered, not priority-ordered) — the rationale is in
`AINOS3-95`'s log. E ≈ 45 · T ≈ 12.5. Titles here are the **canonical short titles** and match
each ticket's `# <key> — <title>` heading; the full reasoning lives in the ticket body, not here.

### Sprint 29 (deferred spine — keys assigned 2026-08-23, scheduled next sprint)

### AINOS3-45 — CLOSED as superseded (2026-08-23)

The replacement work is materially different in protocol, mode scope and instance count, so
per this file's immutability rule it gets a **new slug and a new key**
(`corpus-rebuild-steadyflight`) rather than a re-scope in place. That is the `AINOS3-30`
lesson applied deliberately.

**`AINOS3-45` was closed as superseded on the board, 2026-08-23.** Do not re-scope or
reopen it; the replacement is `AINOS3-100`. Why the original protocol was
rejected is in [`AINOS3-100`](tickets/AINOS3-100.md).

## Sprint 26 (planning)

Workstream Sprint 5 (`SPRINT_26_PLAN.md`), theme "Section B Coverage & Close the Trust
Epic". The Section-B detections turn the 2026-07-16 recording-MID pass into validated
detections; the classification-trust carryover (`AINOS3-39`, `AINOS3-37`) closes that
epic. New slugs get Jira keys when the tickets are created — `subscribe-recording-mids`
documents already-done work (create + close it).

## Sprint 25 (prior)

Workstream Sprint 4 (`SPRINT_25_PLAN.md`), theme "Consolidate & Add Signal" —
executes the `next-ml-bet` (`AINOS3-69`) CONSOLIDATE verdict. All committed items
carried over from the Sprint 24 backlog; only `rollout-s25` is new. The two new
keys (`appdata-slot-map → AINOS3-48`, `rollout-s25 → AINOS3-49`) were created in
Jira 2026-07-15 and entered below.

### Backlog / carryover (slugs reserved; file rows here as they're created)

### Coverage-validation — Section A (in-scope-now techniques) · ✅ ALL 13 VALIDATED (2026-07-17)

From [`SPARTA_COVERAGE_TRIAGE.md`](SPARTA_COVERAGE_TRIAGE.md) / [`COVERAGE_VALIDATION_BACKLOG.md`](COVERAGE_VALIDATION_BACKLOG.md). All Tasks under `coverage-expansion` (AINOS3-41), delivered as unplanned mid-Sprint-25 work. All 13 validated live and **assigned to Sprint 25 + Done in Jira (2026-07-22)**.

### Detector gates (parallel to the IF) — mid-sprint 25

Four complementary runtime detector gates built during the Section-A validation
campaign (2026-07-16), each catching an attack class the deployed v5 IF structurally
misses (state-change / spoof / telemetry-freeze). Created as a dedicated epic
`detector-gates` (**AINOS3-63**) with the four child tickets **AINOS3-64…67**;
detailed ticket writeups (Summary/Description/AC + actuals) are in
[`SPRINT_25_PLAN.md`](SPRINT_25_PLAN.md).

## Sprint 24 (prior)

### Backlog / carryover (slugs reserved; file rows here as they're created)

## Sprint 23 (prior)

## ⚠ AINOS3-30 — key reuse, split 2026-08-19

`AINOS3-30` (`extra-mids`, *"Subscribe extra MIDs to recover DEAD classes"*) **is OPEN in
Jira and has never been closed.** `SPRINT_25_PLAN.md` describes it as "✅ CLOSED, NULL result,
DORMANT" — that refers to the Sprint-25 *investigation* being wound up, **not** to the Jira
issue, and it is misleading. Corrected there too.

Sprint 27 then reused the key for materially different work — collect a 359-column
weak-class corpus and ablate five candidate feature blocks (E 5 / T 1.5, vs the original
E 8 / T 2.5). That violated this file's immutability rule: a key is bound to one slug and one
scope, permanently.

**Resolution:** the Sprint-27 work was split out under the new slug **`signal-feasibility`**
and given its own key, **`AINOS3-88`** (assigned 2026-08-19; ✅ Done, NULL result).
`AINOS3-30` reverts to its original scope and stays **open**; nothing done in Sprint 27
should be used to close it.

**Do not close AINOS3-30 against the Sprint-27 results.** They answer a different question.
