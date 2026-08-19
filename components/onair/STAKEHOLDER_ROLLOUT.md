# NOS3 OnAIR Security Monitor — Stakeholder Rollout (EPIC AINOS3-42)

> **Recurring playbook** for the AINOS3-42 "Stakeholder rollout & feedback" epic —
> reuse this each rollout (once per sprint, or every other). AINOS3-43 is the first
> instance (Sprint 3); file each subsequent readout as a fresh child ticket.

A presenter's guide for walking stakeholders through **what the detector catches
/ what it doesn't**, demoing the live coverage overlay, and capturing feedback as
backlog tickets. The two artifacts to present are already prepared:

- **The doc:** `components/onair/V5_DETECTOR_COVERAGE.md` — the honest
  "catches / doesn't" reference (per-mode FP, detection list, classifier tiers,
  the two DEAD-class failure modes, drift result, blind-window limit).
- **The demo:** `app/sparta_coverage.html` — open in any browser (offline,
  `file://` friendly). The NOS3 overlay badges each SPARTA technique with real
  detection status and, in the coverage panel, a **"Top fields (why)"** column
  (the SHAP-derived telemetry drivers, AINOS3-38/AINOS3-40). Techniques whose
  assessment changed in the current sprint carry a **violet dot + left bar**; hover
  the dot for what changed. Rebuilt 2026-08-19 for the Sprint-27 corrections.
  > The HTML is a **version-controlled deliverable**, not a build artifact — the file is
  > hand-authored and only the inlined NOS3 overlay block inside it is generated. After
  > changing coverage data, rebuild and commit it:
  > `python3 app/gen_nos3_coverage.py && python3 app/build_overlay.py`.

## ⚠ Read this before presenting

**This readout covers two sprints, not one.** AINOS3-76 (the Sprint-26 readout) slipped
twice and was never delivered, and **Sprint 27 corrected several Sprint-26 numbers
downward.** Presenting the Sprint-26 section alone would state things we now know to be
wrong. Give both sections, in order, and lead with the correction — the story is *"we
audited our own results and several did not survive"*, which is a stronger position than
pretending the first set held.

The specific claims Sprint 27 overturned:

| Sprint-26 claim | Sprint-27 finding |
|---|---|
| `EX-0012.09` (EPS switch) caught at **99 %** | **0 %** — detected by nothing in steady flight (0/3 reps). Confirmed gap, AINOS3-87 |
| INERTIAL nominal false alarms **0.00 %** | **33.6 %** — mode currently unusable for detection, AINOS3-86 |
| `EX-0012.08`, `EX-0014.04` caught by the anomaly detector | Caught by the **rule layer** (R14, R1); IF lift ≈ 0. Attribution corrected, not detection lost |
| Hybrid classifier gains INERTIAL **+0.058** | Contested — the same routing *costs* 20.9 pts on the `EX-0012.{03,04,05}` cluster (AINOS3-78). Net still positive; the INERTIAL half is what's in question |
| "Next bet: extra MIDs revive the DEAD classes" | **NULL result** (AINOS3-88). More recorded telemetry did **not** improve attack naming |
| One-line briefing summary (15/23 techniques ≥ 50 %) | **Withdrawn 2026-08-14.** Use the replacement in `V5_DETECTOR_COVERAGE.md` § "One-line summary" |

**One inconsistency is visible on screen.** The `EX-0012.09` panel shows the CONFIRMED-GAP
note next to an incident recall of **3/3 (100 %)** — a stale figure from the pre-correction
corpus that has not been re-derived. If someone spots it, the honest answer is "that number
predates the correction and is queued for re-measurement (AINOS3-89)", not a defence of it.

## What changed in Sprint 26 (never presented)

Sprint 26 turned the newly-*recorded* Section-B MIDs into **validated detections** and
closed out the last unresolved coverage verdicts. The per-leaf SPARTA split moved to
**42 detected · 26 out-of-scope · 0 not-evaluated · 109 not-applicable = 177** — every
applicable leaf carries a verdict.

