<!-- tickets-migrated -->

# Sprint 29 — "The Rebuild" 🏗️

**Component:** `OnAIR-Security`

**Created:** 2026-09-03

**Duration:** 2 weeks (2026-09-06 → 2026-09-20)

**Capacity:** ~16 E-pts / ~7–8 T-pts (solo, realistic focus factor)

**Context:** Sprint 28 did the reading. `AINOS3-96` (STIX) and `AINOS3-95` (logging workbook)
established, from external authority, *what our attacks actually are* and *what we should be
logging*; `AINOS3-122` froze the class label set on that basis; `AINOS3-111` built the CS
integrity app and settled what it can and can't observe; `AINOS3-99` established that the
per-instance F1 spread is a **generalisation limit**, not corpus size or the blind window.

Everything is now staged for the move Sprint 28 deliberately deferred: **rebuild the corpus on
verified labels and a settled schema, retrain on it, and answer — with a like-for-like control —
whether any class can reach `ROBUST`.**

**Sprint goal:** Collect a clean, per-mode, steady-flight corpus against the frozen schema and
label set, retrain and re-derive the confidence tiers on it, and produce the honest answer to
"is `ROBUST` reachable, and if not, why" — without moving the bar to get there.

⚠ **The pre-registered expectation (from `AINOS3-99`):** `ROBUST` is **probably not reachable via
corpus size or steady-flight collection alone** — the binding constraint is footprint
reproducibility across runs, and `min`-over-more-folds is a *stricter* bar with more instances. A
`ROBUST`-empty outcome is the **expected** result, not a failure; the deliverable is *why*, tied
to footprint reproducibility, with the like-for-like control that separates "cleaner data helped"
from "we evaluated an easier slice."

---

## Points — two metrics

Each item carries two independent estimates:

- **E — effort points** (Fibonacci 1·2·3·5·8): relative effort × **uncertainty** ×
  coordination. Sized for risk; comparative, not time.
- **T — time points** (**8 h = 1 point = 1 ideal engineering day**): hands-on-keyboard hours ÷ 8.
  Pure duration; excludes the risk premium and unattended wall-clock (corpus / soak runs), noted
  separately.

Read the gap: **T < E** ⇒ sized up for *risk*; **T ≈ E** ⇒ big-but-known.

---

## Index

**IDs are slugs; Jira keys are the real ticket keys.** The durable slug ↔ Jira-key mapping is
maintained in **[`JIRA_CROSSWALK.md`](JIRA_CROSSWALK.md)** (cross-sprint, append-only). The `Jira`
column below is a read-only mirror. All keys are assigned (carried from Sprint 28).

### Committed — the rebuild spine

| Jira | Slug | Type | Pri | E | T | Summary |
|---|---|---|---|--:|--:|---|
| AINOS3-98 | corpus-integrity | Epic | — | — | — | The corpus as a first-class, versioned artifact |
| AINOS3-108 | subscription-hygiene | Task | Medium | 2 | 0.5 | Resolve the four silent MIDs — clean the schema *before* it is frozen and collected |
| AINOS3-124 | schema-freeze | Story | **High** | 2 | 0.5 | Freeze the recorded telemetry schema (CS columns now in; the last GO cleared by `AINOS3-111`) |
| AINOS3-86 | inertial-false-alarms | Story | **High** | 5 | 1.5 | INERTIAL nominal FP 33.6 % — resolve the closed-loop-control question so collection can go **per-mode**, not SUNSAFE-only |
| AINOS3-100 | corpus-rebuild-steadyflight | Story | **High** | 5 | 1.5 | Recollect the classified attack set, per-mode, under `single_mode_hold_<MODE>`; a corpus manifest is a hard deliverable |
| AINOS3-101 | retrain-clean-corpus | Story | **High** | 3 | 1.0 | Retrain + re-derive tiers on the clean corpus — is `ROBUST` reachable? Closes `AINOS3-122 AC7` |
| AINOS3-122 | label-set-freeze | Story | **High** | 2 | 0.5 | Its one remaining AC (regenerate the derived artifacts on the frozen labels) is part of the `AINOS3-101` retrain |
| AINOS3-97 | quarantine-stale-corpus | Task | Medium | 3 | 0.75 | Separate the new clean corpus from the superseded; the dependency map (AC2) is done |

**Committed set:** E = **22** · T = **6.25** (+ unattended collection/soak wall-clock, ~15 h,
tracked separately).

### Second track — STIX coverage (committed *if the spine lands with room*; else Sprint 30)

These refine the attack set and observability map. They **feed a future increment**, not this
collection — the rebuild uses the current live-validated attack scripts, so the spine does not
wait on them. Pull them in only once the spine is on track.

