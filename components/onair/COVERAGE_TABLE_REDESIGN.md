# Coverage table — redesign proposal

**Component:** `OnAIR-Security` · **Written:** 2026-08-23 · **Status:** proposal, not accepted
· **Slug:** `coverage-table-schema`

Design note for the per-technique coverage table that drives
[`V5_DETECTOR_COVERAGE.md`](V5_DETECTOR_COVERAGE.md)'s matrix and the SPARTA overlay panel
(`app/nos3_coverage.js` → `app/sparta_coverage.html`). It argues the table's **schema** is
the defect, proposes a replacement, and stages the migration.

This is a proposal. Nothing here is built.

---

## 1. Why — the evidence

Sprint 27 found **nine** distinct defects in this one artifact:

| # | Defect | Root cause (§2) |
|---|---|---|
| 1 | `EX-0012.09` catch rate 99 % → **0 %** | C1 hidden mode scope |
| 2 | `EX-0014.04` published 98 % vs **7.4 %** re-measured | C3 no provenance |
| 3 | `EX-0012.08` / `EX-0014.04` credited to the anomaly detector; actually rule-gate catches | C2 three questions in one row |
| 4 | INERTIAL nominal false alarms 0.00 % → **33.6 %** | C1 mode invisible |
| 5 | Four techniques published `ROBUST`; **none** met the published rule | C3 unreproducible cell |
| 6 | Explanations built from the **pre-hybrid** model for three weeks | C3 no provenance |
| 7 | `SIBLING` / `LOW-STABLE` — pseudo-tiers never in the published taxonomy | C2 two axes in one column |
| 8 | `Catch` and `Incidents` cover **disjoint** populations, displayed adjacently | C1 hidden mode scope |
| 9 | Incident label accuracy 76.9 % → **42.3 %** (in-sample → OOF) | C3 no provenance |

Nine defects, one artifact, one sprint — after which the table was still wrong twice more
in a single hour (`EX-0012.09` misread as stale data; `EX-0012.08` one step from being
ticketed as a detector defect that does not exist). That rate is a property of the design,
not of the care taken.

**Causes C1 and C3 alone account for six of the nine.**

---

## 2. Root causes

### C1 — The row's unit is wrong

One row per **technique**. But mode dominates nearly every question the table answers:

| Quantity | Range across the four ADCS modes |
|---|---|
| Nominal false-alarm rate | **0.00 % → 33.6 %** |
| Attack-frame naming accuracy | **10.0 % → 34.9 %** |
| Cluster-level naming accuracy | **14.8 % → 45.6 %** |

The true unit is **technique × mode**. Because the row cannot express that, every column
resolves it silently — and *differently*:

- `Catch` → **SUNSAFE only**
- `Incidents` → attributed to the attack's **first corruption frame's mode** (so: 91 PASSIVE,
  23 INERTIAL, 1 BDOT, **0 SUNSAFE**)
- `tier` → averaged over **all four** modes via LOIO

Three different collapses, none visible, rendered side by side. `Catch` and `Incidents`
share **zero attacks**, yet sit in adjacent columns inviting comparison.

### C2 — One row answers three unrelated questions

*Did we see it? · Which detector saw it? · Can we name it?* These have different answers,
different evidence and different audiences, but occupy one row about one technique. So
`Catch` silently mixed IF detections with rule-gate catches (defect 3), and `tier` absorbed
`SIBLING`, which is cluster membership — an orthogonal axis — rather than a confidence
level (defect 7).

### C3 — Provenance is per-cell but displayed nowhere

Every cell has its own model, corpus and measurement date. AINOS3-80 established the
provenance convention for the *prose doc*; the table still renders bare numbers. As of
today `frame_rate` is the **last hardcoded numeric column** — everything else reads from a
generated artifact.

### C4 — `None` means three different things

`not measured`, `measured but below the 25 % display threshold`, and `not applicable` all
render as `—`, and then get compared anyway.

---

## 3. Proposed schema

A **cell contract**, not a visual refresh. Every numeric cell becomes:

