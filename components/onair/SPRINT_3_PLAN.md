# Sprint 3 — "Trustworthy & Explainable" 🔍

**Component:** `OnAIR-Security` · **Duration:** 2 weeks
**Capacity:** ~16 E-pts / ~7–8 T-pts (solo, realistic focus factor)
**Created:** 2026-06-10 · **Context:** Phases 1–3 are deployed; Phase 4 (TCN) is
closed as diminishing-returns; Sprint 2 shipped the incident layer + coverage
doc + demo overlay (all committed). The next gaps are **classification trust**
(labels collapse in PASSIVE, are noisy elsewhere, and are only validated
in-sample) and **explainability** (Phase 7), which is what makes alerts
actionable for operators.

**Sprint goal:** Make the classifier's verdicts trustworthy per-mode and
explainable, so an operator can act on an incident with both a reliable label
and a reason — and present the result to stakeholders.

## Points — two metrics

Each item carries two independent estimates:
- **E — effort points** (Fibonacci 1·2·3·5·8): relative effort × **uncertainty**
  × coordination. Sized for risk; comparative, not time.
- **T — time points** (**8 h = 1 point = 1 ideal engineering day**): estimated
  hands-on-keyboard hours ÷ 8. Pure duration; excludes the risk premium and
  excludes unattended wall-clock (soak / corpus-collection runs), which is noted
  separately.

Read the gap: **T < E** ⇒ the item is sized up for *risk*, not length (e.g. a
retrain that might not work); **T ≈ E** ⇒ it's just big-but-known.

---

## Index

| Key | Type | Pri | E | T | Summary |
|---|---|---|--:|--:|---|
| NOS3-300 | Epic | — | — | — | Classification trust (close the mode gap) |
| NOS3-301 | Story | Highest | 8 | 3.0 | ✅ CLOSED (negative result) — PASSIVE labeling is an info limit, not modeling; keep v3 |
| NOS3-302 | Task | High | 5 | 1.25 | ✅ DONE (2026-06-29) — out-of-fold incident-label accuracy = 34.6% |
| NOS3-303 | Task | Medium | 3 | 1.0 | ✅ DONE — 36-switch soak: transient settles ~36s ≪ 600f/124s; recommend 600→250 (deploy pending go) |
| NOS3-304 | Bug | High | 2 | 0.5 | ✅ RESOLVED — "FSW idle mode-lock" was a CSV-parsing artifact |
| NOS3-305 | Story | Medium | 5 | 1.5 | Backlog — selective per-mode hybrid (bank INERTIAL/SUNSAFE/ROBUST, no BDOT/PASSIVE regression) |
| NOS3-306 | Spike | Low | 3 | 0.75 | Backlog — audit classifier reliance on activity counters |
| NOS3-310 | Epic | — | — | — | Explainability (Phase 7 start) |
| NOS3-311 | Story | High | 8 | 2.25 | ✅ DONE — per-incident SHAP attribution (offline) + incident wiring |
| NOS3-312 | Story | Medium | 3 | 0.5 | ✅ DONE — surface explanations (catalog) in incident side-file + demo |
| NOS3-320 | Epic | — | — | — | Coverage gaps & stakeholder rollout |
| NOS3-321 | Story | Medium | 8 | 2.5 | Subscribe extra MIDs to recover nominal-ambiguous DEAD classes |
| NOS3-322 | Task | High | 2 | 0.5 | Present coverage doc + demo to stakeholders |
| NOS3-330 | Spike | Medium | 3 | 0.75 | Decide the next big-ML bet (Phase 5 VAE vs Phase 6 graph) |

**Totals (all tickets):** E = 41 · T = 12.0 (≈ 96 ideal hours).

---

## 🟪 EPIC NOS3-300 — Classification trust (close the mode gap)

