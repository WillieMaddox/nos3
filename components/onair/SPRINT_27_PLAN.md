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
keys are now assigned (`AINOS3-77`–`AINOS3-85`). Carryover keys (`AINOS3-30`, `AINOS3-45`,
`AINOS3-68`, `AINOS3-76`) are immutable.

| Jira | Slug | Type | Pri | E | T | Summary |
|---|---|---|---|--:|--:|---|
| AINOS3-41 | coverage-expansion | Epic | — | — | — | Detection coverage expansion (signal lever) |
| AINOS3-30 | extra-mids | Story | High | 5 | 1.5 | ○ COMMIT — signal-feasibility slice: collect a 382-col weak-class corpus + ablate whether any recorded Section-B MID adds discrimination → GO/NO-GO on a retrain |
| AINOS3-77 | mode-transition-rule | Task | High | 3 | 1.0 | ○ COMMIT — R14: flag ADCS mode-force (SET_MODE) — the live-observed IF warmup blind spot (DE-0005) |
| AINOS3-78 | cluster-345-regression | Spike | Medium | 2 | 0.5 | ○ STRETCH — why the hybrid regressed `EX-0012.{03,04,05}` (label_ok −3); recover or accept |
| AINOS3-45 | corpus-instance-4 | Task | Medium | 3 | 0.75 | ○ STRETCH — 4th corpus instance, collected at the 382-col schema (feeds signal-feasibility) |
| AINOS3-68 | deepsad-revisit | Spike | Low | 3 | 0.75 | ○ STRETCH — reopen Phase-5 DeepSAD **only if** signal-feasibility clears the gate |
| AINOS3-83 | ci-command-feature | Task | Low | 2 | 0.5 | ○ STRETCH — turn the full-`ci` HK (0x0884, now on-pipe) into a command-ingest detector |
| AINOS3-79 | detector-rigor | Epic | — | — | — | Detector hardening & measurement honesty |
| AINOS3-80 | metric-provenance-audit | Spike | Medium | 2 | 0.5 | ○ COMMIT — sweep reported metrics for in-sample optimism (the 76.9→42.3 lesson) |
| AINOS3-81 | hybrid-drift-soak | Task | Medium | 1 | 0.25 | ○ COMMIT — long soak: live hybrid + per-mode calibration hold, 0-FP, no drift |
| AINOS3-82 | benchmark-fayyaz | Spike | Medium | 3 | 1.0 | ○ COMMIT — scan the Fayyaz CuCD-ID NOS3 dataset paper + compare method/results with ours |
| AINOS3-42 | stakeholder-rollout | Epic | — | — | — | Stakeholder rollout & feedback (recurring) |
| AINOS3-76 | rollout-s26 | Task | Medium | 2 | 0.5 | ○ COMMIT — carryover: present the Sprint-26 readout + capture feedback (owner-action, slipped last sprint) |

**Committed set:** E = **16** (signal-feasibility 5 · mode-transition-rule 3 ·
metric-provenance-audit 2 · hybrid-drift-soak 1 · benchmark-fayyaz 3 · AINOS3-76 2) ·
T ≈ **4.75** — right at the ~16 E / ~7–8 T capacity, leaving headroom for the
signal-feasibility corpus run's unattended wall-clock.

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

### AINOS3-30 — Signal-adding feasibility (recorded MIDs → weak-class discrimination) · `Story` · High · E 5 · T 1.5 (~12h) · ○ COMMIT

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

### AINOS3-77 — Flag ADCS mode-force (R14) · `Task` · High · E 3 · T 1.0 (~8h) · ○ COMMIT

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

### AINOS3-82 — Compare against the Fayyaz CuCD-ID NOS3 dataset · `Spike` · Medium · E 3 · T 1.0 (~8h) · ○ COMMIT

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

---

## 🟪 EPIC AINOS3-42 — Stakeholder rollout & feedback (recurring)

### AINOS3-76 — Stakeholder rollout (carryover) · `Task` · Medium · E 2 · T 0.5 (~4h) · ○ COMMIT

**Summary:** Present the Sprint-26 result — Section-B detections, the live hybrid, and the
honest-OOF overlay correction — and capture feedback as backlog.

**Description:** Carryover: the Sprint-26 prep is done (overlay + docs refreshed, live
hybrid) but the **presentation slipped** (owner-action, not completed). Re-attempt this
sprint. Lead with the honesty story — detection is strong and unchanged, labeling improved
(+7.7 pts) *and* the overlay stopped overstating it — since that reframes the lower
displayed number correctly. Capture feedback in the `STAKEHOLDER_ROLLOUT.md` table, file as
tickets.

**Acceptance Criteria:**

- Doc + overview presented — **owner action** (cannot be automated); the "What changed
  since Sprint 25" section + the coverage-overlay honesty-fix bullet are the script.
- Feedback captured in the `STAKEHOLDER_ROLLOUT.md` table, then filed as backlog tickets.

---

## 📋 Backlog (carryover / not sprinted)

| Jira | Slug | Type | E | T | Summary |
|---|---|---|--:|--:|---|
| AINOS3-44 | tcn-feature | Story | 5 | 1.5 | TCN reconstruction-error feature, scoped to EX-0008 ATS/RTS |
| AINOS3-46 | demo-tier-bc | Story | 3 | 1.0 | Demo app Tier B/C — the live "detector in action" demo |
| AINOS3-47 | foundation-baseline | Story | 8 | 2.5 | Foundation-model (MOMENT/THEMIS) zero-shot baseline |
| AINOS3-84 | drop-bus-activity-retrain | Task | 3 | 0.75 | AINOS3-39 follow-up: retrain dropping the harmful pure bus-activity features (`CFE_SB.MemInUse`, global EVS rate) — small PNT/theft/denial upside |
| AINOS3-85 | actuator-saturation-fidelity | Spike | 2 | 0.5 | The EX-0005.02 RW-torque path didn't build a real body tumble; find an injection that reaches actuator saturation (tests the within-mode-recovery vs no-FDIR boundary) |

`AINOS3-68` (DeepSAD) stays **gated** — reopen only if `signal-feasibility` (AINOS3-30)
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
regression elsewhere before any deploy. Best folded into the AINOS3-30 retrain if that clears,
to avoid a redundant retrain/deploy cycle.

**Acceptance Criteria:**

- The harmful pure bus-activity features (per AINOS3-39) removed; classifier retrained on the
  frozen corpus.
- LOIO shows the PNT/theft/denial gain retained with no regression on other clusters or modes.
- Deploy only through the AINOS3-37 live-verify + one-line-rollback discipline; ini + build
  tree synced.

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