- **5 new Section-B detections** (all live-validated, folded into the overlay):
  - **EX-0010.01 / EX-0010.02** ransomware / wiper → rule-gate **R11** (`FM.CommandCounter`
    file-op burst).
  - **EXF-0003.02** downlink exfiltration → rule-gate **R12** (`TO.usCmdCnt`) + **R13**
    (downlink route-mask change); R13 also sharpens **IMP-0006** theft.
  - **DE-0001** disable fault management → already caught by **R5** (LC state → DISABLED;
    shared footprint with EX-0011/DE-0005).
  - **DE-0006** modify whitelist → **R8 + R9** (CFE_ES/CFE_TBL command activity).
- **3 coverage verdicts resolved** (no detector, but the honest answer):
  - **EX-0012.11 / DE-0003.11** watchdog → **out-of-scope**: no telemeterable WDT/health
    packet exists in this build (PSP watchdog is a no-op stub; no HS app).
  - **EX-0001.02** bus-traffic replay → **out-of-scope**: internal SBN bus has no external
    injection path.
  - **EX-0005.01** firmware design flaws → **not-applicable**: NOS3 models functional
    behaviour, not the firmware/FPGA layer.
- **rule-gate grew R1–R10 → R1–R13.**
- **Classifier trust (epic closed):** the AINOS3-39 counter-reliance audit (keep v3) and
  the AINOS3-37 **selective per-mode hybrid** close the classification-trust epic. LOIO
  shows overall **0.646 vs 0.627** with zero BDOT/PASSIVE regression (those modes keep the
  global head, identical by construction). ⚠ see the correction table — the INERTIAL
  component of that gain is now contested.
- **Coverage-overlay honesty fix:** the overlay's incident-label number was in-sample
  (76.9 %, ~2× optimistic per NOS3-302). Re-scored **out-of-fold for the deployed hybrid**:
  **42.3 %** label accuracy of detected attacks (vs the v3 global head's 34.6 % OOF). ⚠ when
  presenting: the displayed number went **down** (76.9 → 42.3) only because the methodology
  was corrected — 42.3 % honest beats the old 76.9 % fiction *and* beats honest v3.

## What changed in Sprint 27

Sprint 27's planned headline — *would more recorded telemetry improve attack naming?* —
returned a **documented NULL**. The value came from the other half of the sprint: auditing
our own measurements. Several did not survive.

- **The signal bet failed, and failed informatively (AINOS3-88).** A 17-attack, 359-column
  corpus plus a 7-arm ablation found **no block of added telemetry beats split noise**. One
  arm looked promising until the data was sliced differently, at which point the gain
  **flipped to a loss**. The conclusion is not "the model is too weak" — it is that we have
  **too few independent runs to measure a small effect**. Corpus size, not feature design,
  is the binding constraint.
- **A collection defect invalidated much of the attack corpus.** The detector goes quiet for
  ~45 s after each mode switch; our collection scenario switched modes every 60 s. **83 % of
  attack frames sat inside the detector's own blind window.** The reason we cycled modes so
  fast was a belief the spacecraft wouldn't hold a mode — tested and **false** (17,670
  readings, zero drift over an hour). Fixing collection took usable data from **17 % → 84 %**.
- **Honest re-measurement, mixed results.** With the corrected method: `EX-0012.07`
  (propulsion) is caught superbly — **~80 % of attack frames vs ~1 % nominal, three
  independent runs**. `EX-0012.09` (EPS switch) is caught by **nothing**. Two techniques
  credited to the anomaly detector are actually caught by the rule layer.
- **A blind spot closed (AINOS3-77).** Forcing an ADCS mode change re-arms the detector's
  warmup, so a mode-force attack evaded Stage 1 *by construction*. Rule-gate **R14** now
  flags any confirmed mode transition, plus a **mode-flap** sub-rule for an attacker holding
  the detector off by flipping modes repeatedly. Live-verified: the rule fired and the
  anomaly detector saw nothing — blind spot proven and closed in one test.
  **rule-gate is now R1–R14.**
- **No long-run drift (AINOS3-81).** A 7 h nominal soak found **no degradation** — the
  detector's score margin *widened*. The old v2 drift pathology is closed for good. The same
  soak surfaced the INERTIAL false-alarm problem.
