# Sprint 27 — "Add Signal, Close the Loop" 📡

**Component:** `OnAIR-Security`

**Created:** 2026-08-09

**Duration:** 2 weeks

**Capacity:** ~16 E-pts / ~7–8 T-pts (solo, realistic focus factor)

**Context:** Sprint 26 closed the **classification-trust** epic (AINOS3-37 selective
per-mode hybrid deployed live + verified) and finished **Section-B coverage**
(DE-0001, DE-0006 detected; watchdog + EX-0001.02 out-of-scope; EX-0005.01
not-applicable) — the per-leaf SPARTA split is now **42 detected · 26 OOS · 0
not-evaluated · 109 N/A = 177**. Moving the coverage overlay to **honest hybrid
out-of-fold** numbers exposed the real ceiling: incident-label accuracy is **42.3 %**
(up +7.7 pts from the v3 global head's 34.6 % OOF, but far from the in-sample 76.9 %
fiction). Detection is solid (67.8 % recall, and 92.8 % on genuinely-detectable
state-change attacks); **labeling is the gap, and it is information-limited** — PASSIVE
and the DEAD/HIGH-VARIANCE clusters. `AINOS3-69` (next-ml-bet) has said it three sprints
running: the binding constraint is **observability, not model capacity**. So Sprint 27
turns the signal lever, hardens what we just shipped, and finally lands the stakeholder
readout that slipped last sprint.

**Sprint goal:** Test whether the recorded Section-B MIDs can lift the weak-class labels
(the signal lever), close the live-observed detector gaps, harden the deployed hybrid, and
land the carried-over stakeholder rollout.

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

**IDs are slugs; Jira keys are the real ticket keys.** The durable slug ↔ Jira-key
mapping is maintained in **[`JIRA_CROSSWALK.md`](JIRA_CROSSWALK.md)** (cross-sprint,
append-only). The `Jira` column below is a read-only mirror of that file — all Sprint-27
keys are now assigned (`AINOS3-77`–`AINOS3-85`). Carryover keys (`AINOS3-45`, `AINOS3-68`,
`AINOS3-76`) are immutable. ⚠ `AINOS3-30` was **wrongly reused** for this sprint's
signal-feasibility work, which is now split out as **`AINOS3-88`** (2026-08-19);
`AINOS3-30` itself remains **open** against its original scope.

| Jira | Slug | Type | Pri | E | T | Summary |
|---|---|---|---|--:|--:|---|
| AINOS3-41 | coverage-expansion | Epic | — | — | — | Detection coverage expansion (signal lever) |
| AINOS3-88 | signal-feasibility | Story | High | 5 | 1.5 | ✅ DONE — 17-attack 359-col corpus + 7-arm ablation → **NO-GO (documented NULL)**; no block beats split noise. Split out of AINOS3-30 on 2026-08-19 |
| AINOS3-77 | mode-transition-rule | Task | High | 3 | 1.0 | ✅ DONE — **R14 live** (debounced `ADCS_GNC.Mode` → DE-0005); IF verified blind across the transition |
| AINOS3-78 | cluster-345-regression | Spike | Medium | 2 | 0.5 | ✅ DONE — regression is **entirely INERTIAL** (−20.9); not data thinning (5,564 rows) but lost cross-mode transfer. **Routing SUNSAFE only recovers it for −0.23 pts overall** |
| AINOS3-45 | corpus-instance-4 | Task | Medium | 3 | 0.75 | ○ STRETCH — 4th corpus instance, collected at the 382-col schema (feeds signal-feasibility) |
| AINOS3-68 | deepsad-revisit | Spike | Low | 3 | 0.75 | ○ STRETCH — reopen Phase-5 DeepSAD **only if** signal-feasibility clears the gate |
| AINOS3-83 | ci-command-feature | Task | Low | 2 | 0.5 | → **BACKLOG** (2026-08-19) — first AC already answered by `signal-feasibility`: no full-`ci` counter moves under `:5012` injection (17 attacks / 41,434 frames), so this points at "document the bypass, close out-of-scope" rather than build |
| AINOS3-79 | detector-rigor | Epic | — | — | — | Detector hardening & measurement honesty |
| AINOS3-80 | metric-provenance-audit | Spike | Medium | 2 | 0.5 | ✅ DONE — 2 material findings: IF threshold calibrated **in-sample** (doc claimed held-out); IF training corpus **unrecorded** |
| AINOS3-81 | hybrid-drift-soak | Task | Medium | 1 | 0.25 | ✅ DONE — 7 h soak: **no drift** (margin widens); ⚠ **INERTIAL FP regression 0.54 %** vs documented 0.00 % |
| AINOS3-82 | benchmark-fayyaz | Spike | Medium | 3 | 1.0 | ✅ DONE — dataset pulled + reproduced; CuCD-ID is **trivially separable by session artifacts**; no head-to-head possible |
| AINOS3-42 | stakeholder-rollout | Epic | — | — | — | Stakeholder rollout & feedback (recurring) |
| AINOS3-76 | rollout-s26 | Task | Medium | 2 | 0.5 | ○ COMMIT — carryover: present the Sprint-26 readout + capture feedback (owner-action, slipped last sprint) |

**Committed set:** E = **16** (signal-feasibility 5 · mode-transition-rule 3 ·
metric-provenance-audit 2 · hybrid-drift-soak 1 · benchmark-fayyaz 3 · AINOS3-76 2) ·
T ≈ **4.75** — right at the ~16 E / ~7–8 T capacity, leaving headroom for the
signal-feasibility corpus run's unattended wall-clock.

**Status (2026-08-19, reconciled against Jira): 5 of 6 committed items ✅ DONE, plus one
stretch.** `AINOS3-77` · `AINOS3-80` · `AINOS3-81` · `AINOS3-82` · `AINOS3-88`
(signal-feasibility, split out of AINOS3-30) are **Done**, and the stretch spike
**`AINOS3-78`** (cluster-345 regression) is **Done** as well. **`AINOS3-76`** (stakeholder
rollout, owner action) is the only open item. Everything else — `AINOS3-30`, `-45`, `-68`,
`-83`, `-84`, `-85`, the two findings `-86`/`-87`, and the four late findings `-89`…`-92` —
is in the **backlog**.

The sprint's headline outcome is not the one planned: the signal lever returned a **NULL**,
while the *hardening* half surfaced defects nobody had tickets for — see below.

**Stretch set:** E = **10** (AINOS3-45 3 · AINOS3-68 3 · ci-command-feature 2 ·
cluster-345-regression 2) — pulled in only if the committed chain lands with headroom.
AINOS3-68 is **gated** on signal-feasibility clearing.

---

## 🟩 EPIC AINOS3-41 — Detection coverage expansion

**Sprint 27 slice — the signal lever.** Sections A and B validated every technique whose
footprint sits in a subscribed MID. The residual gap is *labeling* the DEAD/HIGH-VAR/
PASSIVE classes, which the evidence (AINOS3-33/39, NOS3-302, the honest-OOF overlay) says
is information-limited. This slice tests, for real, whether the recorded Section-B MIDs
carry the missing signal — and closes the two gaps this sprint's live work surfaced.

### AINOS3-88 — Ablate recorded Section-B MIDs for weak-class discrimination · `Story` · High · E 5 · T 1.5 (~12h)

> ⚠ **Key split 2026-08-19.** This section was written under `AINOS3-30`, but that key belongs
> to `extra-mids` — *"Subscribe extra MIDs to recover DEAD classes"* (E 8 / T 2.5) — which is
> **still OPEN in Jira** and describes different work. Reusing it here broke the crosswalk's
> immutability rule. This work is now the slug **`signal-feasibility`** under its own key
> **`AINOS3-88`**. **Do not close AINOS3-30 against the result below** — it remains open
> against its original scope. See the note at the foot of
> [`JIRA_CROSSWALK.md`](JIRA_CROSSWALK.md).

**Summary:** As an ML engineer, I want to know — before a full retrain — whether any
recorded-but-unused Section-B MID adds discrimination for the weak-label classes, so the
signal-adding bet rests on an ablation, not a hope.

**Description:** AINOS3-70 subscribed 16 MIDs for *recording* (CSV now 382 cols) but the
IF + classifier still train on the original 894 v5 features. The frozen
`csv_corpus_v3stage` predates those columns, so they cannot be ablated against it. This
ticket collects a **382-col corpus slice** biased toward the weak classes
(DEAD/HIGH-VAR: `EX-0012.08/.09`, `EX-0014.03/.04`; and PASSIVE-mode runs), builds
candidate features from the recorded MIDs, and runs a **leave-one-instance-out ablation**
(baseline 894-feat vs +candidate-block) to measure per-class OOF label-accuracy lift.
Prior partial results temper expectations — the CFE_TBL change-detect features returned
NULL (AINOS3-30 Sprint-25) and the sensor `*_DEVICE` packets were judged redundant with
the fused `ADCS_DI` view — so a NULL here is a valid, publishable outcome that reframes
those classes as truly information-limited.

**Acceptance Criteria:**

- A 382-col corpus slice collected covering the weak classes + PASSIVE (via
  `scenario_all_modes_dwell` / `run_attack_batch.py`); schema fingerprint recorded.
- Candidate feature block(s) built from the recorded MIDs; LOIO ablation vs the 894-feat
  baseline, per-class OOF label accuracy reported.
