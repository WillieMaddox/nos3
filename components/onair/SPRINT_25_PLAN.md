# Sprint 25 — "Consolidate & Add Signal" 📡

**Component:** `OnAIR-Security` · **Duration:** 2 weeks
**Capacity:** ~16 E-pts / ~7–8 T-pts (solo, realistic focus factor)
**Created:** 2026-07-15 · **Context:** Sprint 24 closed the **trust** and
**explainability** epics — the classifier is honestly measured (out-of-fold),
its PASSIVE weakness is a documented information limit (not a modeling one), the
mode-switch warmup is tuned + deployed, and every incident now carries a
human-readable "why." The `next-ml-bet` spike (`NOS3_330_NEXT_ML_BET.md`)
returned a clear verdict: **Phase 5 NO-GO, Phase 6 DEFER, CONSOLIDATE GO** — the
binding constraint is **observability (signal), not model capacity**. Sprint 25
executes that verdict.

**Sprint goal:** Add the *signal* the evidence keeps pointing at — recover the
nominal-ambiguous DEAD classes by subscribing the pruned MIDs, make the dominant
attribution field (`AppData`) actionable at the subsystem level, audit whether
the classifier leans on genuine signal or an activity-level shortcut, and bank
the dynamic-mode classification gains without regressing the weak modes.

## Points — two metrics

Each item carries two independent estimates:
- **E — effort points** (Fibonacci 1·2·3·5·8): relative effort × **uncertainty**
  × coordination. Sized for risk; comparative, not time.
- **T — time points** (**8 h = 1 point = 1 ideal engineering day**): estimated
  hands-on-keyboard hours ÷ 8. Pure duration; excludes the risk premium and
  excludes unattended wall-clock (soak / corpus-collection runs), which is noted
  separately.

Read the gap: **T < E** ⇒ the item is sized up for *risk*, not length (e.g. a
retrain that might not move the classes); **T ≈ E** ⇒ it's just big-but-known.

---

## Index