- **Provenance is now enforced (AINOS3-80).** All 18 headline figures were traced to source
  and tagged (`[OOF]` / `[live-soak]` / `[in-sample]` / `[design-target]` / `[unverifiable]`).
  An untagged number is now a bug. Two material findings: the alarm threshold was calibrated
  **in-sample** while the doc claimed held-out, and the detector's **training corpus was
  never recorded**, leaving four published claims unverifiable by anyone including us.
- **The published competition doesn't survive scrutiny (AINOS3-82).** A university group
  reports near-perfect results on the same simulator. Their dataset records each attack type
  in **one sitting**, so a model can identify the *recording session* instead of the attack —
  demonstrated three ways (the clock alone gets 88 %; memory usage alone 100 %). Our lower
  numbers reflect a harder problem measured more strictly.
- **Two changes were withdrawn before shipping.** A proposed eclipse-window alarm suppression
  would have destroyed **67 % of attack detection** — caught only because the attack-side
  check was run first. A proposed sensitivity change delivered **zero improvement at 2.6× the
  false alarms** once re-tested on corrected data.

## Suggested 5-minute flow

1. **Bottom line first** (coverage doc "Bottom line"): a two-stage detector —
   per-mode IsolationForest (detection) + hybrid classifier (labeling) + incident
   aggregation (one alert per attack, with a reason) — **plus a parallel rule layer**
   (R1–R14, consistency-check, staleness-check) that catches the 13 validated
   Section-A techniques the dynamics model is structurally blind to.
2. **Demo the matrix** — open the SPARTA HTML, show the coverage overlay: green
   = caught, the per-technique panel with status, classifier tier, signal class and
   top telemetry fields, and the **violet markers** showing what changed this sprint.
3. **Walk three contrasting techniques:**
   - a **strong catch** (`EX-0012.07` propulsion — ~80 % of attack frames vs ~1 %
     nominal, replicated three times) — detected + labeled + explained;
   - a **confirmed gap** (`EX-0012.09` EPS switch — detected by nothing) — to show
     we publish the misses, not just the hits;
   - a **DEAD / unlabelable** class — the honest limit (sibling-ambiguous vs
     nominal-ambiguous, coverage doc §B).
4. **The honest limits** (coverage doc "What it does NOT catch", A–F): the classifier
   cannot detect what Stage 1 missed, unlabelable classes, unobservable attacks,
   out-of-fold label accuracy, the **~52 s post-mode-switch blind window** — now closed
   for the mode-force case by R14 — and **INERTIAL's 33.6 % false-alarm rate**, which
   makes that mode presently unusable for detection.
5. **Next bets** — and this is where the ask is. The signal lever (AINOS3-88) returned a
   NULL, so the open backlog is now: **AINOS3-86** INERTIAL false alarms (High — likely
   blocks several other measurements), **AINOS3-87** the EPS gap, **AINOS3-89** the
   catch-rate provenance disagreement, and the AINOS3-78 hybrid-routing fix. **AINOS3-68**
   (DeepSAD) stays gated — the gate was not cleared. Ask which of these matter most to
   them, and whether more independent collection runs are worth the wall-clock.

## Feedback capture (→ turn each into a ticket)

| # | Stakeholder | Feedback / question | Type (gap · feature · doc · priority) | → Candidate ticket |
|---|-------------|---------------------|---------------------------------------|--------------------|
|   |             |                     |                                       |                    |

After the session, file the captured rows as backlog tickets (Summary + Description + Type,
per the crosswalk rule), add each to `JIRA_CROSSWALK.md`, and link them back here.

## Status

- [x] Doc ready (`V5_DETECTOR_COVERAGE.md`, current to 2026-08-19).
- [x] Demo ready + current (`sparta_coverage.html` rebuilt 2026-08-19 with the
      Sprint-27 violet markers).
- [x] Sprint-27 corrections folded in — the readout now covers Sprints 26 **and** 27.
- [ ] **Presentation delivered** — owner action (cannot be automated). Slipped from
      Sprint 26 and Sprint 27; it is the only open item in Sprint 27.
- [ ] **Feedback captured as tickets** — fill the table above during/after.