**Summary:** Make attack-type labels reliable across ADCS modes and honestly
measured.
**Description:** Live verification showed the v3 classifier labels well in
INERTIAL/SUNSAFE but collapses to `nominal`/`EX-0012.09` in PASSIVE, and the
incident-label accuracy reported so far is in-sample. This epic raises label
trust and replaces the in-sample number with an honest one.

### NOS3-301 — Mode-aware classifier · `Story` · Highest · E 8 · T 3.0 (~24h) · ✅ CLOSED 2026-06-29 (documented negative result)
**Summary:** As an operator, I want the attack label to be reliable regardless
of which ADCS mode the spacecraft is in.
**Description:** The single v3 classifier is dominated by SUNSAFE/INERTIAL
training and mislabels in PASSIVE (live IMP-0005 → EX-0012.09). Investigated and
fixed via per-mode classifier heads or a mode feature with rebalanced per-mode
sampling; re-evaluated with LOIO over the frozen `csv_corpus_v3stage`.
**Resolution:** **Won't fix by modeling — closed as a negative result.** All
three ticket-named approaches leave PASSIVE flat or worse; PASSIVE attack-
labeling is an **information limit, not a modeling one** (the quiescent regime
carries little class signal). Frozen-corpus LOIO, cluster-acc on attack frames:

| variant | overall | BDOT | INERTIAL | PASSIVE | SUNSAFE | ROBUST |
|---|--:|--:|--:|--:|--:|--:|
| baseline (v3) | 0.627 | 0.419 | 0.341 | **0.148** | 0.396 | 0.685 |
| mode_feat | 0.625 | 0.397 | 0.325 | 0.146 | 0.388 | 0.685 |
| per_mode | 0.639 | 0.372 | 0.399 | 0.120 | 0.457 | 0.753 |
| mode_rebal | 0.624 | 0.412 | 0.336 | 0.150 | 0.397 | 0.681 |

`mode_rebal` (the targeted rebalanced-sampling lever) lands PASSIVE at 0.150 ≈
baseline 0.148 — provably flat. `per_mode` lifts INERTIAL/SUNSAFE/ROBUST/overall
but **regresses both signal-poor modes** (BDOT −0.047, PASSIVE −0.028), so it is
not deployed wholesale. **The deployed v3 classifier is kept as-is.**
**Acceptance criteria — outcome:**
- ✅ Per-mode LOIO label accuracy reported for all four modes (table above).
- ⛔ "PASSIVE improves vs v3" — **not met, and provably so** (criterion reframed:
  PASSIVE is an information limit). ROBUST tier not regressed (kept v3).