- **GO/NO-GO recommendation**: which MID(s), if any, lift which class, and by how much —
  or a documented NULL (information limit confirmed). No retrain/deploy from the spike
  itself; a positive result tickets the retrain as a follow-up.
- If a candidate moves the CFE_TBL table-activity fields (a real table-LOAD attack, unlike
  DE-0006's NOOP-only), record it — that is the **AINOS3-30-revival / AINOS3-68-gate**
  trigger.

**Estimate note:** E 5 carries corpus-collection + feature-design uncertainty and the real
possibility of a NULL. Unattended corpus wall-clock (~5 h) is on top of the T.

**Result:** ✅ DONE (2026-08-11) — **NO-GO, documented NULL.** Corpus: 17 attacks selected
from the measured per-class F1 in `cluster_taxonomy.json` (6 DEAD · 3 NEAR-DEAD · 5
HIGH-VAR · **3 ROBUST anchors** for contrast), 17/17 exit 0 in 2 h 43 m, **41,434 labeled
rows**, staged at `data/onair/csv_ainos3_30_s27/`. Live schema is a **strict superset** of
the frozen corpus (359 kept cols vs 250; 109 added, 0 removed), so the ablation is properly
controlled. Seven arms share one feature build and one row split
(`training/ablation_ainos3_30_s27.py`); the 109 columns were split into five blocks so a
positive result would point at a subsystem: baseline mF1 0.5261 → `+INGRESS` +0.0030,
`+SENSOR_HK` +0.0268, `+SENSOR_DEV` +0.0168, `+CDH` +0.0078, `+TBL` **+0.0000**,
`+ALL` +0.0159. **The negative control passed** — `TBL` reproduced the Sprint-25 NULL to
four decimals.

**Nothing survives the noise band.** Three attempts at sizing it, and the first two were
wrong in instructive ways: (1) a **seed sweep returned ±0.0000 on every arm** — a *dead
instrument*, since `HistGradientBoostingClassifier` with `early_stopping=False` is
deterministic below sklearn's 200k binning-subsample threshold; (2) a **test-set bootstrap**
gave `+SENSOR_HK` = +0.0270, 95 % CI [+0.0167, +0.0373], **excluding zero** — a trap, because
it resamples test rows while holding fixed the two things that actually vary; (3) a **split
sweep** (train_frac 0.60→0.80) shows the same effect **flipping sign**: +0.0832 / +0.0264 /
+0.0268 / −0.0260 / −0.0022, mean +0.0216, **std 0.0365 > mean**. The bootstrap CI was ~3×
too narrow. The baseline itself swings 0.3992→0.5615 on split placement alone.

**`INGRESS` is untested, not refuted** — all 10 `CI.*`/`TO.*` columns are numerically
constant 0 because the full `to`/`ci` apps are **idle by design** here (commands go via
`:5012`, telemetry via SBN). That is the *static-in-nominal* precondition R12/R13 rely on,
so it corroborates AINOS3-72; it just means **no attack in this corpus commands them**
(`EXF-0003.02` does, and wasn't in the weak-class list). ⚠ Two mis-diagnoses en route are
recorded in the writeup: a raw-string census counted OnAIR's `'[0]'` placeholder as variance,
and a suspected AINOS3-72 recording regression was refuted by diffing
`message_headers.py::TO_HkTlm_t` against `to_hktlm.h` (field-for-field match).

**Provenance:** ONE execution per technique ⇒ LOIO impossible; absolute numbers are
within-instance and **not comparable** to the LOIO 0.645 in `V5_DETECTOR_COVERAGE.md`. Only
deltas were ever the deliverable, and even those don't resolve. **The binding constraint is
corpus size, not feature design** — `AINOS3-45` (2nd instance) is now the prerequisite for
any re-run, and the tooling makes it a re-invocation. `AINOS3-68` (DeepSAD) **stays gated**:
this spike was its trigger and it did not fire. Full detail:
[`SIGNAL_FEASIBILITY.md`](SIGNAL_FEASIBILITY.md).

**Incidental:** 15 of 109 added columns are constant corpus-wide — all 6 `CFE_TBL` (known),
4 `TORQUER`, and 5 `ST_DEV` star-tracker fields (`IsValid`, `Q0`–`Q3`). An ADCS-relevant
sensor reporting nothing is worth its own look. Also **answers AINOS3-83's first AC**: no
full-`ci` ingest counter moves under `:5012`-injected commands, across 17 attacks / 41,434
frames.

### AINOS3-77 — R14: flag ADCS mode-force (SET_MODE) IF blind spot · `Task` · High · E 3 · T 1.0 (~8h) · ○ COMMIT

**Summary:** As a defender, I want an unexpected ADCS mode transition (a forced
`GENERIC_ADCS SET_MODE`) raised as an alert, because Sprint-26's live work showed a
mode-force is an IF blind spot.

**Description:** Directly observed 2026-07-30/31: commanding `SET_MODE` (0x1940 FC2) moves
`ADCS_GNC.Mode`, and the per-mode router then re-arms a **250-frame warmup**
(`ModeSwitchWarmupFrames`) during which detection is *suppressed* — so a pure mode-force
(the DE-0005 `SET_MODE` step, and the general safe-mode-subversion pattern) slips the
dynamics IF entirely. Add a rule-gate **R14** that flags a mode transition — keyed on a
static-in-nominal ADCS command counter (sibling of R6–R13) if one is exposed, else on an
`ADCS_GNC.Mode` baseline deviation (sibling of R5 monitor-state). The rule *is* the label
(mode-transition-legitimacy is an operator decision); it fires once per transition with
the leaky-integrator dwell the other rules use.

**Acceptance Criteria:**

- Footprint confirmed live: a forced `SET_MODE` moves the chosen observable; a nominal
  soak shows the mode is static (no spontaneous transitions → 0-FP).
- R14 built + deployed, labeled to the mode-force / safe-mode-subversion family
  (DE-0005); fires within a bounded dwell; incident wired.
- Unit tests (sibling of the R5/R6 tests); rule-gate suite green; plugin synced.
- Folded into the coverage overview + `V5_DETECTOR_COVERAGE.md`.

**Note:** closes a concrete, live-demonstrated gap; the mechanism (static-counter or
baseline-deviation + leaky integrator) already exists, so most of the E is
false-positive tuning (confirming modes truly don't self-transition in nominal ops).

**Result:** ✅ DONE (2026-08-11) — **R14 built, deployed, live-verified.** The ticket's
preferred design (a static-in-nominal ADCS command counter, R6–R13 sibling) is **not
viable**: `ADCS_HK.CommandCount` is a **wrapping uint8 that increments on routine HK
polling** — 264,019 changes across the AINOS3-81 soak — so it fails the static-in-nominal
precondition. R14 therefore keys on `ADCS_GNC.Mode` (the R5-style baseline-deviation
fallback), with two mechanisms R5/R13 don't have:

- **Debounce.** OnAIR's double buffer oscillates old/new for several frames per switch.
  Replayed over the soak, naive change-detection fires **22 times for 4 real transitions**;
  requiring the new value to persist `ModeDebounceFrames=5` collapses that to exactly 4.
- **Re-baseline after firing.** A mode force is one bounded event, not a persistent bad
  state, so *entering* a mode fires and *being* in one does not — unlike R5/R13, which latch
  until the field returns.

**Flap sub-rule LIVE + verified 2026-08-15.** Synced and OnAIR restarted; three forced
transitions ~40 s apart produced `R14:adcs-mode-force` incidents on transitions 1 and 2, then
on transition 3 **both** rules fired and the incident came out `cluster=DE-0005,
sub=adcs-mode-flapping` at **37 frames** vs 13 for the singles — the priority ordering and 4x
dwell correctly escalating the label rather than letting the weaker "one mode force" win the
aggregator's frame-count vote.

**0-FP** `[live-soak]`: replaying the deployed rule over the full **267,260-frame** soak
gives **4 rising edges and 4 `DE-0005` incidents — one per commanded transition, none during
any mode hold.** **Live-verified**: a forced `SET_MODE` SUNSAFE→INERTIAL raised
`[rule_gate][ALERT] R14:adcs-mode` and one bounded incident (13 frames, `cluster=DE-0005`,
`sub=adcs-mode-force`), while the IF logged **0 anomalies / 0 alerts across the 81 frames
spanning the transition** — the blind spot demonstrated and closed in the same run. A 2-min
hold produced no further incidents. R14 yields to R5 when both fire, so a full DE-0005
(LC disable *plus* mode force) still labels EX-0011 (family representative). **+10 unit
tests** (rule-gate suite 51 pass; 507 pass across plugin + training suites). Plugin synced to
the build tree; folded into `V5_DETECTOR_COVERAGE.md` (§F) and the coverage overlay.

### AINOS3-78 — Diagnose the hybrid's EX-0012.{03,04,05} regression · `Spike` · Medium · E 2 · T 0.5 (~4h) · ○ STRETCH

**Summary:** As an ML engineer, I want to know why the deployed hybrid *lost* label_ok on
the telemetry-indistinguishable `EX-0012.{03,04,05}` cluster (3→2, 2→1, 2→1 OOF) while
gaining elsewhere, so I can recover it or consciously accept the trade.

**Description:** The AINOS3-37 hybrid nets +6 label_ok OOF, but the `{03,04,05}`
modify-on-board-values cluster regressed. These are memory-write / table / scheduling
attacks that land across modes; the per-mode routing may split their (already thin)
training rows across heads. Diagnose: is it a data-thinning artifact (per-mode head
starvation) or a genuine mode-routing mismatch? Options if recoverable: route this cluster
to the global head, or fold it back via the confidence calibration. If not cheaply
recoverable, document it as an accepted trade (net +6 stands).

**Acceptance Criteria:**

- Root cause identified (per-mode row counts for the cluster; head-by-head label breakdown).
- A cheap mitigation evaluated (cluster-scoped global routing, or a training-row floor),
  net OOF label-accuracy re-measured — or a documented "accept the trade" with rationale.
- No BDOT/PASSIVE regression re-introduced; if a change deploys, it goes through the same
  live-verify + rollback discipline as the AINOS3-37 cutover.

**Result:** ✅ DONE (2026-08-19). **Root cause found, ticket hypothesis refuted, cheap
mitigation identified.**

**It is not data thinning.** The ticket proposed "per-mode head starvation — the routing may
split their already-thin training rows across heads". The rows are not thin: INERTIAL holds
**5,564** cluster rows (11.86 % of the mode) versus BDOT's 5,849 (11.46 %) — more than
SUNSAFE — and still performs worst.

**The whole regression is one mode.** Frame-level cluster accuracy, global vs hybrid:

| mode | rows | global | hybrid | Δ | head |
|---|--:|--:|--:|--:|---|
| SUNSAFE | 5,195 | 50.3 % | 49.5 % | −0.8 | per-mode |
| **INERTIAL** | 5,564 | 44.0 % | **23.1 %** | **−20.9** | per-mode |
| PASSIVE | 3,371 | 29.3 % | 29.3 % | **+0.0** | global (unchanged) |
| BDOT | 5,849 | 52.0 % | 52.0 % | **+0.0** | global (unchanged) |

PASSIVE and BDOT at exactly +0.0 are the control — they run identical code.

**Mechanism: loss of cross-mode transfer**, with precedent. AINOS3-33 found a PASSIVE-only
specialist scoring *below* the global model and concluded the global was "propped up by
cross-mode transfer". `EX-0012.{03,04,05}` is internally telemetry-indistinguishable, so it
leans on pooled signal more than most classes; specialising to one mode removes exactly what
was carrying it.

**Mitigation — route SUNSAFE only** (drop INERTIAL from per-mode routing):

| variant | overall | cluster |
|---|--:|--:|
| global head only | 61.14 % | 45.49 % |
| deployed hybrid | **62.15 %** | 39.45 % |
| hybrid, INERTIAL → global | 61.92 % | **45.27 %** |

Recovers essentially the whole cluster regression for **−0.23 pts overall**. The reason the
trade is so lopsided: INERTIAL's per-mode head is worth **+0.86** pts overall while costing
20.9 on this cluster; SUNSAFE's is worth **+3.00** and costs ~nothing. The hybrid's value was
almost entirely SUNSAFE.

⚠ **Two caveats before anyone deploys this.** (1) These are *frame-level* figures; the
ticket's metric is *incident-level* `label_ok` on a **6-incident** sample per technique, where
one flip is a 17 % swing — a 0.23-pt frame change may or may not move it. (2) AINOS3-37
recorded INERTIAL's gain as **+0.058** (LOIO technique-level) against the **+0.86 pts**
measured here frame-level; different metrics and not directly comparable, but the gap is
large enough to reconcile before acting. If the reconciliation holds, dropping INERTIAL from
routing is nearly free and also simplifies the model to a single per-mode head.

**Not deployed.** Rebuilding the hybrid with `route_modes=['MODE_SUNSAFE']` and live-verifying
it is beyond this spike's scope; it needs the AINOS3-37 discipline (one-line rollback,
live-verify). Recommended as a follow-up, not a sprint-27 change.

### AINOS3-83 — Full-`ci` HK command-ingest detector · `Task` · Low · E 2 · T 0.5 (~4h) · ○ STRETCH

**Summary:** As a defender, I want unauthorized command ingest caught via the full-`ci` app
HK (`0x0884`, now on the OnAIR pipe), so the command-injection family has an ingress-side
signal.

**Description:** AINOS3-72 re-pointed OnAIR to the full `to`/`ci` apps and put the full-`ci`
HK (`0x0884`) on the pipe as a bonus (deferred). `CI` owns the ground-link command path; its
HK exposes command-ingest counters. First **validate** whether those counters actually move
under externally-injected commanding — a live finding warned the *lab* CI is bypassed by the
`:5012` UDP→SB bridge (`CI_LAB.Payload.IngestPackets` stayed flat during DE-0010), so it is
unknown whether the FULL `ci` app registers `:5012`-injected commands or only genuine
ground-link traffic. If the counters move, build a rule-gate rule (sibling of R6–R13) labeled
to the command-injection / malicious-commanding family (IA-0007.02); if they don't, record
the bypass and close it out-of-scope.

**Acceptance Criteria:**

- Live check: does a full-`ci` command-ingest counter move under `:5012`-injected commands
  and/or genuine ground-link commanding? Result recorded either way.
- If it moves: a rule-gate rule built + deployed, labeled to the command-injection family;
  0-FP soak; folded into the coverage overview.
- If it doesn't: documented out-of-scope with the bypass reason (mirrors the lab-CI finding).

**Note:** the CI HK is already recorded (AINOS3-72 bonus), so this is validate →
build-or-close, not a subscription change.

---

## 🟦 EPIC AINOS3-79 — Detector hardening & measurement honesty

**Summary:** Keep the deployed stack trustworthy — soak the live hybrid for drift, and make
sure every published number is honest and provenance-tagged, so we never again ship an
in-sample-optimistic figure as if it were operational.

**Description:** Prompted by two Sprint-26 findings: the live hybrid is new (needs a drift
soak like the v5 IF got), and the coverage overlay was silently showing in-sample-optimistic
labels (76.9 % vs the honest 42.3 % OOF) for two months until this sprint caught it. This
epic hardens what we shipped and audits how we measure it.

### AINOS3-80 — Sweep reported metrics for in-sample optimism · `Spike` · Medium · E 2 · T 0.5 (~4h) · ○ COMMIT

**Summary:** As an analyst, I want every headline number in the coverage doc + overlay +
demo tagged with its provenance (in-sample vs out-of-fold vs live-soak), so we never again
ship an optimistic in-sample figure as if it were the operational one.

**Description:** The incident-label accuracy sat at an in-sample 76.9 % for two months
before being corrected to the honest OOF 42.3 %. Audit the other published numbers —
frame-level classifier accuracy, per-class F1, incident recall, the per-tier figures — for
the same trap, and annotate each with its provenance. Where a number is in-sample, either
recompute it OOF or label it clearly.

**Acceptance Criteria:**

- Each headline metric in `V5_DETECTOR_COVERAGE.md` + the overlay carries a provenance tag
  (OOF / in-sample / live-soak / calibrated-FP).
- Any metric found to be in-sample-optimistic is recomputed OOF or explicitly flagged.
- A one-line convention added so future numbers state provenance by default.

**Result:** ✅ DONE (2026-08-11) — **2 material findings, 1 minor.** Register of all 18
headline metrics + the overlay in
[`AINOS3_80_METRIC_PROVENANCE.md`](AINOS3_80_METRIC_PROVENANCE.md); tags `[OOF]` /
`[live-soak]` / `[in-sample]` / `[design-target]` applied throughout
`V5_DETECTOR_COVERAGE.md`, and the convention added at the top.

- **F1 (material):** the doc claimed incident detection was honest because "the threshold is
  calibrated on **held-out** nominal". **It is not** — the calibration row counts are
  *identical* to the model's training row counts in all four modes (296 / 19,641 / 14,367 /
  53,094), so the threshold is the 1 % quantile of the model's **own training scores** and
  `actual_fp_rate ≈ 1.00 %` is true by construction. ⚠ Initially judged benign ("generalised
  conservatively"); **AINOS3-81 refuted that** — see the amendment: conservative for
  BDOT/PASSIVE/SUNSAFE, **optimistic by 7.5× for INERTIAL**.
- **F2 (material):** the deployed IF pickle records **no training-corpus identity** (no
  csv-dir, manifest list, or dates), and no doc records the `train.py` invocation. So
  disjointness between IF training nominal and any evaluation corpus is **unverifiable** —
  which reclassifies the catch rates, the ~61 % frame-level figure and the 92.8 %/67.8 %
  incident recalls as `[unverifiable]`, *not wrong*. The classifier already does this right
  (`training_dates`); the IF should match.
- **F3 (minor):** headline hybrid LOIO is quoted **0.646**; the artifact says **0.6453** →
  0.645. More useful: the fold spread is **±0.036**, *wider than most deltas quoted against
  it* (including the hybrid's own +0.018 over the v3 global head). The doc now carries the
  spread.
- **F4 (new convention clause):** provenance applies to the **error bar**, not just the point
  estimate. `signal-feasibility` produced a correctly-out-of-fold metric whose bootstrap CI was ~3× too
  narrow because it resampled test rows instead of the split. Intervals must now state what
  was resampled.

The overlay had the right source (hybrid OOF) but **displayed no provenance labels at all**;
`gen_nos3_coverage.py` now emits a `provenance` block, regenerated and re-inlined into
`sparta_coverage.html` via `build_overlay.py`.

### AINOS3-81 — Long soak: hybrid + calibration hold, no drift · `Task` · Medium · E 1 · T 0.25 (~2h attended) · ○ COMMIT

**Summary:** As an operator, I want a multi-hour nominal soak confirming the live hybrid
holds ≤1 % FP with no progressive drift and the per-mode calibration stays sane, mirroring
the v5 IF drift soak.

**Description:** The hybrid went live 2026-07-30. Run a fresh-launch soak (≥6 h,
`analyze_soak_drift.py`) across ADCS modes, confirming the classifier's IF-gated FP stays
in the measured 0.0–0.2 % band, the per-mode heads don't drift, and calibrated confidences
stay in range. Cheap, mostly unattended — the point is the belt-and-suspenders confirmation
on the new deployed model.

**Acceptance Criteria:**

- ≥6 h fresh-launch soak; per-mode FP + calibrated-confidence distributions reported.
- No progressive drift (matches the v5 drift-soak result); if drift appears, ticket it.
- Result folded into the coverage doc's soak numbers with provenance = live-soak.

**Result:** ✅ DONE (2026-08-11) — **no drift, but an INERTIAL FP regression.** 7 h
fresh-launch soak, four sequential mode legs (BDOT/INERTIAL/PASSIVE 60 min, **SUNSAFE 240
min last** so its window covers uptime T+3h→T+7h, the band where v2 was suspected of
drifting), all legs exit 0, 140,631 frames, deployed hybrid confirmed loaded.

- **Drift: PASS.** SUNSAFE alert FP **0.0001**; the 1st-percentile score margin does not
  merely plateau, it **widens** (0.052 → 0.086). BDOT/PASSIVE flat at 0.0000. Reproduces the
  2026-06-09 v5 result and extends it to the hybrid.
- ⚠ **INERTIAL FP does not reproduce: 0.54 % operational (raw 7.5 %)** vs the documented
  0.00 % — 27× the stated 0.0–0.2 % band. **Not drift** (0.63 % → 0.44 % across the leg).
  Root cause is AINOS3-80 **F1**: the in-sample threshold promised 1 % raw FP per mode and
  delivers 0.0× / **7.5×** / 0.0× / 0.9×. Only SUNSAFE (53,094 training rows) lands where the
  calibration said. Hysteresis has been silently absorbing the error.
- **Operational impact:** **71 false incidents/hour in INERTIAL** (0 BDOT/PASSIVE, 2.5/h
  SUNSAFE) against the doc's "under 1 alarm per ~5 hours". All labelled `cluster=nominal`, so
  a consumer filtering on that sees none — **not verified** that the operator view does.
- **Gates clean:** staleness **0**, consistency **0** over ~141 K frames; rule-gate **2
  edges in 7 h** (fresh-launch discipline works). **Classifier: 0 false attack labels** on
  2,203 IF-gated frames; calibrated confidences in range but **saturated at ~0.999**, so this
  soak does not exercise the calibration's mid-range.
- **Tooling defect:** `analyze_soak_drift.py` defaults to `--hz 4.2`; true rate measured
  against known leg durations is **~5.6 Hz**, mislabelling uptime bins by ~33 %. All figures
  above used `--hz 5.6`.

Full detail: [`AINOS3_81_HYBRID_DRIFT_SOAK.md`](AINOS3_81_HYBRID_DRIFT_SOAK.md).

### AINOS3-82 — Compare vs Fayyaz CuCD-ID NOS3/cFS dataset (Data in Brief 2026) · `Spike` · Medium · E 3 · T 1.0 (~8h) · ○ COMMIT

**Summary:** As an ML engineer, I want a structured comparison of our detector against the
Fayyaz et al. (2026) CuCD-ID NOS3/cFS dataset + method — the closest published benchmark on
the same stack — to sanity-check our numbers independently.

**Description:** `.claude/Fayyaz_2026_CubeSat_NOS3_dataset.pdf` (Data in Brief 65 (2026)
112598; Ontario Tech) releases a labelled NOS3/cFS dataset: 25,000 balanced raw records ×
31 features (CCSDS-header fields + 20-second sliding-window statistics + system counters)
across **5 classes** — Normal, Command Flooding, Data Injection, Defence Impairment, Storage
Exhaustion — plus a 22,465-record augmented/noised set (9 documented noise categories) and
COSMOS v4 reproduction scripts (public Mendeley DOI 10.17632/7n2d42pm3n3). Their companion
paper (*Computers and Security* — real-time embedded-TinyML IDS) holds the detection results.
Scan both, map their classes to our SPARTA taxonomy, and compare method + numbers.

**Acceptance Criteria:**

- Their method extracted: features (CCSDS + 20 s sliding window vs our raw+delta 894-feature
  vector), model (embedded TinyML vs our per-mode IF gate + selective hybrid classifier),
  attack taxonomy, and *reported detection/classification metrics* (from the companion IDS
  paper if obtainable, else the Data-in-Brief).
- Their 5 classes mapped to our SPARTA leaves — command flooding ↔ EX-0013/DE-0010, data
  injection ↔ EX-0014/EX-0012, storage exhaustion ↔ EX-0010/resource-exhaustion, defence
  impairment ↔ DE-0001/EX-0011/DE-0005, normal ↔ nominal — noting where our taxonomy is finer.
- **Evaluation-honesty cross-check** (ties to `metric-provenance-audit`): do they split to
  avoid the sliding-window leakage they warn about, or report in-sample? Compare to our LOIO
  OOF discipline (the 76.9→42.3 lesson) so any head-to-head number is apples-to-apples.
- A short comparison writeup (`components/onair/BENCHMARK_FAYYAZ_CUCDID.md`): where we align,
  where we differ, what to borrow (their 9 augmentation noise categories for robustness; their
  balanced 5-class framing; the CCSDS + 20 s window feature recipe), and honest limits of the
  comparison.
- **Stretch within the ticket** (note, don't commit unless it's cheap): pull their public
  Mendeley dataset and either score our classifier on it or run their reproduction scripts,
  for a direct number.

**Note:** high learning value, low risk — nearest published NOS3/cFS IDS benchmark; a rare
chance to sanity-check our numbers against an independent group on the same simulator.

**Result:** ✅ DONE (2026-08-11) — writeup in
[`BENCHMARK_FAYYAZ_CUCDID.md`](BENCHMARK_FAYYAZ_CUCDID.md), harness in
`training/benchmark_fayyaz.py`. The **stretch was taken**: the Mendeley dataset was pulled
(CC BY 4.0, both published SHA-256 hashes verify) and reproduced against our own model
family.

- **No head-to-head number is possible, and that is the finding.** Their 30 features (CCSDS
  headers + 20 s arrival-window statistics + host cgroup memory) and our 894 (raw+delta over
  359 telemetry columns incl. GNC dynamics) share **no overlapping column**, and they emit
  one row per *packet* vs our 1 Hz *frame*. Their "normal" is a scripted 5,000-command NOOP
  storm, not idle ops.
- **Their released table is trivially separable by several independent routes.** All-features
  accuracy **1.0000**; the flight-software **memory columns alone 1.0000**; `TimeRadians`
  (a clock) **alone 0.8818** on a balanced 5-class task; **5 of 22 columns reach ≥0.95
  alone**. Each class is **one contiguous 5,000-command run**, so class identity is perfectly
  confounded with session identity, and three class pairs are separable by wall-clock alone.
- **Their recommended split does not fix the leak it warns about** — accuracy is identical
  (1.0000) under a random split and their per-class chronological split, because the cut
  falls *inside* each single-run class. Their README Option 2 isn't a valid supervised
  protocol; Option 3 needs a group column the release doesn't ship. **LOIO is structurally
  impossible** on it (1 run/class vs our 3) — the strongest external endorsement of our LOIO
  discipline.
- **Their 4 attacks all map onto leaves we already detect**, three via a deployed rule firing
  on the exact mechanism (flood→EX-0013; LC/CS disable→DE-0001/**R5**; FM file spam→
  EX-0010/**R11**; MM_POKE GPS→EX-0014.03/EX-0012.03).
- **Worth borrowing:** their command-**ingress** feature family (they classify GPS poke
  injection easily from ingress while we score F1 = 0.000 on the same attack from egress —
  the sharpest evidence yet for AINOS3-69's *observability, not capacity* conclusion), their
  arrival-time window statistics, and their 9 documented augmentation noise categories.
- The companion *Computers & Security* IDS paper is **paywalled**; a web summary attributing
  F1 87.66–99.59 % to this group names classes (DoS/fuzzy/replay) that don't match CuCD-ID's
  five, so it is **treated as unverified and not used**.

---

## 🟪 EPIC AINOS3-42 — Stakeholder rollout & feedback (recurring)

### AINOS3-76 — Stakeholder rollout — Sprint 26 · `Task` · Medium · E 2 · T 0.5 (~4h) · ○ COMMIT

**Summary:** Present the Sprint-26 result — Section-B detections, the live hybrid, and the
honest-OOF overlay correction — and capture feedback as backlog.

**Description:** Carryover: the Sprint-26 prep is done (overlay + docs refreshed, live
hybrid) but the **presentation slipped** (owner-action, not completed). Re-attempt this
sprint. Lead with the honesty story — detection is strong and unchanged, labeling improved
(+7.7 pts) *and* the overlay stopped overstating it — since that reframes the lower
displayed number correctly. The script is now
[`SPRINT_27_STAKEHOLDER_ROLLOUT.md`](SPRINT_27_STAKEHOLDER_ROLLOUT.md) — split out of the
recurring playbook (`STAKEHOLDER_ROLLOUT_TEMPLATE.md`) on 2026-08-19 so each sprint's
readout is preserved instead of overwritten. ⚠ It now covers **Sprints 26 and 27**, and
leads with the six Sprint-26 claims Sprint 27 overturned.

**Acceptance Criteria:**

- Doc + overview presented — **owner action** (cannot be automated); the "Read this before
  presenting" correction table + both "What changed" sections are the script.
- Feedback captured in the `SPRINT_27_STAKEHOLDER_ROLLOUT.md` table, then filed as backlog
  tickets (slug assigned at triage, crosswalk row added).

---

## 📋 Backlog (carryover / not sprinted)

| Jira | Slug | Type | E | T | Summary |
|---|---|---|--:|--:|---|
| AINOS3-44 | tcn-feature | Story | 5 | 1.5 | TCN reconstruction-error feature, scoped to EX-0008 ATS/RTS |
| AINOS3-46 | demo-tier-bc | Story | 3 | 1.0 | Demo app Tier B/C — the live "detector in action" demo |
| AINOS3-47 | foundation-baseline | Story | 8 | 2.5 | Foundation-model (MOMENT/THEMIS) zero-shot baseline |
| AINOS3-84 | drop-bus-activity-retrain | Task | 3 | 0.75 | AINOS3-39 follow-up: retrain dropping the harmful pure bus-activity features (`CFE_SB.MemInUse`, global EVS rate) — small PNT/theft/denial upside |
| AINOS3-85 | actuator-saturation-fidelity | Spike | 2 | 0.5 | The EX-0005.02 RW-torque path didn't build a real body tumble; find an injection that reaches actuator saturation (tests the within-mode-recovery vs no-FDIR boundary) |
| AINOS3-86 | inertial-false-alarms | Story | 5 | 1.5 | **HIGH** — INERTIAL nominal FP measured **33.6 %**; mode currently unusable for detection. Settling hypothesis refuted |
| AINOS3-87 | detect-eps-switch | Story | 3 | 1.0 | EX-0012.09 EPS switch toggle is detected by **nothing** in steady flight (0/3 reps) despite a published 99 % catch rate |
| AINOS3-89 | catch-rate-provenance-gap | Spike | 3 | 0.75 | Published per-technique catch rates disagree with measurement in **both** directions — `EX-0014.04` 98 % vs 7.4 % |
| AINOS3-90 | verify-nominal-incident-filter | Task | 1 | 0.25 | Does the operator view filter `cluster=nominal`? Decides whether INERTIAL's 71 false incidents/hr are user-visible |
| AINOS3-91 | startracker-inert-fields | Spike | 2 | 0.5 | 5 `ST_DEV` fields constant corpus-wide — an ADCS sensor reporting nothing |
| AINOS3-92 | soak-drift-hz | Task | 1 | 0.25 | `analyze_soak_drift.py --hz` default 4.2 vs true ~5.6 — every uptime bin mislabelled ~33 % |
| — | overlay-column-scope-mismatch | Bug | 2 | 0.5 | Overlay displays **Catch** (SUNSAFE-only) next to **Incidents** (contains **zero** SUNSAFE) as though comparable — two people have already drawn a false conclusion from it |

`AINOS3-68` (DeepSAD) stays **gated** — reopen only if `signal-feasibility`
finds a MID that broadens the labeled signal, or a validated attack finally activates a
CFE_TBL table (reviving the dormant change-detect feature).

The two new backlog slugs below carry full bodies (per the Summary+Description rule); the
older backlog rows keep their bodies in the sprint that scoped them.

### AINOS3-84 — Retrain dropping harmful bus-activity features · `Task` · Backlog · E 3 · T 0.75 (~6h)

**Summary:** As an ML engineer, I want a retrain that drops the pure bus-activity features the
AINOS3-39 audit found net-harmful, for a small free labeling gain on PNT / theft / denial.

**Description:** The AINOS3-39 counter-reliance audit found the generic counters net-contribute
overall, but a few *pure bus-activity* features MASK real signal — dropping `CFE_SB.MemInUse`
and the global EVS rate raised EX-0014.04 (PNT) F1 and helped IMP-0003 (denial) / IMP-0006
(theft). This is a scoped, low-risk retrain: remove only the demonstrably-harmful pure
bus-activity features (not the genuine per-app streams), retrain, and confirm LOIO shows no
regression elsewhere before any deploy. Best folded into a `signal-feasibility` retrain if that clears,
to avoid a redundant retrain/deploy cycle.

**Acceptance Criteria:**

- The harmful pure bus-activity features (per AINOS3-39) removed; classifier retrained on the
  frozen corpus.
- LOIO shows the PNT/theft/denial gain retained with no regression on other clusters or modes.
- Deploy only through the AINOS3-37 live-verify + one-line-rollback discipline; ini + build
  tree synced.

### AINOS3-86 — Bring INERTIAL's false-alarm rate into the design band · `Story` · **High** · E 5 · T 1.5 (~12h)

**Summary:** As an operator, I want INERTIAL's nominal false-alarm rate brought under the
1 % design target, because it currently measures **33.6 %** and that makes the mode unusable
for detection and un-evaluatable for coverage.

**Description:** An escalating history, each measurement larger than the last:

| measurement | conditions | nominal FP |
|---|---|--:|
| published | 35 K frames / 116 min | **0.00 %** |
| AINOS3-81 soak | 60 min hold | 0.54 % operational / **7.5 % raw** |
| steady-flight replication | 12 runs, 600 s hold | **33.6 %** (range 21.1–48.5 %) |

The settling-transient explanation offered for the 8-minute pilot runs is **refuted**: 10
minutes is not enough for the rate to subside, and it lands far above the 60-minute soak.
Every INERTIAL lift measurement sits on this noise floor, so the mode cannot currently be
evaluated for attack detection at all — which is why the replication's INERTIAL column was
discarded.

One contributing cause is known: the threshold is calibrated **in-sample** (AINOS3-80 **F1**)
— INERTIAL's threshold promised 1 % raw FP and the soak delivered 7.5 %. But that does not
explain 33.6 %, so there is a second factor. Candidates, in rough order of suspicion:

1. **Training gap.** INERTIAL has 19,641 training rows from a *single* 116-minute session.
   That may not cover the mode's normal operating range — the same root cause as BDOT's 296
   rows and the missing sun-acquisition examples.
2. **Missing target quaternion.** INERTIAL pointing takes a commanded attitude
   (`GENERIC_ADCS_INERTIAL_QUATERNION_CC`). Absent one, the controller may drive toward a
   default attitude with sustained large control effort — dynamics that legitimately look
   anomalous. None of our scenario tooling ever sends that command.
3. **Genuinely long settling.** The mode may need far more than 10 min, in which case the
   250-frame (~45 s) warmup is wrong for INERTIAL specifically.

**Acceptance Criteria:**

- Root cause identified and (1)/(2)/(3) distinguished — e.g. a ≥ 2 h INERTIAL soak run twice,
  with and without a commanded target quaternion, reporting nominal FP against uptime.
- Fix applied to the cause, not the symptom: retrain/recalibrate on a proper INERTIAL
  baseline; or command a quaternion and fix the scenario tooling; or set an INERTIAL-specific
  warmup from the measured settling time.
- INERTIAL nominal FP under the 1 % design target, measured on **held-out** nominal.
- Re-soak to confirm; coverage doc updated with the measured value and its provenance tag.

⚠ **Do not fix by tightening the threshold alone.** The ROC sweep showed tightening INERTIAL
to a 0.1 % target drives its false alarms to 0.00 % but **collapses its attack detection 60×**
(12.4 % → 0.2 %). Any threshold change must be paired with an attack-detection measurement —
see the held-out-recalibration follow-on above.

### AINOS3-87 — EX-0012.09 EPS switch toggle is undetected · `Story` · Medium · E 3 · T 1.0 (~8h)

**Summary:** As a defender, I want an EPS power-switch toggle detected, because the
steady-flight replication found **nothing** detects `EX-0012.09` — not the anomaly detector,
not any rule — while it is published at a **99 %** catch rate.

**Description:** Measured across 3 independent runs in held SUNSAFE: IF lift **−0.4 ± 0.1**
(0.00 % of attack frames flagged) and **no rule-gate rule fired in any run**. The attack
sends `EPS_FC_SWITCH` with a `(switch_num, state)` payload — a **discrete state change**, so
the dynamics IF is structurally blind to it *by design*. That is expected and fine; what is
not fine is that its two siblings are covered and this one is not:

| technique | mechanism | caught by |
|---|---|---|
| EX-0012.08 | `ADCS_SET_MODE` | R14 (2/3 reps) |
| EX-0014.04 | GPS `FC_DISABLE` | R1 (2/3), R3 (1/3) |
| **EX-0012.09** | **`EPS_FC_SWITCH`** | **nothing (0/3)** |

The published 99 % comes from the pre-fix corpus, where 83 % of attack frames sat inside a
post-mode-switch blind window — it does not describe steady-flight behaviour.

First establish the on-board footprint, because the outcome forks:

- **If a recorded field moves** (an `EPS.DeviceHK.*` switch state, an EPS command counter),
  this is a cheap R1/R5/R6-style rule — baseline deviation or static-in-nominal new-high.
- **If nothing moves**, the technique is **UNSUBSCRIBED** and should be *reclassified* rather
  than detected. That is still a valuable outcome: it corrects a 99 % claim to an honest
  "structurally invisible", and tells us whether subscribing an EPS MID would close it.

**Acceptance Criteria:**

- Footprint confirmed live: run EX-0012.09 in held SUNSAFE (`single_mode_hold_SUNSAFE`) and
  identify which recorded field, if any, changes. Parse with `csv.DictReader`, never
  `awk -F','`.
- **If an observable moves:** rule built as a sibling of R1/R5/R6–R13, labeled to EX-0012.09;
  0-FP over a nominal soak; unit tests; plugin synced to the build tree; live-verified.
- **If nothing moves:** reclassified UNSUBSCRIBED in `V5_DETECTOR_COVERAGE.md` and the SPARTA
  matrix, with the evidence and a note on which MID would be needed.
- Either way, the published 99 % catch rate is corrected to what is actually measured.

### AINOS3-89 — Published catch rates disagree with measurement · `Spike` · Medium · E 3 · T 0.75 (~6h)

**Summary:** As an analyst, I want to know why published per-technique catch rates disagree
with fresh measurement **in both directions**, because until that is explained no
per-technique number in the coverage doc can be quoted with confidence.

**Description:** Measuring the same techniques on the 2026-08-11 corpus at the deployed
threshold gave results that diverge sharply from the published table, and not consistently:

| technique | published | measured | direction |
|---|--:|--:|---|
| EX-0014.04 PNT | 98 % | **7.4 %** | far worse |
| DE-0003.06 | < 25 % | **48.7 %** | far better |

A 90-point gap is too large for instance variance. Candidate causes: the attack script
behaves differently between collections (the Section-A campaign vs the weak-class corpus);
the published numbers came from a different corpus or a different threshold; or the
corruption-window labelling differs. This is distinct from the transient confound already
resolved by the steady-flight replication — these are same-corpus, same-threshold
comparisons.

**Acceptance Criteria:**

- Cause identified for at least the `EX-0014.04` case, the largest gap.
- Determine whether the published table, the recent corpus, or both are unrepresentative.
- Every per-technique catch rate in `V5_DETECTOR_COVERAGE.md` either re-derived from a named
  corpus with a provenance tag, or explicitly marked as unverified.
- Note recorded in `AINOS3_80_METRIC_PROVENANCE.md`, which owns the provenance register.

### AINOS3-90 — Is `cluster=nominal` filtered from the operator view? · `Task` · Medium · E 1 · T 0.25 (~2h)

**Summary:** As an operator, I want to know whether incidents labelled `cluster=nominal`
reach the operator display, because that single fact decides whether INERTIAL's **71 false
incidents per hour** are an invisible annoyance or a credibility problem.

**Description:** The AINOS3-81 soak raised 81 false incidents in 7 h of nominal flight — 71 of
them in a single hour of INERTIAL — all labelled `cluster=nominal`. If the overlay / operator
view filters those out, the impact is confined to log volume. If it does not, the monitor
cries wolf roughly once a minute in that mode, which would dominate any stakeholder
impression of reliability. **We have not checked.** Cheap to answer and it re-prioritises
`inertial-false-alarms` (AINOS3-86) either way.

**Acceptance Criteria:**

- Determine, from the deployed overlay/reporter path, whether `cluster=nominal` incidents are
  surfaced or suppressed. Evidence, not inference.
- If surfaced: raise the priority of AINOS3-86 and note the operator impact in
  `V5_DETECTOR_COVERAGE.md`.
- If suppressed: record where the filter lives, so it is not removed by accident later.

### AINOS3-91 — 5 `ST_DEV` star-tracker fields are constant · `Spike` · Medium · E 2 · T 0.5 (~4h)

**Summary:** As a defender, I want to know why five star-tracker fields never change, because
an ADCS-relevant sensor reporting nothing is either a dead subscription or a blind spot, and
both matter.

**Description:** In the 41,434-row weak-class corpus, `ST_DEV.Generic_star_tracker.IsValid`
and `.Q0`–`.Q3` are **constant across every frame**. Found incidentally during the
signal-feasibility ablation, where 15 of 109 added columns were inert — the other ten are
explained (6 `CFE_TBL` known-dormant, 4 `TORQUER`), these five are not. A star tracker
supplies attitude quaternions; if it genuinely produces nothing, any attack on it is
invisible, and the fused `ADCS_DI` view may be carrying the whole attitude signal alone.

**Acceptance Criteria:**

- Determine whether the star tracker is emitting and OnAIR is mis-parsing, or the sim never
  populates the fields (compare against the FSW struct as done for `TO_HkTlm_t` in
  AINOS3-30/88).
- If mis-parsed: fix the schema and confirm the fields move.
- If never populated: record it, and reclassify any star-tracker technique that depends on
  them as UNSUBSCRIBED rather than covered.

### AINOS3-92 — `analyze_soak_drift.py` uses the wrong sample rate · `Task` · Low · E 1 · T 0.25 (~2h)

**Summary:** As an analyst, I want the drift tool to derive the frame rate from the data,
because its hardcoded 4.2 Hz default mislabels every uptime bin by about a third.

**Description:** Measured against legs of known wall-clock duration, the true rate is
**~5.6 Hz** (5.36–5.79 across modes), not the 4.2 Hz default. At 4.2 a bin labelled
"T+30–60 min" actually covers roughly T+22–45 min. It does not change any pass/fail verdict —
drift is judged on the trend, not the bin labels — but every published drift table has
mislabelled time axes, and the AINOS3-81 figures were only correct because `--hz 5.6` was
passed explicitly.

**Acceptance Criteria:**

- Rate derived from the side file (frame count ÷ elapsed wall-clock) rather than assumed;
  `--hz` retained as an override.
- Warn when the derived rate differs from any supplied `--hz` by more than ~10 %.
- Any drift table already published with the 4.2 default is re-checked or annotated.

### overlay-column-scope-mismatch — `Catch` and `Incidents` are not comparable · `Bug` · Medium · E 2 · T 0.5 (~4h)

**Summary:** As a presenter, I want the overlay to stop displaying two figures side by side
that describe non-overlapping populations, because reading across them produces confident
wrong conclusions — and it already has, twice.

**Description:** The technique panel shows **Catch** and **Incidents** as adjacent columns.
They cannot be compared:

- **Catch** is the per-frame flag rate **in SUNSAFE only**.
- **Incidents** are attributed to each attack's **first corruption frame's mode**. Attacks
  start where the FSW boots, so the corpus holds **91 PASSIVE · 23 INERTIAL · 1 BDOT ·
  0 SUNSAFE** incidents.

The two columns therefore share **zero attacks**. No arithmetic between them means anything
— not a difference, not a ratio, not a direction — yet the layout invites exactly that.
`V5_DETECTOR_COVERAGE.md` §B already warns these are "two views that must not be confused",
but the overlay presents them as if they were one.

This is not hypothetical. **Two false conclusions have already been drawn from it:**

1. `EX-0012.09` showing "0 % caught" beside "3/3 incidents" was read as a stale-data
   contradiction. It is not — those incidents are simply all non-SUNSAFE.
2. `EX-0012.08` (incident recall 67 % *below* its 100 % catch) was flagged as an inverted
   result suggesting the incident aggregator was dropping real signal, and was one step from
   being ticketed as a detector defect. It is an artifact of comparing disjoint populations.
   `app/check_overlay_consistency.py` carries the retracted test as a comment so the mistake
   is not re-made.

The fix is presentational, not analytical — no re-measurement is required, which is what
separates this from **AINOS3-89** (that one owns whether the Catch *values* are right; this
one owns whether they can be read against the neighbouring column at all).

**Acceptance Criteria:**

- Each column states its population in the UI — at minimum "SUNSAFE frames" on Catch and the
  attributed-mode rule on Incidents — so scope is visible without opening the coverage doc.
- A panel whose Incidents contain no frames from Catch's mode does not render them as a
  side-by-side pair, or renders them visibly separated.
- The footer key explains that the two columns are not comparable and why (one sentence).
- `check_overlay_consistency.py` still passes with no new blocking finding; its `SAYS-BOTH`
  rule is re-examined once the presentation changes, since it exists to catch the same
  misreading.
- Ideally: report incidents per mode, or restrict the pairing to a common mode, so the
  comparison becomes meaningful rather than merely labelled — record the decision either way.

### AINOS3-85 — Reach actuator saturation for the recovery-boundary test · `Spike` · Backlog · E 2 · T 0.5 (~4h)

**Summary:** As a security researcher, I want an injection that drives the ADCS into genuine
actuator saturation, so the "within-mode recovery vs no autonomous FDIR" boundary is tested
empirically instead of inferred.

**Description:** The Sprint-26 recovery experiment showed the FSW self-recovers a *mild*
perturbation within a mode (BDOT drove `|Mcmd|` 0→30 to null the rate) but has no autonomous
safing (no HS app). The extreme branch — a disturbance exceeding actuator authority, where the
controller CAN'T recover and, lacking FDIR, wouldn't safe itself — remained inference: the
EX-0005.02 `RW SET_TORQUE +3000` path never built real body momentum (`|Hwhl|` stayed pinned
at 0.0016; the sim didn't integrate a tumble). Find an injection that reaches saturation
(sustained/large RW torque, a body-rate initial condition, or a different actuator path),
observe whether the within-mode controller diverges, and confirm no autonomous mode-change
fires.

**Acceptance Criteria:**

- An injection reproducibly drives `|wbn|` / wheel momentum past the controller's recovery
  authority (a real tumble / RW saturation), verified via `csv.DictReader`.
- Recorded: does the within-mode controller diverge, and does `ADCS_GNC.Mode` stay put (no
  autonomous safing)? — resolving the extreme-case claim from inference to fact.
- Any new observable it surfaces (e.g. a saturation flag) noted as a possible detector input.

---

## Findings this sprint that had no ticket (2026-08-11)

The hardening half produced more than it was scoped to. Ticketing status is in the right-hand column; the three-item chain (1–3) is covered by
`AINOS3-86` plus the follow-on above. They
need keys before Sprint 28 planning. The first three are one causal chain and probably want
a single ticket.

| # | Finding | Source | Pri |
|---|---|---|---|
| 1 | **IF threshold calibrated in-sample** — calibration rows == training rows in all 4 modes; the doc claimed held-out. ⚠ **Scope enlarged 2026-08-14: all four thresholds are mis-set, in different directions** — see follow-on below | AINOS3-80 F1 | **High** |
| 2 | **INERTIAL FP regression 0.54 %** (raw 7.5 %, 7.5× its calibration target) vs a documented 0.00 %; 71 false incidents/hour | AINOS3-81 | **High** |
| 3 | **IF training corpus unrecorded** — no csv-dir/manifest/dates in the pickle, so 4 headline metrics are `[unverifiable]` | AINOS3-80 F2 | **High** |
| 4 | `analyze_soak_drift.py --hz` defaults to 4.2; true rate ~5.6 Hz → uptime bins mislabelled ~33 % | AINOS3-81 | Low → **AINOS3-92** |
| 5 | 5 `ST_DEV` star-tracker fields (`IsValid`, `Q0`–`Q3`) constant corpus-wide — an ADCS sensor reporting nothing | AINOS3-88 | Medium → **AINOS3-91** |
| 6 | Operator-facing filtering of `cluster=nominal` incidents **unverified** — determines whether finding 2 is user-visible | AINOS3-81 | Medium → **AINOS3-90** |

**Recommended fix for 1–3:** re-derive the IF threshold on a held-out split of the baseline
corpus, and persist training inputs into the pickle (mirroring the classifier's
`training_dates`). That closes the false "held-out" claim, likely fixes INERTIAL, and
converts four `[unverifiable]` metrics into verifiable ones. Re-soak INERTIAL to confirm.

**Also re-scoped by results:** `AINOS3-45` (2nd corpus instance) is promoted from stretch to
**prerequisite** for any `signal-feasibility` re-run — corpus size, not feature design, is the binding
constraint. `AINOS3-83` has its first AC answered (**no** full-`ci` counter movement under
`:5012` injection), pointing it at "document the bypass and close out-of-scope" unless
genuine ground-link commanding is tested. `AINOS3-68` **stays gated**.

---

## Follow-on work agreed 2026-08-14

### AINOS3-88 follow-on — two more collection rounds

Round 1 could not resolve a 2-point effect because every technique executed **once**. Agreed:
collect **two further rounds** (3 total) so leave-one-instance-out becomes possible and the
noise band shrinks to something that can resolve a small effect. **Add `EXF-0003.02` to the
attack list** — it is the only technique that commands the full `to`/`ci` apps, so it is the
only way to test the command-ingress hypothesis borrowed from AINOS3-82, currently our most
promising lead and completely untested. ~2.75 h unattended per round; re-invocation of the
existing tooling, no new code.

### AINOS3-80 / AINOS3-81 follow-on — threshold recalibration (STARTED, and it overturned the plan)

`training/recalibrate_heldout.py` + `training/roc_threshold_sweep.py`. Thresholds re-derived
on **held-out** nominal (soak part A picks, part B measures — part B chose nothing), then
paired with attack detection measured on the `signal-feasibility` corpus corruption windows.

**Result — the "cheap fix" was wrong, twice over.**

1. **Recalibrating every mode to the 1 % design target makes three of four modes worse**
   (PASSIVE 0.05 % → **16.98 %** held-out FP). The 1 % figure was a config default, never an
   operational goal — the system had been beating it by accident of where the in-sample
   thresholds landed.
2. **Pairing with detection inverted the recommendation entirely.** A false-alarm sweep alone
   only ever says which end of the dial is quieter:

   | mode | deployed FP → detection | best alternative |
   |---|---|---|
   | **INERTIAL** | 6.88 % → **12.4 %** | tightening to 0.1 % target gives 0.00 % FP but **0.2 % detection** — a 60× collapse. **Do not tighten.** |
   | **SUNSAFE** | 0.24 % → **52.2 %** | loosening to the 0.5 % target gives 0.83 % FP and **95.0 % detection** — **+43 pts for +0.6 pts**, inside the design target |
   | PASSIVE | 0.05 % → **0.0 %** | loosening to 1 % target gives 0.17 % FP, 20.7 % detection |
   | BDOT | 0.00 % → **0.0 %** | no threshold helps; 296 training rows is the real defect |

**Corrected diagnosis.** The deployed thresholds all sit near **zero** because they are
quantiles of *training* scores. Live, INERTIAL's scores run low and the other three run high,
so a near-zero threshold is arbitrary relative to each mode's real distribution — **too loose
where scores run low, too tight where they run high.** Finding 1 is therefore not "one bad
mode": it is four mis-set thresholds, and the three quiet ones are quiet because they are
**deaf**, which is the worse failure.

**Biggest available win in the sprint:** loosening SUNSAFE — the spacecraft's resident mode,
and where every published catch rate was measured — roughly **doubles detection** within the
existing FP budget.

⚠ **SUNSAFE candidate threshold `+3.89e-02` — WITHDRAWN 2026-08-17. Do not deploy.**

It was pinned on 2026-08-14 with an apparent detection gain of **52.2 % → 90.5 %** for
+0.4 pts of false alarms, chosen by a rule fixed before seeing the curve and backed by a
breadth check (techniques individually ≥ 50 % going 5/13 → 12/13). All of that was
methodologically careful and all of it was measured on the **pre-fix corpus, where 83 % of
attack frames sit inside post-mode-switch blind windows** — so the sweep was largely counting
*transient* frames.

Re-tested on the steady-flight replication (12 SUNSAFE runs, 3 reps per technique):

| technique | det @ deployed | det @ candidate | Δ det | fp @ deployed | fp @ candidate | Δ fp |
|---|--:|--:|--:|--:|--:|--:|
| EX-0012.07 propulsion | 78.5 % | 78.5 % | **+0.0** | 1.00 % | 2.59 % | **+1.59** |
| EX-0012.08 ADCS | 0.0 % | 2.9 % | +2.9 | 0.70 % | 4.53 % | +3.82 |
| EX-0012.09 EPS | 0.0 % | 0.0 % | +0.0 | 0.35 % | 1.73 % | +1.38 |
| EX-0014.04 PNT | 0.0 % | 0.0 % | +0.0 | 0.90 % | 3.59 % | +2.70 |

**Zero detection gain and 2.6× the false alarms.** On the one attack the IF genuinely detects,
detection is identical while false alarms rise from 1.00 % to 2.59 %. The discrete-state-change
attacks are unreachable by *any* threshold — they need a rule, which is what `detect-eps-switch`
covers. The deployed threshold is already at the right operating point for steady flight.

**Method note.** This is the eighth measurement this sprint that could only return one answer.
The ROC sweep had a pre-stated selection rule, a breadth check, and held-out false alarms —
and still rested on a corpus that was 83 % transient. Careful method does not rescue a
confounded dataset. The staged
`data/onair/models/recalibrated_heldout.calibration.json` is retained as evidence, not as a
deployment candidate; `CalibrationPath` stays empty.

**Next steps, in order:**

2. Re-check the candidate operating point at **incident** level, not frame level (the
   operational metric, and more forgiving).
3. **Measure operational FP with a fresh soak** at the candidate threshold. Hysteresis
   suppresses raw FP ~10×, but that ratio depends on whether false positives cluster —
   it must be measured, not extrapolated.
4. Deploy (if it holds) through the AINOS3-37 discipline: one-line ini change, one-line
   rollback, live-verify.
5. **INERTIAL is a training-data problem, not a threshold problem** — 19,641 rows from a
   single 116-minute session. Bolstering it is the real fix.
6. Investigate **PASSIVE's within-hour score drift** (1st-percentile score 0.058 → 0.025
   across one leg), which is why no quantile threshold transfers in that mode. Harmless
   today only because the deployed threshold is conservative.
7. Verify whether the operator view filters `cluster=nominal` incidents — decides whether
   INERTIAL's 71 false incidents/hour are user-visible.
8. **Investigate the published-vs-measured per-technique gap** (caveat 2 above). Either the
   published catch rates or this corpus is unrepresentative; `EX-0014.04` at 98 % vs 7.4 %
   is too large to be variance alone and may indicate the attack script behaves differently
   between collections.

### Per-mode attack pilot (2026-08-15) — ⚠ the catch rates may measure transients

**Collection fix works.** New `single_mode_hold_<MODE>` bracketing scenario (one mode, held
throughout, commanded once — modes are sticky, demonstrated). 16 runs (4 techniques × 4
modes), full stack relaunch per run, 16/16 exit 0, ~2.4 h. Alert-eligible attack frames go
from **16.8 % → 84.4 %**: the blind-window problem is a collection problem and it is fixed.

**But the first honest per-mode numbers are alarming.** Measuring attack detection against
each run's OWN nominal frames (the control that matters — INERTIAL carries a large noise
floor), **lift is zero or negative in 11 of 16 cells**:

| LIFT (attack − nominal) | SUNSAFE | INERTIAL | BDOT | PASSIVE |
|---|--:|--:|--:|--:|
| DE-0003.06 | −1.1 | −18.7 | 0.0 | −0.4 |
| EX-0012.09 | −1.4 | −9.0 | 0.0 | −0.4 |
| EX-0014.03 | −4.6 | +9.8 | 0.0 | −1.0 |
| IMP-0005 | 0.0 | +8.9 | 0.0 | +0.4 |

INERTIAL's apparent 22–64 % "detection" is mostly its own noise floor (nominal 19.6–55.2 %).
In most cells the IF flags *nominal* frames MORE than attack frames.

**Reading, with its limits stated.** With transients excluded, the v5 dynamics IF does not
discriminate these four techniques in any mode. That is consistent with the rest of the
sprint: 83 % of the old corpus sat inside mode-switch transients and 67 % of SUNSAFE
detections sat inside sun-acquisition transients — strip the transients and the signal goes
too. The uncomfortable cell is **EX-0012.09**, dynamics-relevant and published at **99 %**
SUNSAFE, measuring **−1.4** lift in steady SUNSAFE.

⚠ **Do NOT treat this as established.** Four techniques, ONE run per cell. Two of the four
(DE-0003.06, EX-0014.03) have discrete flag/counter footprints and are **rule-gate**
catches — the IF was never the right detector for them, so their null is expected, and
choosing techniques by classifier tier was the wrong axis for an IF-lift question. And
INERTIAL's nominal FP here (19.6–55.2 %) is far above the 7.5 % measured over a 60-min soak,
which says these ~8-min runs are dominated by a settling transient longer than the
250-frame warmup — so the INERTIAL column is untrustworthy in either direction.

**Scope: this does not touch the rule-gate.** R1–R14 are deterministic rules on counters,
flags and state, separately validated and live-verified. The 13 Section-A techniques stand.
This concerns the dynamics IF only.

**Replication needed before any of this is published:** dynamics-relevant techniques only,
much longer pre-holds (especially INERTIAL), several runs per cell, and **lift** as the
metric rather than raw detection. ~1 night of collection. Until then the honest position is
that the headline catch rates *may* reflect manoeuvre transients rather than steady flight,
and we do not yet know.

Artifacts: `scenarios/batch_permode_pilot.json`, `data/onair/models/permode_pilot.json`,
`permode_pilot_control.json`.

### Sun-acquisition false alarms — and a suppression rule that was nearly shipped

The 7 h SUNSAFE soak showed the false alarms are not a steady background at all. **Zero** in
eclipse (50,584 frames) and **zero** in cruise more than 2 min after sun acquisition (75,620
frames); **14.8 %** in the first 2 min after acquisition, and **75.4 %** while the sun is
visible but the fine sun sensor has not yet locked — i.e. while the spacecraft is slewing to
acquire. Just 415 frames, 0.3 % of the soak, account for **52 %** of all false alarms.

A **sun-acquisition suppression window** was proposed on the back of that: a clean
correlation, a tidy physical explanation, and it would have removed essentially every
observed false alarm.

⚠ **It was nearly shipped, and it would have been a disaster.** Checked against the attack
corpus before building it: the naive mask covered 57.5 % of frames and would have cost
**87.7 %** of all detections; scoped correctly to SUNSAFE it still covered 17.3 % of attack
frames and cost **66.8 %** of detections, with seven techniques losing 100 %. The reason is
the inverse of the framing: the window holds 17 % of attack frames but **67 % of all
detections** — the detector does most of its work exactly when there are dynamics to watch.
Those bursts are not noise to remove, they are the cost of the detector working.

**No suppression rule was built.** The right fix is to *train the acquisitions in* — the
model flags them only because the training baselines are too short to contain one — which
removes the false alarms without creating a blind window an attacker could predict from
orbital mechanics. Same root cause as BDOT's 296 training rows.

**Process lesson:** the suppression rule was validated on the data where it looked good
(nominal) and not on the data where it had to be safe (attacks). Every suppression rule needs
an attack-side check before deployment — including the mode-switch warmup that started this
whole thread, which as far as we can tell never had one.

### Replication (2026-08-15) — the pilot alarm was a MEASUREMENT ERROR

24 runs (4 techniques × 2 modes × 3 reps, 600 s pre-hold, lift vs own-run nominal), 24/24
exit 0. **The alarm does not survive.** The system detects 3 of the 4 techniques; the pilot
and the first reading of this replication both measured the **wrong detector**.

| technique | actual mechanism | caught by | verdict |
|---|---|---|---|
| EX-0012.07 propulsion | sustained dynamics | **IF, +77.5 ± 3.6 lift** | ✅ IF is the right detector and works |
| EX-0012.08 ADCS | `ADCS_SET_MODE` — a mode change | **R14** (2/3 reps) | ✅ caught by the rule built this sprint |
| EX-0014.04 PNT | GPS receiver `FC_DISABLE` | **R1** (2/3), R3 (1/3) | ✅ caught |
| EX-0012.09 EPS | `EPS_FC_SWITCH` toggle | **nothing** (0/3) | ❌ **genuine gap** |

**Root cause of the false alarm: technique selection, twice.** Three of the four are
*discrete state changes*, not dynamics attacks — the IF is documented as structurally blind
to those, which is why the gate layer exists. Both experiments measured the IF's silence on
attacks the rule-gate owns and read it as failure. Worse, for EX-0012.08 the analysis
excluded frames within 250 of a mode change — and the attack *is* a mode change, so it was
invalid by construction. **Lesson: read what an attack script commands before deciding which
detector should see it.**

**Two real findings survive:**

1. **EX-0012.09 (EPS switch) is detected by NOTHING in steady flight** — 0/3 reps, no IF
   lift, no rule fired — while published at **99 %** SUNSAFE catch. Genuine coverage gap.
2. **INERTIAL nominal FP is 33.6 %** (range 21.1–48.5 %) at a 600 s hold. This **refutes the
   settling explanation** and supersedes the 0.54 % from AINOS3-81. INERTIAL is unusable for
   detection until understood — higher priority than previously assessed.

Also: the earlier footprint check ("did the attack change anything?") was **worthless** —
nominal-vs-nominal scored 61–68 changed columns against nominal-vs-attack's 61–72. It was
measuring orbital drift. Kept here because it nearly became a sixth false conclusion.

Artifacts: `scenarios/batch_steadyflight_replication.json`,
`data/onair/models/steadyflight_replication.json`.

⚠ **Nothing deployed.** New thresholds are in `data/onair/models/recalibrated_heldout.calibration.json`
and the curve in `roc_threshold_sweep.json`; the live `CalibrationPath` is untouched.

## Capacity note

- **Effort:** committed E = **16** — at the ~16/sprint capacity. Stretch adds **10**.
- **Time:** committed = **~4.75 T** (≈ 38 ideal hours) — inside the ~7–8 T solo capacity,
  leaving room for the signal-feasibility corpus run (~5 h unattended) and the drift soak
  (≥6 h unattended).

The headroom is deliberate: `signal-feasibility` is the highest-uncertainty item (it may
return a NULL) and the rollout is owner-gated, so the sprint front-loads the cheap,
high-certainty hardening (audit + soak + the paper benchmark) and the concrete gap-closer
(mode-transition-rule) while the corpus run overlaps.

## Suggested execution order

1. **Kick off the `signal-feasibility` corpus collection first** so its ~5 h wall-clock
   overlaps everything else. Then **mode-transition-rule** (R14) — a concrete gap that's
   live-verifiable now.
2. **hybrid-drift-soak** on a fresh launch (overlaps the corpus run); while it and the corpus
   accumulate, run the two desk items — **metric-provenance-audit** and **benchmark-fayyaz**
   (they reinforce each other: the paper's data-leakage caveat is a direct external check on
   our OOF discipline).
3. When the corpus lands: the **signal-feasibility** ablation → GO/NO-GO. If GO, ticket the
   retrain and (if signal is broad enough) un-gate **AINOS3-68**.
4. **Stretch** if there's headroom: **cluster-345-regression**, **AINOS3-45** (fold the corpus
   run into a 4th instance), **ci-command-feature**, **AINOS3-68**.
5. **AINOS3-76** stakeholder rollout — schedule the readout early this time so it doesn't
   slip again.