```json
{
  "value": 0.80,
  "unit": "fraction_of_attack_frames",
  "state": "measured",
  "scope":      { "mode": "MODE_SUNSAFE", "n_runs": 3, "n_frames": 1322 },
  "provenance": { "class": "live-soak",
                  "model": "iforest_per_mode_v5_invariant_bolstered",
                  "corpus": "permode_replication_2026-08-15",
                  "date": "2026-08-15",
                  "source": "data/onair/models/permode_pilot.json" },
  "interval":   { "lo": 0.76, "hi": 0.84, "resampled": "runs" }
}
```

- **`state`** ∈ `measured` · `not-measured` · `not-applicable` · `suppressed` — fixes **C4**.
  `suppressed` carries the reason and the raw value.
- **`scope.mode`** is mandatory. A cell that is genuinely mode-independent (rule-gate
  catches, signal class) says `"mode": "any"` explicitly — fixes **C1**.
- **`provenance`** is mandatory; a missing one is a **build error**, mirroring the doc's
  "an untagged number is a bug" rule — fixes **C3**.
- **`interval.resampled`** states *what* was resampled, per the AINOS3-80 finding that
  resampling test rows alone understates uncertainty.

The row splits into three panes — fixing **C2**:

| Pane | Answers | Contents |
|---|---|---|
| **Detection** | did we see it | per-mode flag rate, IF lift vs own-run nominal |
| **Attribution** | which detector saw it | `IF` / `rule-gate R##` / `staleness` / `consistency`, live-verified date |
| **Naming** | can we name it | tier + the F1 folds behind it, cluster, top fields |

Detection becomes a **per-mode map**, not a scalar.

---

## 4. Migration

Staged, each stage independently useful and shippable:

| Stage | Work | Closes |
|---|---|---|
| **1** | Define the cell contract; add a validator that fails the build on a missing `state`/`scope`/`provenance` | C3, C4 |
| **2** | Migrate the already-derived columns (tier, cluster, explanation) into it — no re-measurement | C3 |
| **3** | Derive `frame_rate` from a cache the way tiers now are; per-mode, killing the last hardcoded numeric | C1, and **AINOS3-89**'s whole defect class |
| **4** | Split detection / attribution / naming in the generator; overlay follows | C2 |
| **5** | Per-mode rendering in the overlay + coverage matrix | C1 |

Stages 1–2 are schema work with no measurement cost. Stage 3 is the expensive one and
subsumes AINOS3-89 — that ticket fixes catch-rate *values* one at a time; stage 3 removes
the possibility of a hand-maintained value.

---

## 5. Consequences worth accepting deliberately

**The table will look much worse, and that is the point.** Making mode explicit turns one
number per technique into four cells, and most will read `not-measured` — because outside
SUNSAFE, they *are*. Today that gap is hidden by a column header nobody reads. After the
change it is the first thing a stakeholder sees. **This is a presentation regression and an
honesty improvement, and it needs to be briefed as such**, ideally alongside the ROBUST
correction rather than as a second surprise.

**It does not add coverage.** Nothing here detects one more attack. It stops us publishing
claims we cannot support, which is the failure mode this artifact actually has.

**Cost is dominated by stage 3**, which needs a per-mode attack corpus that does not yet
exist for PASSIVE and BDOT.

---

## 6. Sequencing

**Gate stages 3–5 on [AINOS3-86](JIRA_CROSSWALK.md) (INERTIAL false alarms, 33.6 %).**
Making mode a first-class axis while one mode's numbers are uninterpretable means building
a table whose most prominent new column is noise. Stages 1–2 can proceed regardless.

Related tickets, and the boundaries between them:

- **AINOS3-89** `catch-rate-provenance-gap` — whether the `Catch` *values* are right. Stage 3
  subsumes it; do not run both.
- **`overlay-column-scope-mismatch`** — the immediate presentational fix for C1 on the
  current schema. Worth doing now as a stopgap; superseded by stage 5.
- **AINOS3-90** `verify-nominal-incident-filter` — independent.