**IDs are slugs; Jira keys are the real ticket keys.** The durable slug ↔
Jira-key mapping is maintained in **[`JIRA_CROSSWALK.md`](JIRA_CROSSWALK.md)**
(cross-sprint, append-only) — that file is where you *enter* keys. The `Jira`
column below is a read-only mirror (keys are immutable, so it can't drift). All
Sprint-25 tickets now have keys (`appdata-slot-map → AINOS3-48` and
`rollout-s25 → AINOS3-49` were created 2026-07-15). Recurring work keeps a stable
epic slug and tags each instance with the Jira sprint number (`rollout-s25`,
prior `rollout-s24`).

| Slug | Jira | Type | Pri | E | T | Summary |
|---|---|---|---|--:|--:|---|
| coverage-expansion | AINOS3-41 | Epic | — | — | — | Detection coverage expansion (add signal) |
| extra-mids | AINOS3-30 | Story | Highest | 8 | 2.5 | ◑ COMMIT — subscribe pruned MIDs to recover nominal-ambiguous DEAD classes |
| explainability | AINOS3-32 | Epic | — | — | — | Explainability (Phase 7) |
| appdata-slot-map | AINOS3-48 | Task | High | 3 | 0.75 | ◑ COMMIT — EVS `AppData` slot→app crosswalk; unblocks the counter-reliance audit |
| classification-trust | AINOS3-31 | Epic | — | — | — | Classification trust (close the mode gap) |
| counter-reliance-audit | AINOS3-39 | Spike | Medium | 3 | 0.75 | ◑ COMMIT — audit classifier reliance on generic activity counters |
| selective-mode-hybrid | AINOS3-37 | Story | Medium | 5 | 1.5 | ○ STRETCH — bank INERTIAL/SUNSAFE/ROBUST gains, no BDOT/PASSIVE regression |
| stakeholder-rollout | AINOS3-42 | Epic | — | — | — | Stakeholder rollout & feedback (recurring) |
| rollout-s25 | AINOS3-49 | Task | Medium | 2 | 0.5 | ◑ COMMIT — Sprint-25 readout: DEAD-class recovery + audit findings |

**Totals (all tickets):** E = 21 · T = 6.0 (≈ 48 ideal hours).

---

## 🟪 EPIC AINOS3-41 — Detection coverage expansion (add signal)

**Summary:** Broaden what the detector can *see* and classify — add signal, not
model capacity.
**Description:** The `next-ml-bet` spike found the binding constraint is
observability, not architecture, so this epic invests in coverage — *adding
signal*, not changing the model. `AINOS3-30` is the first and highest-value
lever: restore the MIDs that csv-format-v2 pruned so the nominal-ambiguous DEAD
classes can separate. It is the headliner of Sprint 25.

### AINOS3-30 — Recover nominal-ambiguous DEAD classes · `Story` · Highest · E 8 · T 2.5 (~20h) · ◑ COMMIT
**Summary:** As an analyst, I want `DE-0003.03/.08/.09` and `EX-0014.03` to be
detectable/classifiable — subscribe the MIDs that currently make them
indistinguishable from nominal.
**Description:** Carried from the Sprint 23 → 24 backlog and now promoted to the
sprint headliner per the `next-ml-bet` verdict. These techniques' frames are
indistinguishable from nominal because their discriminating MIDs
(`CFE_TBL.LastFileLoaded` / `CFE_TBL.LastUpdatedTable`, and the CryptoLib SA
state) were pruned by csv-format-v2's Tier-1 column reduction (273→250 cols).
Add them back to `nos3_security_tlm.json` (+ `message_headers.py` structs and
the MID→channel map if the types aren't already defined), re-collect a fresh
mode-balanced corpus slice, retrain, and **measure whether the four classes
separate** above the DEAD floor.
**Acceptance criteria:**
- Targeted MIDs added to the telemetry schema (source + runtime build tree in
  sync); schema-fingerprint / `.meta.json` sidecar updated so the new columns are
  recorded and drift-detected.
- A fresh corpus slice collected covering the four techniques across ADCS modes.
- Per-class F1 / incident recall reported for `DE-0003.03/.08/.09` + `EX-0014.03`.
- **Deploy gate:** if a class clears the DEAD floor, retrain + redeploy the v3
  classifier (ini pointer + build-tree sync); if it stays dead even with the new
  MIDs, document *why* (the signal genuinely isn't in those MIDs) and leave the
  class flagged as DEAD.
**Estimate note:** ~5h of corpus-collection wall-clock excluded from T; E carries
the real risk that the classes stay dead even with the new MIDs (in which case
the deliverable is the negative finding + the ruled-out MIDs, not a deploy).
**Dependency for downstream bets:** this is also the gate `NOS3_330` set on
re-opening Phase 5 (DeepSAD) — a broader signal + larger corpus is what changes
that data-sufficiency picture.

**Investigation (2026-07-15) — the story splits three ways, not one:**
The "subscribe extra MIDs" framing only partly holds once verified against the
live schema:
- **DE-0003.03/.08/.09 (table-load) — NOT an unsubscribed-MID problem.** `CFE_TBL`
  (0x0804) is already subscribed and `LastFileLoaded` / `LastUpdatedTable` /
  `LastTableLoaded` are still in `nos3_security_tlm.json` — only suppressed by
  `ExcludeColumns`. But they're `c_char[]` **string** fields (decode to text at
  `sbn_adapter.py`), which the IF/XGB can't use and which re-introduce the
  text↔numeric drift that got them cut. Fix = **un-suppress via numeric
  encoding**, not un-exclude-raw.
- **EX-0014.03 (CryptoLib SA state) — no MID exists; DOCUMENTED NEGATIVE.**
  CryptoLib is a `CFE_LIB` (loaded in `cfe_es_startup.scr`), not a cFS app: it
  publishes **zero** Software Bus telemetry. `SecurityAssociation_t`
  (spi, sa_state, ekid/akid, arsn, est/ast) lives only in process memory — there
  is nothing to subscribe. Worse, the recommended proxy signals
  (`RADIO_HK.ForwardErrorCount`/`ForwardCount`/`DeviceErrorCount`, the full
  `CFE_SB.*` error-counter family) are **already in the feature set**. So
  EX-0014.03 being DEAD is *not* a missing-signal problem and has **no MID
  lever**; recovering it (if possible) is a proxy-feature/model question, not a
  subscription one. Getting true SA observability would require adding a new HK
  packet inside CryptoLib — out of sprint scope.

**Progress (2026-07-15) — DE-0003 encoding DONE at code level (change-detection,
approved approach):**
- `sbn_adapter.py`: `_DERIVED_TBL_FIELDS` + pure `_tbl_change_detect()` +
  `_update_tbl_derived()`. Emits **6 numeric derived columns** — per field a
  `…Changed` (0/1, name differs from previous frame = a load/update event) and a
  monotonic `…Count`. First observation (boot load) is intentionally not an
  event. Raw strings **stay** in `ExcludeColumns` (read for the delta, never
  written).
- `nos3_security_tlm.json`: 6 entries added under `subsystems` + appended to the
  `order` tail; parser-verified alignment (`data_labels` 279 == `order` 279, the
  6 derived at the tail matching the sbn_adapter append order). CSV now carries
  256 columns (was 250).
- Tests: 7 new (`test_sbn_adapter.py`), full suite **24 passed**; csv_output
  **14 passed**. Synced to `fsw/build/exe/cpu1/cf/onair/` (build tree in sync).
- **Remaining (gated):** one stack launch + ~5h corpus collection under the new
  schema → retrain → per-class F1 vs DEAD floor → deploy if it clears. Held for
  an explicit go (do it once, with the final schema).

**VERDICT (2026-07-15) — NULL result, premise disproven. DO NOT DEPLOY.**
Collected a fresh mode-balanced corpus (32/32 attacks, new 256-col schema,
`data/onair/csv_ainos3_30/`) and ran a classifier feature-ablation
(`ablation_ainos3_30.py`, `data/onair/models/ablation_ainos3_30.json`):
- The 6 derived columns are **constant 0 across the entire 63,261-row corpus** —
  every attack window and all nominal frames. Ablation delta = **exactly +0.000**
  for all four targets and overall (acc 0.718, macro-F1 0.5525, identical arms).
- **Root cause (positive control) — static-after-boot, not universally empty:**
  `CFE_TBL.LastUpdatedTable` **is** populated (`b'..SBN.SBN_ConfTbl'`, set at boot),
  so the name fields *can* carry table names — they just don't *change* mid-session
  during nominal ops or any of the 32 attacks, so the change-detection reads
  constant 0. `LastFileLoaded`/`LastTableLoaded` are empty; a successful ground
  `CFE_TBL_LOAD` (CommandCounter 1→2, no error) did **not** populate `LastFileLoaded`
  — cFE updates it on table *activation*, not a load-to-inactive-buffer. The feature
  is correctly wired (unit tests pass; deployed sbn_adapter appends+reads the fields)
  and would fire on a genuine table load+activate; these attacks never do that. Not
  a modeling limit — absent *change* events.
- **Premise disproven:** DE-0003.03/.08/.09 + EX-0014.03 are **not** table-load
  attacks and don't touch CFE_TBL table state; the "pruned CFE_TBL discriminators"
  hypothesis is false. Their DEAD status is nominal/sibling ambiguity (an
  information limit — same shape as AINOS3-33 PASSIVE), not a subscription/feature
  gap. AINOS3-30's MID-lever thesis does not apply to these four classes.
- **Decision (user): KEEP DORMANT — do not revert, do not deploy.** The fields can
  populate, so a future SPARTA technique that loads+activates/updates an on-board
  table will change them and the feature fires (unit-tested); many techniques are
  still unexplored, so the instrumented columns are retained until we know none
  trigger table activity. The 6 columns are harmless (constant 0 ⇒ HistGB ignores
  them; ablation +0.000). NOT deployed into the classifier (zero signal now).
  Follow-up: when validating new techniques, watch whether any move
  `LastUpdatedTable`/`LastFileLoaded`/`LastTableLoaded` or the numeric
  `LastUpdateTimeSeconds`/`ValidationCounter`/`SuccessValCounter` (which move on any
  table activity) — that's the trigger for a real table-activity feature. Real
  DEAD-class recovery still needs a different signal source (NOS3-321 thread). Code
  remains uncommitted (kept in tree, dormant).

---

## 🟪 EPIC AINOS3-32 — Explainability (Phase 7)

**Summary:** Attach a human-readable, *actionable* reason to every incident.
**Description:** Sprint 24 shipped per-incident SHAP attribution (AINOS3-38) and
surfaced it in the incident record + demo (AINOS3-40). The remaining gap is that
the field that dominates almost every attribution — `CFE_EVS_HK.AppData` — is an
anonymous 16×4 array, so "AppData drove it" isn't yet actionable. This task
resolves the slots to app names, which is the missing piece that makes the
attribution useful *and* unblocks the counter-reliance audit.

### AINOS3-48 — EVS AppData slot→app reference map · `Task` · High · E 3 · T 0.75 (~6h) · ◑ COMMIT
**Summary:** As a developer/analyst, I want a reference map from each
`CFE_EVS_HK.AppData` slot to the human-readable app it represents, so the
top-field that dominates most attack attributions becomes actionable at the
subsystem level instead of an anonymous array.
**Description:** `CFE_EVS_HK.AppData` is an array of 16 `CFE_EVS_AppTlmData_t`
records (`message_headers.py:756`); each record's field 0 is an **opaque cFE
resource `AppID`** (`CFE_ES_APPID_BASE 0x110000 + N`, e.g. observed
`1114113 = 0x110001`), not a name. The array only holds the first 16
EVS-registered apps (the build has >16). SHAP attribution (AINOS3-38) shows
`AppData` in the top-6 for nearly every attack, but we currently cannot say
*which* app drives it — a diagnostic dead-end.
**Why this is dual-use (primary beneficiary is the engineering loop, not the
stakeholder readout):**
- **Unblocks AINOS3-39** (counter-reliance audit): lets us ask the sharp
  question — is the `AppData` signal the *attacked* subsystem's event stream
  (genuine) or a generic busy app like SCH (a shortcut)?
- **Enables targeted features:** the struct docstring (`message_headers.py:769`)
  flags `AppEnableStatus = 0` as the *event-suppression* attack signal (an
  attacker silencing a subsystem to hide activity). A named map lets us build an
  explicit `AppData[<app>].AppEnableStatus` feature instead of leaving it buried
  in a 64-wide array for the model to discover.
- **Sharpens footprint assertions:** attack-validation / soaks can assert "attack
  Y suppresses app Z ⇒ `AppData[Z].AppEnableStatus`→0 and
  `AppMessageSquelchedCounter` climbs" rather than "AppData changed somewhere."
**Approach — static crosswalk (build-static, no runtime change):** the
`AppID→name` binding is deterministic for a fixed cFS image (same
`cfe_es_startup.scr` + cFE core apps every launch), so it does **not** need
per-run telemetry. Take one live `CFE_ES` App Info dump to pin the
`0x110000+N → name` offset against the startup-script names, commit a JSON
crosswalk artifact, and resolve by the **`AppID` value in field 0** (not slot
position, so EVS registration-order variation can't misname). Explicitly **not**
subscribing the ES App Info MID at runtime — that solves a per-run-dynamic
problem we don't have and adds permanent flight-runtime surface.
**Acceptance criteria:**
- Committed `AppID→name` crosswalk JSON covering the 16 populated slots, pinned
  against one live ES App Info dump.
- Attribution / demo render `AppData` contributions by app name (e.g.
  `AppData[ADCS].AppEnableStatus`) where a specific slot dominates.
- **Diff-guard:** a script that re-dumps ES App Info and fails if the committed
  map no longer matches the running build (ties into the existing
  schema-fingerprint discipline), so an intentional rebuild that shifts app
  registration order is flagged rather than silently misnaming.
**Depends on:** AINOS3-38 (attribution, DONE). **Feeds:** AINOS3-39 (counter-reliance
audit); optionally the AINOS3-37 targeted-feature work.
**Escape hatch:** if a future need makes live app-registration state worthwhile
(frequent rebuilds, or an operator wants live ES state), the static table
upgrades to the ES App Info telemetry approach cheaply.
**Estimate note:** E 3 carries the offset-pinning uncertainty (mapping the opaque
IDs to names correctly the first time); T ~0.75 (~6h) is the table + render +
guard once the dump is in hand.

**Progress (2026-07-15) — crosswalk + diff-guard DONE + live-validated:**
- Dumped app info from the live FSW via `CFE_ES_QUERY_ALL` (MID 0x1806, FC 9, raw
  UDP:5012 — no COSMOS needed). Parsed the binary file (64-byte FS header + 184-byte
  `CFE_ES_AppInfo_t` records; `ResourceId` u32, `Type`, `Name[20]`).
- Committed **`components/onair/cfe_appid_crosswalk.json`** — all 33 resources
  (5 CORE + 25 EXTERNAL apps + 3 libraries). The 16 populated `AppData` slots =
  AppIDs 0x110001–0x110010 (CFE_EVS…SC). Registration order is **not** ES-first
  (EVS, SB, ES, TIME, TBL, then startup.scr apps) — exactly why a live pin was
  needed, not a guess.
- **Validated against live telemetry:** the 16 `CFE_EVS_HK.AppData[i].AppID`
  values in the current OnAIR CSV resolve exactly (1114113→CFE_EVS … 1114118→SCH).
- **Diff-guard** `appid_crosswalk.py --check` (re-dumps live, diffs the committed
  map, exits nonzero on mismatch) — **live-verified OK**. `--write` regenerates.
- Gotcha logged: OSAL `OS_MAX_FILE_NAME`=20 silently drops longer dump basenames.

**Rendering DONE + live-verified (2026-07-15):**
- Crosswalk emits a validated `appdata_slots[16]` array (`CFE_EVS`…`SC`).
- `attribution.py` resolves `CFE_EVS_HK.AppData[i_j]` → `AppData[<app>].<field>`
  (`load_appid_slot_map` + optional `appid_slot_map` through `base_field` /
  `aggregate_incident` / `explain_incident`; opaque-collapse fallback when the
  crosswalk is absent). 8 new tests + 2 doctests (24 pass).
- `build_explanation_catalog.py` wired; catalog regenerated → **18/25 classes
  now app-named**. Payoff for AINOS3-39: `EX-0008.01/.02` (SC-app ATS/RTS) surface
  `AppData[SC].AppMessageSentCounter` as #1 — the AppData mass there is *genuine
  SC activity*, not a generic shortcut. (Field-level granularity means a
  widely-distributed EVS signal can occupy several top-N slots — noted in the
  catalog meta.)
- Demo regenerated (`gen_nos3_coverage.py` → `nos3_coverage.js`,
  `build_overlay.py` → `app/sparta_coverage.html`; 24 app-named refs inlined).
- **Live-verified:** restarted OnAIR — the xgb plugin loaded the updated catalog
  (25 classes, `appdata_resolved=True`), read from `data/onair/models/` (mounted;
  no build-tree copy needed). Runtime now reports `AppData[<app>].<field>` in
  incident explanations.
**AINOS3-48 COMPLETE.** Unblocks AINOS3-39 (the AppID→name map + per-app
attribution are exactly its inputs).

---

## 🟪 EPIC AINOS3-31 — Classification trust (close the mode gap)

**Summary:** Make attack-type labels reliable across ADCS modes and honestly
measured.
**Description:** Sprint 24 established the honest baseline (out-of-fold
accuracy), proved PASSIVE labeling is an information limit, and kept the deployed
v3 classifier as-is. Two backlog items remain under this epic: an audit of *how*
v3 forms its verdicts (does it lean on genuine signal or an activity shortcut),
and the selective per-mode hybrid that banks the dynamic-mode upside AINOS3-33
uncovered. Both are sequenced after AINOS3-30 per `NOS3_330` ("306 → 305").

### AINOS3-39 — Audit classifier reliance on activity counters · `Spike` · Medium · E 3 · T 0.75 (~6h) · ◑ COMMIT
**Summary:** Determine whether v3's heavy reliance on generic high-traffic
counters is genuine discriminative signal or an activity-level shortcut.
**Description:** AINOS3-38 attribution showed v3 keys heavily on generic
high-traffic counters (`CFE_EVS_HK.AppData`, `CFE_ES.CommandCounter`,
`CFE_TBL.*`) across many attacks — they are high-IMPORTANCE but
low-DISCRIMINATION (they top many attacks; the attack-specific field ranks just
below). Audit whether these are genuine signal or a busy-app shortcut, and
whether regularizing / dropping them would improve per-attack discrimination
without hurting LOIO accuracy.
**Approach:** with AINOS3-48 in hand, resolve the `AppData` contribution
to specific apps and test the sharp question — is it the *attacked* subsystem's
event stream (genuine) or a generic busy app (shortcut)? Prototype a
drop/regularize experiment over the frozen `csv_corpus_v3stage` under LOIO and
compare per-attack cluster accuracy.
**Acceptance criteria:**
- The `AppData` / `CFE_ES.CommandCounter` contributions resolved to named apps
  (via AINOS3-48) and classified genuine-vs-shortcut per attack.
- Drop/regularize experiment run under LOIO; net effect on discrimination and
  overall accuracy reported.
- Recommendation: leave v3 as-is, or a scoped feature change for a *future*
  retrain (any model change interacts with AINOS3-33's "keep v3" decision, so
  this spike only *recommends*, it does not deploy).
**Prerequisite:** AINOS3-48 — the `AppData` half of this audit can't
distinguish genuine attacked-subsystem signal from a generic busy-app shortcut
until each of the 16 slots is resolved to an app name.
**Placement:** a model-behaviour concern, so it lives under EPIC AINOS3-31, not
Explainability — even though it's fed by an Explainability task.

### AINOS3-37 — Selective per-mode classifier hybrid · `Story` · Medium · E 5 · T 1.5 (~12h) · ○ STRETCH
**Summary:** Bank the INERTIAL/SUNSAFE/ROBUST gains from per-mode heads without
the BDOT/PASSIVE regressions, via mode-routed classification.
**Description:** AINOS3-33 showed full `per_mode` routing helps the two signal-rich
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
**Sequencing:** STRETCH — pull in only after AINOS3-39's audit clears (the audit
may change *which* features the per-mode heads should train on, so doing the
hybrid first risks a rework). If AINOS3-30 slips or the corpus re-collection eats
the sprint, AINOS3-37 rolls to Sprint 26 with no loss.
**Estimate note:** E carries integration risk (routing + multi-head calibration
in the live plugin). Independent of AINOS3-33's outcome.

---

## 🟪 EPIC AINOS3-42 — Stakeholder rollout & feedback (recurring)

**Summary:** Recurring stakeholder readout — show the coverage overlay + doc each
sprint (or every other) and turn feedback into backlog.
**Description:** A standing readout, not a one-off. Present the current
`app/sparta_coverage.html` detection-coverage overlay + `V5_DETECTOR_COVERAGE.md`,
walk stakeholders through "what it catches / what it doesn't," and log feedback as
backlog candidates. **Cadence:** once per sprint or every other sprint; each
occurrence is a fresh child slug tagged with the Jira sprint number
(`rollout-s25` follows `rollout-s24`).

### AINOS3-49 — Stakeholder rollout (Sprint 25) · `Task` · Medium · E 2 · T 0.5 (~4h) · ◑ COMMIT
**Summary:** Present the Sprint-25 result — DEAD-class recovery + the
counter-reliance audit findings — on top of the existing coverage overlay, and
capture feedback.
**Description:** Second instance of the recurring `AINOS3-42` readout. Refresh
`STAKEHOLDER_ROLLOUT.md` and regenerate the demo overlay
(`gen_nos3_coverage.py` → `nos3_coverage.js` → `app/sparta_coverage.html`) so it
reflects any classes AINOS3-30 recovered and any `AppData`-by-app explanation
improvements. Walk stakeholders through what changed since Sprint 24, and — per
the `NOS3_330` Phase-6 hold — explicitly ask whether operators want causal-chain
root-cause beyond the current top-fields explanations (that answer is the gate on
reopening the graph model).
**Acceptance criteria:**
- Demo overlay + coverage doc refreshed to Sprint-25 state.
- Doc + demo presented — **owner action** (cannot be automated).
- Feedback captured in the `STAKEHOLDER_ROLLOUT.md` table, then filed as backlog
  tickets — including an explicit read on the Phase-6 (causal chains) demand
  signal.
**Depends on:** AINOS3-30 + AINOS3-48 (so the readout shows new results,
not a repeat of Sprint 24).

---

## 📋 Backlog (carryover)

| Slug | Jira | Type | E | T | Summary |
|---|---|---|--:|--:|---|
| tcn-feature | AINOS3-44 | Story | 5 | 1.5 | TCN reconstruction-error as a feature, scoped to EX-0008 ATS/RTS |
| corpus-instance-4 | AINOS3-45 | Task | 3 | 0.75 | 4th corpus instance (LOIO variance already ±3.6%; ~5h wall-clock) |
| demo-tier-bc | AINOS3-46 | Story | 3 | 1.0 | Demo app Tier B/C (live execution / agent) |
| foundation-baseline | AINOS3-47 | Story | 8 | 2.5 | Optional: foundation-model (MOMENT/THEMIS) zero-shot baseline |
| deepsad-revisit | — | Spike | 3 | 0.75 | Reopen Phase 5 DeepSAD **only after** AINOS3-30 broadens signal (`NOS3_330` gate) |

---

## Capacity note

**Two readings of the same commitment:**
- **Effort:** committed E across AINOS3-30 / AINOS3-48 / AINOS3-39 /
  AINOS3-49 = **16** — right at the ~16/sprint capacity. Adding the AINOS3-37
  stretch pushes it to **21**.
- **Time:** the committed set = **~4.5 T** (≈ 36 ideal hours); with the AINOS3-37
  stretch, **~6.0 T** (≈ 48 h) — both inside the ~7–8 T realistic solo capacity
  for a 2-week sprint, with the collection/soak wall-clock (~5h for AINOS3-30's
  corpus slice) running unattended on top.

The T headroom is deliberate: AINOS3-30 is the highest-risk item (the classes may
stay dead), so the sprint commits the add-signal chain first and holds AINOS3-37
as a de-risked stretch that also *wants* the audit's findings before it starts.

## Suggested execution order

1. **AINOS3-30** (extra MIDs — the headliner; kick off corpus re-collection early
   so the ~5h wall-clock overlaps other work).
2. **AINOS3-48** (take the ES App Info dump; commit the crosswalk +
   diff-guard) — can run in parallel with AINOS3-30's collection.
3. **AINOS3-39** (counter-reliance audit — unblocked by step 2; grounds the
   AINOS3-37 feature decision).
4. **AINOS3-37** (selective hybrid — STRETCH; start only if steps 1–3 land with
   time to spare and the audit hasn't changed the feature set under it).
5. **AINOS3-49** (readout on the new results) near end of sprint.