| Jira | Slug | Type | Pri | E | T | Summary |
|---|---|---|---|--:|--:|---|
| AINOS3-115 | mid-stix-observable-map | Spike | **High** | 5 | 1.5 | The complete 254-argument MID↔STIX map (reopened) — unblocks `AINOS3-116 AC3` |
| AINOS3-116 | stix-iob-pattern-index | Spike | Medium | 3 | 0.75 | Run `--coverage`/`--degeneracy` across the queue once the full map lands |
| AINOS3-118 | stix-guided-attack-generation | Story | Medium | 5 | 2.0 | Repair/generate the remaining attack vectors from STIX IOB patterns |

### Stretch

| Jira | Slug | Type | E | T | Condition |
|---|---|---|--:|--:|---|
| AINOS3-93 | overlay-column-scope-mismatch | Bug | 2 | 0.5 | Presentational; cheapest if the coverage generator is already open |
| AINOS3-91 | startracker-inert-fields | Spike | 2 | 0.5 | Cheaper alongside `AINOS3-86`'s per-mode soaks than standing up its own stack |
| AINOS3-94 | coverage-table-schema | Spike | 3 | 0.75 | Stages 1–2 (cell contract + migrate derived columns); 3–5 gated on `AINOS3-86` |
| AINOS3-123 | per-subsystem-consistency-primitive | Story | 5 | 2.0 | New detector build; stack-dependent, not gating the rebuild |

---

## The critical path — why this order

The rebuild is a dependency chain, and getting the order wrong bakes a defect into both a new
corpus **and** a new retrain (the mistake that cost `EX-0012` wave-1 a full re-derivation).

1. **Settle and freeze the schema first — `AINOS3-108` → `AINOS3-124`.** Removing the four silent
   MIDs (`108`) is a schema change; do it *before* collection so the new corpus never carries dead
   columns, then freeze (`124`). Folding a column into a collection that has not started is free;
   redoing one that has is not.
2. **Un-gate per-mode collection — `AINOS3-86`.** The Sprint-28 finding is that INERTIAL may have
   been collected with no closed-loop control at all (33.6 % nominal FP). Resolve that **before**
   `100`, or the collection repeats SUNSAFE-only and the per-mode heads stay starved. ⚠ **If `86`
   slips, `100` proceeds per-mode where it can and SUNSAFE-held as the floor** — the rebuild does
   not block on it, but the INERTIAL slice is then provisional.
3. **Collect — `AINOS3-100`.** Per-mode, `single_mode_hold_<MODE>`, frozen schema + labels. The
   **corpus manifest** (scenario, date, schema sha256, FSW build, per-run technique/mode, frame
   counts) is a hard deliverable — its absence is what made four `AINOS3-80` metrics unverifiable.
   Operational discipline: full `make stop` + `make launch-quiet` per run, chunks of ≤ 8 runs,
   **never `nohup &`**, `csv.DictReader` never `awk -F','`, and **GSW up before `launch-quiet`**
   (build once with `make gsw`; it survives `make stop`). Read the *actively-growing* CSV, past
   OnAIR's ~30–60 s startup warmup.
4. **Retrain + re-derive tiers — `AINOS3-101`**, which **closes `AINOS3-122 AC7`** (regenerate the
   four derived artifacts on the frozen labels) and **absorbs `AINOS3-108`** (the deployed model
   stops reading the removed columns). Pre-registered traps: more instances make `ROBUST`
   *harder*; **do not move the 0.85 bar**; produce the like-for-like control. Deploy only through
   the `AINOS3-37` discipline (one-line ini flip, one-line rollback, live-verified) — **not
   deploying is a valid outcome.**
5. **Quarantine — `AINOS3-97`.** Once the clean corpus exists, separate it from the superseded 30
   GB so the next person cannot train on stale data by accident.

---

## Sprint 30 preview — deferred, recorded so it is a plan not a gap

- **The STIX coverage track** (`AINOS3-115`/`116`/`118`) if it does not fit here — it improves the
  *next* corpus increment, not this one.
- **`AINOS3-123`** per-subsystem consistency gate — a new detector, once the rebuild frees the stack.
- Whatever `AINOS3-101` concludes about `ROBUST`: if the answer is "not via data alone," Sprint 30's
  question becomes the **observability** lever (added signal / extra MIDs), which `AINOS3-69`
  already named as the binding constraint over model capacity.

---

## 📋 Not sprinted, and why

| Jira | Slug | Why not committed this sprint |
|---|---|---|
| AINOS3-115/116/118 | STIX coverage | Feed a *future* increment; the rebuild uses the current validated scripts, so they do not gate collection. Second-track / Sprint 30. |
| AINOS3-123 | per-subsystem-consistency-primitive | New detector build, stack-dependent; competes with the rebuild for the stack. Sprint 30. |
| AINOS3-94 | coverage-table-schema | Stages 3–5 remain gated on `AINOS3-86`; stages 1–2 are stretch. |
