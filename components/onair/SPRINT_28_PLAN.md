# Sprint 28 — "Read the Manual Before Rebuilding" 📖

**Component:** `OnAIR-Security`

**Created:** 2026-08-23

**Duration:** 2 weeks (2026-08-23 → 2026-09-06)

**Capacity:** ~16 E-pts / ~7–8 T-pts (solo, realistic focus factor)

**Context:** Sprint 27 closed with its planned headline overturned. `AINOS3-88`
(signal-feasibility) returned a **documented NULL** — no block of added telemetry beat split
noise — and the reason it could not tell us more was **corpus size and quality**, not feature
design. The same sprint found that 83 % of attack frames sat inside the detector's own blind
window, and that the `ROBUST` tier had **never been supported by its own data**. Tiers are
now derived, and `ROBUST` is **empty**.

The obvious next move was to rebuild the corpus. **That move was planned and then
deliberately re-ordered**, because two SPARTA artifacts the stakeholder supplied
(`data/sparta/`) turn out to gate the rebuild rather than follow it:

- **`AINOS3-96` gates the label set.** Our 30-plus attack scripts *assert* which technique
  they implement, and those assertions are the classifier's classes. STIX 2.1 carries each
  technique's authoritative definition. Recollecting before checking them would bake any
  mislabel into a new corpus **and** a new retrain — and mislabelled results have already
  cost this project one full re-derivation (`EX-0012` wave-1).
- **`AINOS3-95` gates the schema.** If the logging workbook names telemetry we should record
  and can, we want it subscribed *before* collection, not after. Folding columns into a
  collection that has not started is free; redoing one that has is not. Precedent:
  `AINOS3-70` took the CSV 360 → 382 columns and needed an `sbn_client.so` rebuild.

**Sprint goal:** Establish, from external authority rather than from our own assumptions,
*what we should be logging* and *what our attacks actually are* — then close the one
confirmed detection gap and prepare a clean data estate, so Sprint 29's corpus rebuild is
built on verified labels and a settled schema.

---

## Points — two metrics

Each item carries two independent estimates:

- **E — effort points** (Fibonacci 1·2·3·5·8): relative effort × **uncertainty** ×
  coordination. Sized for risk; comparative, not time.
- **T — time points** (**8 h = 1 point = 1 ideal engineering day**): estimated
  hands-on-keyboard hours ÷ 8. Pure duration; excludes the risk premium and unattended
  wall-clock (corpus / soak runs), which is noted separately.

Read the gap: **T < E** ⇒ sized up for *risk*; **T ≈ E** ⇒ big-but-known.

---

## Index

**IDs are slugs; Jira keys are the real ticket keys.** The durable slug ↔ Jira-key mapping
is maintained in **[`JIRA_CROSSWALK.md`](JIRA_CROSSWALK.md)** (cross-sprint, append-only).
The `Jira` column below is a read-only mirror of that file. **All Sprint-28 keys are
assigned** — the four new slugs got keys on 2026-08-23 (`AINOS3-98`–`AINOS3-101`).

| Jira | Slug | Type | Pri | E | T | Summary |
|---|---|---|---|--:|--:|---|
| AINOS3-41 | coverage-expansion | Epic | — | — | — | Detection coverage expansion (signal lever) |
| AINOS3-96 | sparta-stix-ingest | Spike | **High** | 3 | 1.0 | STIX 2.1 as ground truth — do our scripts implement what they claim? **Gates the label set** |
| AINOS3-95 | sparta-logging-gap-analysis | Spike | **High** | 3 | 0.75 | SPARTA logging best practices vs what we record. **Gates the schema.** Re-sized from E 5 — see body |
| AINOS3-87 | detect-eps-switch | Story | Medium | 3 | 1.0 | `EX-0012.09` EPS switch toggle is caught by **nothing** — rule it, or reclassify it honestly |
| AINOS3-79 | detector-rigor | Epic | — | — | — | Detector hardening & measurement honesty |
| AINOS3-86 | inertial-false-alarms | Story | **High** | 5 | 1.5 | INERTIAL nominal FP measured **33.6 %**; mode unusable for detection. Best use of an otherwise-idle stack |
| AINOS3-90 | verify-nominal-incident-filter | Task | High | 1 | 0.25 | Does the operator view filter `cluster=nominal`? Decides if 71 false incidents/hr are visible |
| AINOS3-92 | soak-drift-hz | Task | Medium | 1 | 0.25 | `analyze_soak_drift.py --hz` 4.2 vs true ~5.6 — every uptime bin mislabelled ~33 % |
| AINOS3-98 | corpus-integrity | Epic | — | — | — | **NEW** — the corpus as a first-class, versioned artifact |
| AINOS3-99 | fold-variance-triage | Spike | Medium | 1 | 0.25 | Why does one instance score 0.00 and another 0.80? Sizes Sprint 29's collection |
| AINOS3-97 | quarantine-stale-corpus | Task | Medium | 3 | 0.75 | Inventory 30 GB / 1,465 entries; dependency-map **first**, then quarantine |