- ➡️ Deploy criterion intentionally **not** exercised — no model change shipped.
**Honest deliverable:** the per-mode LOIO table, the provable negative result,
operator guidance that **PASSIVE incident labels are low-confidence**, and a
redirect of the real PASSIVE fix to signal-adding work (NOS3-321 extra MIDs /
temporal features add *information*; they don't rearrange the model).
**Spun off:** the per_mode INERTIAL/SUNSAFE/ROBUST upside → **NOS3-305** (selective
hybrid), tracked separately because it's plugin work for a benefit that is *not*
what NOS3-301 was for.

### NOS3-302 — Out-of-fold incident-label accuracy · `Task` · High · E 5 · T 1.25 (~10h)
**Summary:** Measure incident-label accuracy out-of-fold, not in-sample.
**Description:** `eval_incident_rescore.py` currently labels incidents with the
in-sample v3. Extend it to drive incident aggregation from the LOIO out-of-fold
predictions (persist per-frame predictions with file/row/window/mode metadata
in `eval_classifier_clusters.py`), and report honest incident-level label
accuracy per mode and per cluster.
**Acceptance criteria:**
- Incident-label accuracy computed from out-of-fold predictions.
- Coverage doc updated to replace the in-sample caveat with the real number.
**Estimate note:** ~80 min of LOIO retrain wall-clock is excluded from T.

### NOS3-303 — Mode-switch warmup tuning / guidance · `Task` · Medium · E 3 · T 1.0 (~8h) · ✅ DONE 2026-07-05
**Summary:** Stop the 600-frame mode-switch warmup from blinding detection in
transient modes (or document the operational guidance).
**Description:** The IF re-arms a 600-frame (~124 s @ 4.83 fps) warmup on every
routing switch (`ModeSwitchWarmupFrames`, `isolation_forest_plugin.py`),
suppressing ALERT/CLEAR. An attack in a mode held < that window is never flagged.
NOS3-304 makes this MORE relevant (modes do switch reliably/often).
**Measured — confirmatory 36-switch nominal soak (2026-07-05,
`analyze_mode_switch_warmup.py`, 8731 frames, steady-state baseline 0.0%):**
the post-switch transient is **16-21% through ~26 s**, drops to 9.4% at ~31 s,
and **settles to ≤3% by ~frame 175 (~36 s)**, ~0% after. (An initial noisy
9-switch read gave ~26 s — the confirmatory soak revised the settle UP ~10 s;
the initial was optimistic.) So the 600-frame/124 s warmup is **~3.5× longer
than the transient** — ~72 s of the blind window per switch is avoidable.
**Recommendation:** reduce `ModeSwitchWarmupFrames` 600 → **250** (~52 s, solid
margin over the ~36 s/175-frame settle), cutting the blind window by ~58 % and
restoring detection in briefly-held modes at ~0 FP cost. (200/~41 s is the
aggressive floor — tighter margin.)
**Operational limit (committed to `V5_DETECTOR_COVERAGE.md`):** with the current
600-frame setting, detection is reliable only in a mode held > ~124 s.
**Acceptance criteria — met:** FP-vs-warmup tradeoff measured (36-switch decay
curve); operational limit documented + a recommended setting given.
**GATE satisfied:** the confirmatory ≥30-switch nominal soak is done (36 clean
switches, 0.0% baseline — no uptime drift). Deploying 600→250 (edit
`nos3_security.ini` + sync runtime + restart OnAIR) is now justified; **left for
an explicit go** since it changes a live detection safety parameter.
**Estimate note:** soak wall-clock for the confirmatory measurement excluded.

### NOS3-304 — "FSW idle mode-lock" was a CSV-parsing artifact · `Bug` · High · E 2 · T 0.5 (~4h) · ✅ RESOLVED 2026-06-29
**Summary:** The long-held belief that a long-idle FSW silently rejects
BDOT/SUNSAFE mode commands (and stays pinned in PASSIVE) is not a real FSW
behaviour — it was a telemetry **measurement artifact** from naive CSV parsing.
**Type:** Bug · **Priority:** High · **Resolution:** Fixed (measurement
corrected; no FSW/flight-code change required).
**Description:** The 2026-05-16 observation — *14,145 OnAIR rows all
`MODE_PASSIVE` despite 38× BDOT + 38× SUNSAFE `SET_MODE` commands* — was used
to justify the fresh-launch ritual (`make stop` + `make launch-quiet` before
BDOT/PASSIVE collection) and the 30-s re-command cadence in
`run_attack.py` / `run_baseline.py`. Root cause: the OnAIR CSV contains quoted
array columns with embedded commas (250 fields/row). Parsing it with
`awk -F','` / `cut -d,` / naive `str.split(',')` shifts every field index past
the first array column, collapsing `ADCS_GNC.Mode` to a wrong-but-constant
column that reads `0` for every row. A correct parser (`csv.DictReader`,
addressing columns by header name) shows the mode changing normally.
**Evidence / how it was found (2026-06-29):**
- Code review: the ADCS `SET_MODE_CC` handler
  (`components/generic_adcs/fsw/cfs/src/generic_adcs_app.c` ~L440) writes
  `cmd->Mode` **unconditionally** — there is no mode-transition guard, rate
  gate, or fault-clearance check that could "reject" an upward transition.
  Only the control *laws* are sensor-gated (`generic_adcs_adac.c`: BDOT needs
  `MAGV(bvb) > b_range`, SUNSAFE needs `SunValid`).
- Live test on a fresh stack: sent SET_MODE BDOT→SUNSAFE→INERTIAL→PASSIVE; the
  live OnAIR `ADCS_GNC.Mode` (read via `csv.DictReader`) cycled `1→2→3→0`
  exactly as commanded, `ADCS_HK.CommandErrorCount` stayed `0`, `CommandCount`
  incremented. An `awk -F','` read of the *same* file falsely reported 100%
  `mode=0`, reproducing the original artifact.
**Blast radius — NONE on models/corpus:** the training/eval pipeline reads
telemetry via `pd.read_csv` (`loader.py:140`) and additionally rejects
row-misaligned files via `_file_is_clean()` (`loader.py:66`). The IF models,
XGBoost classifiers, mode-balanced corpus, and all per-mode accuracy findings
(NOS3-301/302) are unaffected — they were always parsed correctly. The artifact
only ever affected ad-hoc shell one-liners and the operational mode-lock belief.
**Resolution / actions:**
- Memory corrected (`project_fsw_autonomy_mode_lock.md`): the "Why" and
  workaround now flag the artifact; added the rule *always parse the OnAIR CSV
  with `csv.DictReader` by header name*.
- Auto-runnable confirmation script committed:
  `components/onair/training/scenarios/idle_mode_lock_retest.py` (parses
  correctly; PASS/FAIL verdict). Run it after a multi-hour idle to retire the
  fresh-launch ritual with full confidence.
**Acceptance criteria (met):**
- Root cause identified and demonstrated (fresh-stack live test + artifact
  reproduction). ✅
- Confirmed the ML pipeline is unaffected (pandas + alignment guard). ✅
- Corrected memory + committed a re-test harness. ✅
**Confirmation run (2026-06-30):** ran `idle_mode_lock_retest.py` after ~4.7 h
of stack idle → **PASS** (4/4 commanded modes reached, CmdErrCount=0). No idle
lock at multi-hour idle; the artifact conclusion holds. The fresh-launch ritual
is unnecessary at this scale and can be dropped from `run_attack` /
`run_baseline` mode-baseline collection. (Only the exact ~11 h condition of the
original 2026-05-16 observation remains formally un-reproduced, but the handler
has no time-based gate, so 11 h is expected to behave identically.)

### NOS3-305 — Selective per-mode classifier hybrid · `Story` · Medium · E 5 · T 1.5 (~12h) · `Backlog`
**Summary:** Bank the INERTIAL/SUNSAFE/ROBUST gains from per-mode heads without
the BDOT/PASSIVE regressions, via mode-routed classification.
**Description:** NOS3-301 showed full `per_mode` routing helps the two signal-rich
dynamic **modes** (INERTIAL +0.058, SUNSAFE +0.061, overall +0.012) and the
cross-mode ROBUST **tier** (+0.068) but regresses the signal-poor modes
(BDOT −0.047, PASSIVE −0.028). A **selective hybrid** — route INERTIAL/SUNSAFE
frames to per-mode heads, keep the global v3 head for PASSIVE/BDOT — should
capture the dynamic-mode upside while leaving the weak modes on the model that
serves them best. Requires classifier mode-routing in the plugin + per-mode
probability calibration so confidences stay comparable across heads.
**NOTE — ROBUST is a tier, not a routed mode:** the ROBUST tier is a set of four
attack clusters that span *all* ADCS modes, so its accuracy is a downstream
*consequence* of routing, not a routing target. The full +0.068 came from
routing every mode; under selective (INERTIAL/SUNSAFE-only) routing, only the
portion of ROBUST-tier frames that fall in INERTIAL/SUNSAFE benefits — the
realized ROBUST-tier gain is **to be measured**, not assumed.
**Acceptance criteria:**
- LOIO shows the INERTIAL/SUNSAFE mode gains retained and **no** BDOT/PASSIVE
  regression vs deployed v3.
- ROBUST-tier accuracy **measured** under the hybrid and shown not to regress vs
  v3 (any gain is upside, not a requirement).
- Per-mode calibration validated (confidences comparable across heads).
- Model + routing + calibration deployed; ini updated; build tree synced.
**Estimate note:** E carries integration risk (routing + multi-head calibration
in the live plugin). Independent of NOS3-301's outcome; pull in only after the
explainability epic (NOS3-310) if capacity is tight.

### NOS3-306 — Audit classifier reliance on activity counters · `Spike` · Low · E 3 · T 0.75 · `Backlog`
**Summary:** NOS3-311 attribution showed v3 keys heavily on generic high-traffic
counters (`CFE_EVS_HK.AppData`, `CFE_ES.CommandCounter`, `CFE_TBL.*`) across many
attacks. Audit whether these are genuine discriminative signal or an
activity-level shortcut, and whether regularizing/dropping them would improve
per-attack discrimination without hurting LOIO accuracy. Deferred — informational,
not blocking; any model change interacts with NOS3-301's "keep v3" decision.
**Placement:** spun off from the NOS3-311 finding but it's a classification-trust
concern (model behaviour), so it lives under EPIC NOS3-300, not Explainability.

---

## 🟪 EPIC NOS3-310 — Explainability (Phase 7 start)

**Summary:** Attach a human-readable reason to every incident.
**Description:** Master-plan Phase 7 calls for SHAP explainability as part of the
production-grade system. A label without a reason is hard to action; this epic
gives each incident its top contributing telemetry fields.

### NOS3-311 — Per-incident feature attribution · `Story` · High · E 8 · T 2.25 (~18h) · ✅ DONE 2026-07-04
**Summary:** As an analyst, I want each incident to show which telemetry fields
drove the detection/classification.
**Description:** Compute SHAP (or TreeExplainer) attributions on the classifier
for flagged frames; aggregate across an incident to a stable top-N field list
(e.g. "EPS.CommandCount, THRUSTER.*"). Keep it cheap enough to run only on
IF-gated frames.
**Acceptance criteria:**
- Each incident carries a ranked top-N contributing fields.
- Attributions validated against ≥3 known attacks (the fields match the
  attack's actual footprint from the SPARTA validation).
**Estimate note:** E carries risk that aggregated attributions are unstable
across an incident and need a second approach.
**Progress (2026-06-30) — offline core done + validated:**
- Explainer fork resolved: `shap.TreeExplainer` supports the v3
  `HistGradientBoostingClassifier` (shap 0.49.1; output `(frames, 894, 26)`),
  path-dependent so cheap. shap added to the `~/.virtualenvs/nos3` dev env only,
  NOT the OnAIR flight runtime.
- `attribution.py` — TreeExplainer wrapper + per-frame target-class SHAP
  (handles 3-D multiclass and 2-D binary) + `aggregate_incident()` ranking
  operator-readable telemetry fields (collapses `d_` deltas + `[i_j]` array
  elements; flags delta-dominant). `test_attribution.py` = 10 passing tests.
- `validate_attribution.py` — real-corpus footprints. 3/4 ROBUST-tier attacks
  match their catalog target cleanly: EX-0008.02→SC.CmdCtr (RTS),
  IMP-0005→THRUSTER.CommandCount (destruction), DE-0003.10→NOVATEL_HK.CommandCount
  (gps_ephemeris). DE-0003.01 partial. **Acceptance criterion 2 (≥3 attacks) met.**
**Update 2 (2026-06-30) — width-bias hypothesis REFUTED + incident wiring done:**
- Added configurable aggregation (`agg=max|mean|sum`, default `max`) to
  `aggregate_incident` + a regression test proving it fixes a *genuine* wide-array
  bias. BUT on the real corpus `max ≈ sum` (EX-0008.02 AppData 89.9% vs 89.4%;
  IMP-0005 CFE_ES.CommandCounter 72.5% vs 72.0%). So `CFE_EVS_HK.AppData` /
  `CFE_ES.CommandCounter` dominance is NOT a summing artifact — the model
  genuinely leans on generic high-traffic counters. They are high-IMPORTANCE but
  low-DISCRIMINATION (they top many attacks); the attack-specific field
  (SC.CmdCtr / THRUSTER.CommandCount / NOVATEL_HK.CommandCount) ranks just below.
- `incident_attribution.py` + 4 tests: `enrich_incident_record()` attaches
  `top_features` + `top_features_str` to a real `IncidentAggregator` Incident,
  OFFLINE (no submodule/runtime change). **Criterion 1 met** (incidents carry
  ranked top-N fields).
**Discrimination decision (2026-07-04) — RESOLVED as accept:** prototyped
contrastive (specificity) ranking = per-attack |SHAP| profile minus the
cross-attack mean. It did NOT demote the generic counters (EX-0008.02 AppData
and IMP-0005 CFE_ES.CommandCounter stayed #1); it only reshuffled ranks 3–6 (a
genuine win for DE-0003.10, which surfaced the spoofed NOVATEL ephemeris values).
All three methods (sum/max/contrastive) agree the generic counters dominate →
this is the MODEL's real behavior, not an attribution artifact. Reweighting to
hide it would be misleading. So: **keep the faithful ranking; close NOS3-311.**
The attack-specific field is present in the top-6 in every validated case.
**Both acceptance criteria met** (per-mode/attack top-N carried by incidents +
validated ≥3 attacks). Prototype discarded.
**Spun off:** a model-level observation → NOS3-306 (the classifier keys on
activity-level counters; audit whether that's genuine signal or a shortcut —
NOT a v3 change, since NOS3-301 kept v3).

### NOS3-312 — Surface explanations · `Story` · Medium · E 3 · T 0.5 (~5h) · ✅ DONE 2026-07-04
**Summary:** Show the per-incident explanation in the incident record and the
demo app.
**Description:** Add the top-N fields to `incident_*.csv` / the plugin reasoning,
and render them in the demo app's coverage panel.
**Design:** live runtime has no shap → a precomputed per-class **explanation
catalog** (`data/onair/models/explanation_catalog.json`, built offline by
`build_explanation_catalog.py`) is loaded by the plugin and the demo generator.
**Delivered:**
- `build_explanation_catalog.py` → 25-class catalog (class → top-N telemetry
  fields via offline SHAP; faithful ranking per NOS3-311).
- Plugin (`xgb_classifier_plugin.py`, submodule): loads the catalog (sibling of
  the classifier pickle, so it resolves at runtime with no ini change),
  `_explanation_for()` looks it up by winning sub-technique→cluster, and
  `_handle_incident` appends an `explanation` column to the incident side-file +
  console line. Missing catalog ⇒ column omitted (backward compatible).
- Demo: `gen_nos3_coverage.py` reads the catalog and adds `explanation` per
  technique; `nos3_overlay.js` renders a "Top fields (why)" column;
  `nos3_coverage.js` regenerated.
**Acceptance criteria — met + LIVE-VERIFIED 2026-07-04:** restarted OnAIR (loaded
`explanation_catalog.json (25 classes)`), ran DE-0003.10 live; a SUNSAFE incident
classified EX-0012.12/EX-0014.01 wrote the `explanation` column to the side-file:
`CFE_EVS_HK.AppData:45%|CFE_SB.MsgSendErrorCounter:14%|SCH.SameSlotCount:13%|…`.
Nominal incidents correctly carry an empty explanation. Demo column verified in
the regenerated `nos3_coverage.js`. (Runtime plugin synced to the build tree;
the diff vs source was exactly this change.)
**Depends on:** NOS3-311.

---

## 🟪 EPIC NOS3-320 — Coverage gaps & stakeholder rollout

### NOS3-321 — Recover nominal-ambiguous DEAD classes · `Story` · Medium · E 8 · T 2.5 (~20h)
**Summary:** Subscribe extra MIDs so `DE-0003.03/.08/.09`, `EX-0014.03` become
detectable/classifiable.
**Description:** Promoted from the Sprint-2 backlog (was NOS3-220). These
techniques' frames are indistinguishable from nominal because the discriminating
MIDs (`CFE_TBL.LastFileLoaded`/`LastUpdatedTable`, CryptoLib SA state) were
pruned by csv-format-v2. Add them to `nos3_security_tlm.json`, re-collect +
retrain, and measure whether the classes separate.
**Acceptance criteria:**
- Targeted MIDs added; a fresh corpus slice collected; per-class F1 / incident
  recall reported for the four classes; deploy if they clear the DEAD floor.
**Estimate note:** ~5h of corpus-collection wall-clock excluded from T; E
carries risk the classes stay dead even with the new MIDs.

### NOS3-322 — Stakeholder rollout · `Task` · High · E 2 · T 0.5 (~3h)
**Summary:** Present `V5_DETECTOR_COVERAGE.md` + the demo overlay to stakeholders
and capture feedback.
**Description:** The coverage doc and demo overlay exist but haven't been shown.
Walk stakeholders through "what it catches / what it doesn't," demo the live
matrix overlay, and log the feedback as backlog candidates.
**Acceptance criteria:**
- Doc + demo presented; feedback captured as tickets.

---

## 🔬 Spike

### NOS3-330 — Next big-ML bet · `Spike` · Medium · E 3 · T 0.75 (~6h)
**Summary:** Decide whether Phase 5 (VAE/DeepSAD) or Phase 6 (graph root-cause)
is the next investment, or whether to consolidate.
**Description:** Phases 1–3 are deployed and Phase 4 is closed. Before committing
weeks to Phase 5 or 6, run a scoped feasibility read (data sufficiency, expected
lift over v5+v3, operational value) and recommend the next bet — or recommend
consolidating the current system instead.
**Acceptance criteria:**
- One-page recommendation with a go/no-go for Phase 5 vs 6 vs consolidate.

---

## 📋 Backlog (carryover)

| Key | Type | E | T | Summary |
|---|---|--:|--:|---|
| NOS3-221 | Story | 5 | 1.5 | TCN reconstruction-error as a feature, scoped to EX-0008 ATS/RTS |
| NOS3-222 | Task | 3 | 0.75 | 4th corpus instance (LOIO variance already ±3.6%; ~5h wall-clock) |
| NOS3-223 | Story | 3 | 1.0 | Demo app Tier B/C (live execution / agent) |
| NOS3-350 | Story | 8 | 2.5 | Optional: foundation-model (MOMENT/THEMIS) zero-shot baseline |

---

## Capacity note

**Two readings of the same overcommit:**
- **Effort:** committed E across NOS3-301/302/303/311/312/322/330 = **32**
  vs ~16/sprint capacity.
- **Time:** the same set = **~9.25 T** (≈ 74 ideal hours) vs ~7–8 T realistic
  solo capacity for a 2-week sprint (10 working days × ~0.7 focus factor).

Both say the full set doesn't fit. Recommended **commitment**: the two
highest-value epics — **NOS3-300 (E 16 / T 5.25)** + **NOS3-311+312 (E 11 /
T 2.75)** ≈ **T 8.0** — with NOS3-321 and the spike as stretch. If velocity is
tighter, commit NOS3-300 and pull explainability forward only after the mode
gap is closed.

## Suggested execution order

1. **NOS3-302** (honest out-of-fold numbers — grounds everything else).
2. **NOS3-301** (mode-aware classifier — the core trust fix).
3. **NOS3-311 → 312** (explainability on the improved model).
5. **NOS3-322** (rollout) + **NOS3-330** (next-bet spike) in parallel.