**Committed set:** E = **20** · T = **5.75**. See the [capacity note](#capacity-note) — this
is above the nominal 16 and the reasoning is stated there rather than hidden in the estimates.

**Stretch set:** E = **7**.

| Jira | Slug | Type | E | T | Condition |
|---|---|---|--:|--:|---|
| AINOS3-93 | overlay-column-scope-mismatch | Bug | 2 | 0.5 | Presentational; cheapest if the coverage generator is already open |
| AINOS3-94 | coverage-table-schema | Spike | 3 | 0.75 | **Stages 1–2 only** (cell contract + migrate derived columns). Natural companion to `AINOS3-96`'s STIX-as-build-source decision. Stages 3–5 stay gated on `AINOS3-86` |
| AINOS3-91 | startracker-inert-fields | Spike | 2 | 0.5 | Cheaper alongside `AINOS3-86`'s soaks than standing up its own stack |

---

## What changed from the first draft of this plan, and why

The first Sprint-28 draft committed the corpus spine (`fold-variance-triage` → `AINOS3-97` →
`corpus-rebuild-steadyflight` → `retrain-clean-corpus`, E 17) and deferred `AINOS3-95` /
`AINOS3-96` to Sprint 29 on the reasoning that *"they generate leads, and a lead cannot be
exploited until we can measure whether it helps."*

**That reasoning was half right and it had the dependency backwards.** It is true that
exploiting a lead needs a corpus. It does not follow that the corpus should be built first —
because the two spikes constrain *what the corpus should contain*:

| | If the spikes run first | If the rebuild runs first |
|---|---|---|
| **Labels** | Script-vs-technique mismatches found before collection; classes corrected once | Mismatches discovered after ~15 h of collection and a retrain — both re-done |
| **Schema** | Any subscribable-now telemetry folded in before the first run | New corpus obsolete at the schema level on arrival |
| **`AINOS3-87`** | The workbook's **EPS sheet** answers its "which MID would close it" branch | That branch answered by inspection, as before |

The straight swap is **8 E out, 6 E in** (`corpus-rebuild-steadyflight` 5 + `retrain-clean-corpus`
3 → `AINOS3-96` 3 + `AINOS3-95` 3, the latter re-sized down after measuring the workbook).
The freed capacity plus a now-idle stack is what makes `AINOS3-86` affordable.

**One honest caveat, stated up front.** `AINOS3-88` already tested "more recorded telemetry"
and returned a NULL, so a newly-named MID is not, on current evidence, *likely* to lift the
weak classes. What `AINOS3-95` changes is the **provenance of the candidates**: technique-indexed
from an external authority rather than chosen by us. Candidate selection was precisely the
weak joint in `AINOS3-88`'s seven-arm ablation.

**And the cost, stated equally plainly.** Two spikes at the head of the sprint means the
committed half produces *documents*, not detections — a second consecutive sprint without a
shipped detector, against a standing "more green" ask. `AINOS3-87` is the one committed item
that can ship a rule; `AINOS3-95`'s re-openable-UNSUBSCRIBED criterion is the other surface
where green can appear. Both are called out in their bodies.

---

## 🟩 EPIC AINOS3-41 — Detection coverage expansion

### AINOS3-96 — Use the SPARTA STIX 2.1 dataset as ground truth · `Spike` · **High** · E 3 · T 1.0 (~8h)

Body as scoped in [`SPRINT_27_PLAN.md`](SPRINT_27_PLAN.md). Promoted to **High** and placed
**first in the sprint** for a reason that ticket did not state: it gates the label set that
Sprint 29's rebuild and retrain will be built on.

**Why it runs before any collection.** The classifier's classes are our scripts' *claims*
about which technique they implement. A script whose behaviour does not match its technique's
STIX definition is a mislabelled class — and every downstream artifact (LOIO folds, cluster
taxonomy, tier column, explanation catalog) inherits that label. Collecting 15 h of fresh
data under an unverified label set, then retraining on it, would propagate the error into two
new artifacts before anyone checked. `EX-0012` wave-1 is the precedent: mislabelled results
cost a full re-derivation.

**Second, sharper payoff.** The tier column carries **telemetry-indistinguishable
multi-member clusters** — `EX-0012.{03,04,05}` share one identical fold triple
`[0.39, 0.45, 0.50]`, as do `EX-0012.12` / `EX-0014.01`. The first Sprint-28 draft named
"label taxonomy" as the fallback lever if a retrain returned null. **`AINOS3-96` *is* that
lever**, and running it first means the taxonomy may be corrected before we spend the
collection, not after.

⚠ **Day-1 setup:** `stix2` is **not installed** in the dev venv (`~/.virtualenvs/nos3`).
`pip install stix2`. The fetch must be documented and repeatable — API call or download path
— not a one-off manual step.

**Acceptance Criteria:** as in `SPRINT_27_PLAN.md`, plus two additions for this sprint:

- **Verdict per attack script**, not just a mismatch list: `implements-as-claimed` /
  `mislabelled (correct technique named)` / `partially implements` / `undecidable from STIX`.
  A count in each bucket is the headline result.
- **A written decision on the multi-member clusters** — does STIX support treating
  `EX-0012.{03,04,05}` as one class, or are they genuinely distinct techniques our telemetry
  cannot separate? Those are different problems with different fixes, and the tier column
  currently cannot tell them apart.

### AINOS3-95 — SPARTA logging best practices vs what we record · `Spike` · **High** · E 3 · T 0.75 (~6h)

Body as scoped in [`SPRINT_27_PLAN.md`](SPRINT_27_PLAN.md), with the estimate **revised down
from E 5 / T 1.5** on measurement rather than assumption.

**Re-sizing, with the evidence.** The ticket was written against "a ~20-sheet workbook" and
sized for a multi-day read. Inspecting
`data/sparta/Space_Vehicle_Logging_Best_Practices-Distro_A.xlsx` directly:

| Sheets | Shape |
|---|---|
| 13 subsystem sheets (Propulsion, ADCS, EPS, GN&C, C&DH, TT&C, SMS, TCS, Payload ×5) | 11–38 rows × 10 cols each |
| `SPARTA_Mapping` — the technique ↔ log-source index | 78 rows × 7 cols |
| `Index & Acronyms`, `Content of Log Records`, `SPARTA_Mapping_Abstract`, `REF_Info`, `Change_Log` | reference / metadata |

**~330 data rows in total.** The reading is half a day; the work is cross-referencing against
our 382-column schema. The Sprint-27 AC "every sheet must be read" is now cheap to honour in
full, and it stays — a partial pass would most likely miss `SPARTA_Mapping`, which is the
point of the artifact.

**Two things this sprint specifically wants from it:**

1. **The `EPS` sheet feeds `AINOS3-87` directly.** That ticket forks on "if nothing moves,
   name the MID that would close it". A 15-row authoritative list of what an EPS subsystem
   should log is the answer to that AC, sourced externally instead of inferred.
2. **The `ADCS` and `GN&C` sheets feed `AINOS3-86`** — INERTIAL's 33.6 % false-alarm floor
   is an attitude-control problem, and the workbook may name state we are not recording.

Expect the 5 Payload sheets to be **not modelled by NOS3**; read them anyway and record that
verdict, because "not modelled" is a legitimate and reusable answer.

⚠ **Day-1 setup:** `openpyxl` is **not installed** in the dev venv — required to open the
workbook at all. `pip install openpyxl`.

**Acceptance Criteria:** as in `SPRINT_27_PLAN.md`. The criterion that matters most for this
sprint is the fourth one — **any technique currently marked out-of-scope / UNSUBSCRIBED in
`V5_DETECTOR_COVERAGE.md` that the workbook says *is* loggable gets flagged explicitly.**
Those are re-openable verdicts, and they are the one place in this sprint where the committed
work can turn a red cell green.

### AINOS3-87 — `EX-0012.09` EPS switch toggle is undetected · `Story` · Medium · E 3 · T 1.0 (~8h)

Body as scoped in [`SPRINT_27_PLAN.md`](SPRINT_27_PLAN.md). The **only confirmed coverage
gap** on the board and the most direct available answer to "more green": measured across 3
independent runs in held SUNSAFE, IF lift **−0.4 ± 0.1** and **no rule-gate rule fired in any
run**, against a published **99 %** catch rate.

Both outcomes are wins and the ticket must not be written as though only one is:

- **A recorded field moves** → a cheap R1/R5/R6-style rule, sibling of R6–R14.
- **Nothing moves** → reclassified **UNSUBSCRIBED**, correcting a 99 % claim to an honest
  "structurally invisible", and naming the MID that would close it.

**Sequencing change:** run it **after `AINOS3-95`**, not before. The workbook's EPS sheet
turns the negative branch from "we could not find an observable" into "here is the
authoritative list of what should be observable, and here is which of it we do not
subscribe" — a materially stronger result for the same effort.

---

## 🟦 EPIC AINOS3-79 — Detector hardening & measurement honesty

### AINOS3-86 — Bring INERTIAL's false-alarm rate into the design band · `Story` · **High** · E 5 · T 1.5 (~12h)

Body as scoped in [`SPRINT_27_PLAN.md`](SPRINT_27_PLAN.md) — the escalating history
(0.00 % published → 0.54 % operational / 7.5 % raw at 60 min → **33.6 %** at a 600 s hold,
range 21.1–48.5 %), the three candidate causes, and the ⚠ **do not fix by tightening the
threshold alone** warning (tightening to a 0.1 % target drives false alarms to 0.00 % but
**collapses attack detection 60×**, 12.4 % → 0.2 %).

**Why it is affordable this sprint and was not in the first draft.** Its cost is dominated by
two ≥ 2 h **unattended** INERTIAL soaks. With the corpus rebuild deferred, the stack is idle
from day 1 — the soaks cost calendar, not attention. This is the single best use of that
idle time on the board.

**Why it is worth doing before Sprint 29's rebuild, specifically.** The deferred rebuild was
scoped **SUNSAFE-only**, because making mode a first-class axis while INERTIAL's own noise
floor sits at 33.6 % builds a column of noise
([`COVERAGE_TABLE_REDESIGN.md`](COVERAGE_TABLE_REDESIGN.md) §6). Fix INERTIAL now and Sprint
29's collection can be **per-mode** instead — which also un-gates `AINOS3-94` stages 3–5. The
deferral becomes a strict upgrade rather than a slip.

⚠ **Bounded commitment, stated so it cannot balloon.** The committed deliverable is the
**diagnosis** — distinguishing (1) training gap, (2) missing commanded target quaternion,
(3) genuinely long settling. Whether the *fix* lands this sprint depends on which one it is:

| cause | fix lands this sprint? |
|---|---|
| (2) missing `GENERIC_ADCS_INERTIAL_QUATERNION_CC` | **Yes** — command it, fix the scenario tooling, re-soak |
| (3) settling longer than the 250-frame warmup | **Yes** — set an INERTIAL-specific warmup from the measured settling time |
| (1) training gap (19,641 rows, one 116-min session) | **No** — the fix needs fresh nominal INERTIAL collection, which is Sprint 29 corpus work. Say so and carry it |

⚠ **Any change that suppresses alarms needs an attack-side check before deployment.** The
sun-acquisition suppression rule nearly shipped on a clean nominal correlation and would have
cost **66.8 %** of all detections. Validate on the data where it has to be *safe*, not only
where it looks good.

### AINOS3-90 — Is `cluster=nominal` filtered from the operator view? · `Task` · High · E 1 · T 0.25 (~2h)

Body as scoped in [`SPRINT_27_PLAN.md`](SPRINT_27_PLAN.md). **Run this on day 1.** One fact
decides whether INERTIAL's **71 false incidents per hour** are an invisible log-volume
annoyance or a credibility problem — and with `AINOS3-86` now committed, it sets that
ticket's urgency rather than deciding whether it runs at all. Evidence from the deployed
reporter path, not inference.

**Result:** ✅ DONE (2026-08-23) — **NO. Nothing filters it, at any layer.** The answer is
the credibility branch, and the ticket's implied cheap mitigation turns out to be a trap.

**Code evidence — the deployed reporter path has no cluster predicate.** Every closed
incident reaches the operator through `_handle_incident`
(`fsw/plugins/xgb_classifier/xgb_classifier_plugin.py:585`), which prints a
`[xgb_cls][INCIDENT #N] … → nominal` line and appends the row to `incident_*.csv`
unconditionally. There is no `if cluster == "nominal"` anywhere in the chain, and the three
sibling gates (`rule_gate`, `consistency_check`, `staleness_check`) write their own incident
files by the same unfiltered pattern. Nothing downstream re-reads those files with a filter
either — the coverage overlay in `app/` is a static offline artifact, and OnAIR publishes no
telemetry into COSMOS, so the console log and the CSV **are** the operator view.

**Data evidence — 55.8 false incidents/hour, all visible.** Measured on
`incident_2026-08-15T14-29-46-306680_pid11.csv`: an 86.9 h `MODE_INERTIAL` session whose
manifest (`scenarios/manifest_2026-08-15T14-29-48Z.json`) confines its attack batch to the
first 15 min. Restricting to the post-batch, definitively-nominal window — 86.6 h,
**4,836 incidents, 100 % `cluster=nominal`**, median 8 frames — gives **55.8 incidents/hour**.
The ticket's figure of 71/hr is the same order; treat 55.8 as the measured replacement.
Across all 113 archived incident files, 5,865 of 6,435 INERTIAL incidents (**91.1 %**) carry
`cluster=nominal`.

⚠ **Do not "just filter `cluster=nominal`" — it would cost 48.4 % of true attack frames.**
The mitigation is tempting because it is one predicate and it is 100 %-effective on the clean
window above. It is also exactly the shape of the sun-acquisition rule that nearly shipped on
a clean nominal correlation. Checked on the attack side first, per this sprint's standing
rule: in `loio_predictions_oof_v3hybrid_full.npz`, **48.4 % of the 79,932 true-attack frames
are themselves predicted `nominal`** (BDOT 54.2 % · PASSIVE 55.7 % · SUNSAFE 47.8 % ·
**INERTIAL 39.3 %**). Suppressing that cluster suppresses those frames too.

*Stated limit:* that 48.4 % is **frame-level**, and incidents aggregate frames by summed
top-1 probability, so the incident-level cost is lower — but it is not zero, and nobody has
measured it. A nominal-suppression filter is therefore **not** a free win and must not ship
without that measurement.

**Consequence for `AINOS3-86`:** urgency **confirmed High**. 55.8 visible false incidents per
hour in a mode with no attack running is a credibility problem in the operator's face, not a
log-volume annoyance, and the one-line cosmetic escape is closed.

**Side finding, not chased:** three archived incident files carry `cluster` values of `25`
and `15` in `MODE_PASSIVE` — integers where a label belongs, i.e. a header-version mismatch
between the writer and those files. 11 rows, all pre-dating the hybrid deployment. Noted for
`AINOS3-97`'s inventory rather than fixed here.

### AINOS3-92 — `analyze_soak_drift.py` uses the wrong sample rate · `Task` · Medium · E 1 · T 0.25 (~2h)

Body as scoped in [`SPRINT_27_PLAN.md`](SPRINT_27_PLAN.md). **Now on the critical path:**
`AINOS3-86`'s soaks are read by this tool, and it mislabels every uptime bin by ~33 %
(hardcoded 4.2 Hz vs a true ~5.6). Fix it **before** the first soak, not after. Derive the
rate from the data; keep `--hz` as an override; warn on > 10 % disagreement.

**Result:** ✅ DONE (2026-08-23) — **fixed, and the error was larger than the ticket said.**

**The rate is now derived, not assumed.** The side-file carries no clock at all — only
`frame_idx` — so `derive_hz()` reads `CFE_TIME.SecondsMET` from the `csv_out_*` log of the
same session, paired by `(pid, nearest timestamp)`; OnAIR opens the two ~0.5 s apart, so the
pairing is unambiguous. Two properties of that clock drove the implementation: MET is only
~0.25 Hz-granular in the HK packet, so per-sample diffs are useless (median `dt` = 4.0 s →
0.25 Hz) and only the endpoints over a long span are informative; and MET is **non-monotonic**
across the OnAIR double buffer, so the span is `max − min`, not `last − first`.

**Measured, across four 2026-08-15 sessions:** 5.551 · 5.460 · 5.100 · 4.783 Hz. The
hardcoded 4.2 was **24 % low against 5.551**, and the effect on the tool's own output is
worse than the ticket's ~33 %: the same 86.9 h soak reports **5,229 min at the derived rate
and 6,911 min at 4.2** — every uptime bin overstated by **32 %**.

**Guards, because a derived number can be wrong too:** rates outside 1–20 Hz are rejected, as
are MET spans under 60 s (startup jitter dominates) and sessions with no pair or no
`SecondsMET` column. When derivation fails and no `--hz` is given the tool warns on stderr and
falls back to a named `FALLBACK_HZ = 5.5` rather than a silent constant. `--hz` remains an
override and always wins, but is now checked: a > 10 % disagreement prints
`WARNING: --hz 4.2 disagrees with the derived rate 5.551 Hz by 24%`. The resolved rate and its
provenance print in the header and are recorded in the `--json` dump, so any future soak
result carries its own rate.

**Verification:** 10 tests in `training/test_soak_drift.py` covering derive, sub-second pair
skew, no-pair, short-span, missing column, insane rate, loud fallback, and both override
branches — all passing; plus all three paths exercised against the real 1.74 M-frame soak.

⚠ **Every soak number published before today used 4.2 Hz.** Their FP *rates* are unaffected
(a ratio of frame counts), but their **uptime axis is stretched ~32 %** — any claim of the
form "FP was flat through T+6 h" was really measuring T+4.5 h. Re-run `--json` on any archived
side-file before citing its bins.

---

## 🟨 EPIC AINOS3-98 — Corpus integrity: the corpus as a first-class artifact

**Why a new epic.** Four sprints of results trace back to properties of the corpus that
nobody owned: the blind-window collection defect (83 % of attack frames unusable), the
unrecorded IF training corpus (`AINOS3-80` F2 — four headline metrics `[unverifiable]`),
`csv_corpus_v3stage` being frozen and load-bearing for four deployed artifacts without that
being written down, and 30 GB of mixed live-and-superseded collections. This is not
data-hygiene housekeeping — it is the binding constraint on every measurement we publish.

**This sprint carries the epic's two preparatory items.** The rebuild itself
(`corpus-rebuild-steadyflight`, **AINOS3-100**) and the retrain (`retrain-clean-corpus`,
**AINOS3-101**) move to **Sprint 29**, where they will be built on `AINOS3-96`-verified labels
and an `AINOS3-95`-settled schema. Both have keys already — created early so the deferral is
tracked on the board rather than in a plan document — and are drafted in full in the
[Sprint 29 preview](#sprint-29-preview).

**Proposed reparenting:** `AINOS3-97` currently sits under `detector-rigor` (AINOS3-79). Move
it here. Parent changes are a normal Jira edit — only the `slug → key` binding is immutable.

### AINOS3-99 — Explain the per-instance F1 spread holding the tier column down · `Spike` · Medium · E 1 · T 0.25 (~2h)

*Why does the same technique score 0.00 on one spacecraft run and 0.80 on another?*

**Summary:** As an ML engineer, I want to know which *runs* produce the zero-F1 LOIO folds,
because the tier rule takes the **minimum** across folds, so a handful of bad runs — not the
model's average ability — is what is holding `ROBUST` empty.

**Description:** The derived tiers (`data/onair/models/classifier_tiers.json`, 26 classes,
3 LOIO folds) show enormous per-instance spread:

| class | fold F1s | min | max | tier |
|---|---|--:|--:|---|
| `IMP-0001` | `[0.00, 0.66, 0.80]` | 0.00 | 0.80 | HIGH-VAR |
| `EX-0012.09` | `[0.00, 0.00, 0.50]` | 0.00 | 0.50 | HIGH-VAR |
| `DE-0003.02` | `[0.07, 0.00, 0.65]` | 0.00 | 0.65 | HIGH-VAR |
| `EX-0012.08` | `[0.52, 0.00, 0.29]` | 0.00 | 0.52 | HIGH-VAR |
| `IMP-0003` | `[0.94, 0.11, 0.71]` | 0.11 | 0.94 | HIGH-VAR |

A class reaching 0.80 on one spacecraft run and 0.00 on another is not information-limited —
it is **instance-limited**. A single contaminated instance is already **ruled out**: zero-F1
folds distribute across all three instances (**9 / 6 / 6** of 26 classes).

That leaves the useful question — is the spread explained by the **blind-window collection
defect**? The answer sizes Sprint 29's collection, which is why a 2-hour desk spike runs a
sprint ahead of the ~15 h of wall-clock it governs.

**Acceptance Criteria:**

- Per-class, per-fold F1 cross-tabulated against the collecting run, from
  `loio_predictions_oof_v3hybrid_full.npz` and the corpus manifest — no re-training.
- For each zero-F1 fold, the fraction of that run's attack frames falling inside a
  post-mode-switch blind window (~45 s / 250 frames).
- A stated verdict with its limits: **blind-window-explained**, **partially explained**, or
  **unexplained** — and if unexplained, what else differs between the runs.
- A recommended instance count for Sprint 29, justified by the observed spread rather than
  assumed. "3, because that is what we had" is acceptable only if the evidence says so.
- ⚠ Note in the write-up that adding instances adds folds, and **min-over-more-folds is a
  stricter bar**.
- **Cross-check against `AINOS3-96`:** if a class's fold spread coincides with a script that
  STIX flags as mislabelled, that is a shared root cause and both tickets should say so.

### AINOS3-97 — Separate live corpus data from superseded · `Task` · Medium · E 3 · T 0.75 (~6h)

Body as scoped in [`SPRINT_27_PLAN.md`](SPRINT_27_PLAN.md). It stays in this sprint even
though the rebuild moved out, for two reasons: it produces the **artifact → corpus dependency
map** that `fold-variance-triage` needs to know which collection each LOIO instance came
from, and Sprint 29's collection must land in a clean estate rather than into 30 GB of
ambiguity.

⚠ **Dependency mapping comes first, and it is the whole risk.** `csv_corpus_v3stage` is
frozen and **still load-bearing** — the deployed classifier's LOIO, `cluster_taxonomy.json`,
`explanation_catalog.json` and the newly-derived `classifier_tiers.json` all trace to it.
"Pre-correction" does **not** mean "safe to move". Quarantine, not delete.

---

## Sprint 29 preview — the deferred corpus spine

Not committed here; recorded so the deferral is a plan rather than a gap. Both carry keys
already (**AINOS3-100**, **AINOS3-101**) and sit in the backlog against a Sprint-29 target.

### AINOS3-100 — Recollect the classified attack set under the steady-flight protocol · `Story` · E 5 · T 1.5 (~12h attended, ~15h unattended)

Recollect the classified attack set under the corrected protocol. `single_mode_hold_<MODE>`
commands a mode once and holds it — modes are sticky, demonstrated over 17,670 readings with
zero drift in an hour. On the pilot it took alert-eligible attack frames from
**16.8 % → 84.4 %** (16/16 runs exit 0); the replication ran 24/24 exit 0 at a 600 s pre-hold.
The tooling exists and is validated (`training/scenarios/run_attack_batch.py`, template
`batch_steadyflight_replication.json`).

**Now additionally constrained by this sprint:** labels verified by `AINOS3-96`, schema
settled by `AINOS3-95`, instance count set by `fold-variance-triage`, and — **if `AINOS3-86`
lands** — collected **per-mode** rather than SUNSAFE-only.

⚠ Operational discipline: full `make stop` + `make launch-quiet` per run (sim state persists
across a Tier 1.5 reset); chunks of ≤ 8 runs (Tier 1.5 reliability degrades with stack
uptime); **never `nohup &`**; parse with `csv.DictReader`, never `awk -F','`. A **corpus
manifest** (scenario, date, schema sha256, FSW build, per-run technique and mode, frame
counts) is a hard deliverable — its absence is what made four `AINOS3-80` metrics
`[unverifiable]`.

### AINOS3-101 — Retrain + re-derive tiers on the clean corpus — is `ROBUST` reachable? · `Story` · E 3 · T 1.0 (~8h)

Retrain and re-derive tiers on the clean corpus; the direct test of *"what will it take to
make them ROBUST again?"*. Designated test case **`IMP-0005`**: min F1 **0.8481** against a
`ROBUST` bar of 0.85 — it misses by **0.0019**.

⚠ Three traps, pre-registered now so they cannot be rationalised later:

1. **More instances make `ROBUST` *harder*.** The rule is min-F1 ≥ 0.85 across **all** folds;
   more instances means a stricter minimum. The mechanism is cleaner data per fold, not more
   of it.
2. **Do not move the bar.** 0.85 was published; `IMP-0005` missing by 0.002 is not a reason
   to lower it.
3. **Isolate data quality from scope change.** Current tiers average four modes. Produce the
   like-for-like control — tiers re-derived on `csv_corpus_v3stage` restricted to the same
   mode scope — or the comparison confounds cleaner data with narrower scope.

Deploy only through the `AINOS3-37` discipline: one-line ini change, one-line rollback,
live-verified, build tree synced. **Not deploying is a valid outcome.**

---

## 📋 Not sprinted, and why

| Jira | Slug | Why not this sprint |
|---|---|---|
| AINOS3-94 | coverage-table-schema | Stages 1–2 are **stretch**; stages 3–5 gated on `AINOS3-86`, which may un-gate them this sprint |
| AINOS3-89 | catch-rate-provenance-gap | **Subsumed** by `AINOS3-94` stage 3. Do not run both |
| AINOS3-45 | corpus-instance-4 | **Close as superseded** — see below |
| AINOS3-68 | deepsad-revisit | Stays gated. `AINOS3-88` returned NULL, so the gate did not open. ⚠ `AINOS3-95` could re-open it if it names a genuinely new signal source |
| AINOS3-83 | ci-command-feature | First AC already answered negatively; points at "document the bypass, close out-of-scope" |
| AINOS3-84 | drop-bus-activity-retrain | Needs a retrain to fold into; that moved to Sprint 29. Fold in there, never as its own cycle |
| AINOS3-30, -44, -46, -47, -85 | — | Backlog, unchanged |

### ⚠ AINOS3-45 — recommend **close as superseded**

`AINOS3-45` (`corpus-instance-4`) is scoped to collect another instance **of the collection
protocol we now know is defective** — ~83 % of attack frames inside the detector's blind
window. Executing it as written would add a fourth LOIO fold built from unusable data, which
is worse than not collecting, because the tier rule takes the **minimum** across folds.

The replacement work differs in protocol, mode scope and instance count, so per the
crosswalk's immutability rule it gets a **new slug and key** — `corpus-rebuild-steadyflight`,
**AINOS3-100**, created 2026-08-23 — rather than a re-scope in place. That is the `AINOS3-30`
lesson applied deliberately.

---

## Jira state

**Tickets created 2026-08-23** — all four new slugs carry keys, and
[`JIRA_CROSSWALK.md`](JIRA_CROSSWALK.md) is the canonical record:

| Jira | Slug | Type | Epic (parent) | Sprint |
|---|---|---|---|---|
| AINOS3-98 | corpus-integrity | Epic | — | 28 |
| AINOS3-99 | fold-variance-triage | Spike | corpus-integrity | 28 |
| AINOS3-100 | corpus-rebuild-steadyflight | Story | corpus-integrity | 29 (backlog) |
| AINOS3-101 | retrain-clean-corpus | Story | corpus-integrity | 29 (backlog) |

Remaining Jira actions:

- Decide **`rollout-s28`** — not committed (`AINOS3-76` delivered the 26 + 27 readout on
  2026-08-23, and a second readout 14 days later may not be worth the interrupt). Needs a new
  slug and key if it goes in.

---

## Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | **Two spikes at the head of the sprint produce documents, not detections** — second consecutive sprint without a shipped detector, against a "more green" ask | `AINOS3-87` is committed and can ship a rule; `AINOS3-95`'s re-openable-UNSUBSCRIBED criterion is the other green surface. Brief the readout on *what the spikes unblock*, not on their page count |
| 2 | **`AINOS3-95` finds nothing subscribable** — plausible, since `AINOS3-88` already returned NULL on added telemetry | Still a result: it converts "we should probably log more" from an open question into a measured verdict, and closes the observability hypothesis `AINOS3-69` has carried for three sprints |
| 3 | **`AINOS3-86` root-causes to the training gap (1)**, whose fix needs collection we deferred | Bounded commitment table in its body — diagnosis is the deliverable, the fix carries to Sprint 29 with the corpus work. Say so rather than half-fixing |
| 4 | **`AINOS3-96` finds mislabelled scripts**, invalidating part of the published coverage | That is the ticket working, not failing. It is also exactly why it runs **before** the rebuild. Budget readout time for a correction table, as Sprint 27 needed |
| 5 | **Committed E 20 vs nominal 16** | See capacity note — the overage is concentrated in `AINOS3-86`, whose cost is unattended, and the de-scope ladder names it first |
| 6 | **Day-1 dependency blockers** — `stix2` and `openpyxl` are both missing from the dev venv | Install before anything else; neither is more than a `pip install`, but `AINOS3-95` cannot open its own artifact without one |

---

## Capacity note

- **Effort:** committed E = **20** against a nominal ~16. Sprint 27 delivered 16 committed
  **plus** a stretch spike (≈ 18–21 E of demonstrated throughput), so 20 sits at the top of observed capacity rather than beyond it.
- **Time:** committed T = **5.75** (≈ 46 ideal hours) — inside the ~7–8 T band.

**The overage is deliberate and it is concentrated in one item.** `AINOS3-86` (E 5) is
committed *because* this sprint's shape makes it cheap: with the corpus rebuild deferred, the
stack is idle, and `AINOS3-86`'s cost is two ≥ 2 h unattended soaks. It is priced at E 5 for
uncertainty of *outcome* (three candidate causes), not for hands-on hours.

**De-scope ladder**, in order, if the sprint runs hot:

1. **`AINOS3-86`** (E 5) — down to its diagnosis half, then out entirely. It is the overage.
2. **`AINOS3-87`** (E 3) — self-contained; loses nothing else if deferred, though it is the only committed item that can ship a detector.
3. **`AINOS3-99`** `fold-variance-triage` (E 1) — only if Sprint 29's collection is itself slipping.

`AINOS3-95`, `AINOS3-96` and `AINOS3-97` do not de-scope. The first two are the sprint's premise, and the third is the estate Sprint 29 collects into.

---

## Kickoff checklist

- [x] `pip install stix2 openpyxl` into `~/.virtualenvs/nos3` — done 2026-08-23
      (`stix2` 3.0.2, `openpyxl` 3.1.5). Both day-1 blockers cleared.
- [x] **Clear the violet `UPDATED` markers** in `app/gen_nos3_coverage.py` — done 2026-08-23:
      `UPDATED_SPRINT` → `"Sprint 28"`, `UPDATED` emptied. Sprint 27's markers had served
      their readout (`AINOS3-76`, delivered 2026-08-23). ⚠ **The rebuild is two commands, not
      one** — `gen_nos3_coverage.py` only writes `app/nos3_coverage.js`; the standalone
      `sparta_coverage.html` carries its own **inlined copy** and stays stale until
      `build_overlay.py` re-inlines it. Both run; verified 0 `"Sprint 27"` and 0 non-null
      `"updated"` strings left in the HTML, `updated_techniques: []`, 68 techniques.
- [x] **Tickets created and keys entered** (`AINOS3-98`–`AINOS3-101`, 2026-08-23).
- [x] Remaining Jira actions (board-side, not doable from the repo): close `AINOS3-45`;
      reparent `AINOS3-97` to `AINOS3-98`; re-prioritise `AINOS3-95` / `AINOS3-96` to High.
- [ ] Fresh stack before the first soak: `make start-gsw` **before** `make launch-quiet` when
      the stack is fully down, or the launch no-ops the GSW link.

---

## Suggested execution order

1. ~~**Day 1 — unblock, then the two desk items.**~~ ✅ **done 2026-08-23.** Both installs
   in; `AINOS3-90` answered (**not filtered** — 55.8 visible false incidents/hr, and the
   one-predicate mitigation would cost 48.4 % of attack frames) and `AINOS3-92` fixed (rate
   now derived from `CFE_TIME.SecondsMET`; the old 4.2 Hz overstated every uptime bin by
   32 %). `AINOS3-86`'s urgency is confirmed High and its reading tool is correct before the
   first soak.
2. **Day 1, in the background — start `AINOS3-86`'s first INERTIAL soak.** The stack is
   otherwise idle all sprint; soaks are calendar, not attention. Get the ≥ 2 h baseline
   running before the desk work starts.
3. **Days 2–4 — `AINOS3-96` (STIX).** First because it gates the label set, and because its
   script-vs-technique verdicts feed both `AINOS3-99` and Sprint 29's collection.
4. **Days 4–6 — `AINOS3-95` (logging workbook).** ~330 rows; the work is the cross-reference
   against our 382-column schema. Pull the `EPS` sheet forward — `AINOS3-87` wants it.
5. **Days 6–8 — `AINOS3-87`**, now armed with the EPS sheet. Ship a rule, or reclassify with
   an authoritative citation for what would be needed.
6. **Days 7–10 — `AINOS3-86` analysis** as the soaks complete. Distinguish the three causes;
   apply the fix only if it is cause (2) or (3).
7. **Days 10–12 — `AINOS3-97`** dependency map and quarantine, then **`AINOS3-99`** against it
   (it needs the map to know which collection each instance came from).
8. **If headroom, in this order:** `AINOS3-94` stages 1–2 (pairs with `AINOS3-96`'s
   STIX-as-build-source decision), `AINOS3-93`, `AINOS3-91` (cheapest while a soak stack is
   already up).
