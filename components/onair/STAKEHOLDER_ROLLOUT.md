# NOS3 OnAIR Security Monitor — Stakeholder Rollout (EPIC AINOS3-42)

> **Recurring playbook** for the AINOS3-42 "Stakeholder rollout & feedback" epic —
> reuse this each rollout (once per sprint, or every other). AINOS3-43 is the first
> instance (Sprint 3); file each subsequent readout as a fresh child ticket.

A presenter's guide for walking stakeholders through **what the detector catches
/ what it doesn't**, demoing the live coverage overlay, and capturing feedback as
backlog tickets. The two artifacts to present are already prepared:

- **The doc:** `components/onair/V5_DETECTOR_COVERAGE.md` — the honest
  "catches / doesn't" reference (per-mode FP, SUNSAFE detection list, classifier
  tiers, the two DEAD-class failure modes, drift result, blind-window limit).
- **The demo:** `app/sparta_coverage.html` — open in any browser (offline,
  `file://` friendly). The NOS3 overlay badges each SPARTA technique with real
  detection status and, in the coverage panel, a **"Top fields (why)"** column
  (the SHAP-derived telemetry drivers, AINOS3-38/AINOS3-40). Rebuilt 2026-07-29 so it
  reflects the Sprint-26 Section-B detections + the resolved coverage verdicts.
  > The HTML is a **local build artifact** (git-ignored; regenerated from the
  > tracked `nos3_coverage.js` + `nos3_overlay.js`). If it's missing or stale,
  > rebuild: `python3 app/gen_nos3_coverage.py && python3 app/build_overlay.py`.

## What changed since Sprint 25 (Sprint-26 readout)

Sprint 26 turned the newly-*recorded* Section-B MIDs into **validated detections** and
closed out the last unresolved coverage verdicts. The per-leaf SPARTA split moved to
**42 detected · 26 out-of-scope · 0 not-evaluated · 109 not-applicable = 177** — every
applicable leaf now carries a verdict.

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
  (frozen `csv_corpus_v3stage`, max_iter=300) shows the hybrid banks the dynamic-mode
  gains with **zero** quiescent-mode regression: INERTIAL **+0.058**, SUNSAFE **+0.061**,
  ROBUST **+0.099**, BDOT/PASSIVE **+0.000** (identical to v3 by construction — those modes
  keep the global head), overall **0.646 vs 0.627**. **Cut over live and verified 2026-07-30**
  (OnAIR loads the hybrid; SUNSAFE frames route through the SUNSAFE per-mode head → IMP-0005,
  INERTIAL → EX-0014.04; survives a fresh launch; one-line ini rollback).
- **Coverage-overlay honesty fix:** the overlay's incident-label number was in-sample
  (76.9 %, ~2× optimistic per NOS3-302). Re-scored **out-of-fold for the deployed hybrid**:
  **42.3 %** label accuracy of detected attacks (vs the v3 global head's 34.6 % OOF, +7.7 pts).
  Detection recall is unchanged (67.8 %, 78/115 — IF-driven, not classifier-driven). ⚠ when
  presenting: the displayed label number went **down** (76.9 → 42.3) only because the
  methodology was corrected to honest OOF — 42.3 % honest beats the old 76.9 % fiction *and*
  beats honest v3.

## Suggested 5-minute flow

1. **Bottom line first** (coverage doc "Bottom line"): a two-stage detector —
   v5 per-mode IsolationForest (detection) + v3 classifier (labeling) + incident
   aggregation (one alert per attack, with a reason).
2. **Demo the matrix** — open the SPARTA HTML, show the coverage overlay: green
   = caught, and the per-technique panel with status, classifier tier, signal
   class, and the top telemetry fields that drove it.
3. **Walk three contrasting techniques:**
   - a **strong catch** (e.g. `IMP-0005` → THRUSTER.CommandCount) — detected +
     labeled + explained;
   - a **DEAD / unlabelable** class — to show the honest limit (sibling-ambiguous
     vs nominal-ambiguous, coverage doc §B);
   - an **explanation caveat** — generic activity counters can top the list
     (AINOS3-39); the attack-specific field is within the top-N.
4. **The honest limits** (coverage doc "What it does NOT catch", A–F): SUNSAFE-
   tied detection, unlabelable classes, unobservable attacks, out-of-fold label
   accuracy, and the ~52 s post-mode-switch blind window (AINOS3-35, just reduced
   from ~124 s).
5. **Next bets** — the open backlog (AINOS3-30 extra MIDs to revive DEAD classes,
   AINOS3-68 DeepSAD revisit — gate still uncleared, next-ml-bet next-ML spike) — and
   ask which matter most. (AINOS3-37 hybrid is now live-deployed, so the classification-
   trust epic is closed; the standing signal-adding work is the remaining lever.)

## Feedback capture (→ turn each into a ticket)

| # | Stakeholder | Feedback / question | Type (gap · feature · doc · priority) | → Candidate ticket |
|---|-------------|---------------------|---------------------------------------|--------------------|
|   |             |                     |                                       |                    |

After the session, file the captured rows as backlog tickets (mirror the
`SPRINT_24_PLAN.md` format: Summary + Description + Type) and link them back here.

## Status

- [x] Doc ready (`V5_DETECTOR_COVERAGE.md`, current).
- [x] Demo ready + current (`sparta_coverage.html` rebuilt with explanations).
- [ ] **Presentation delivered** — owner action (cannot be automated).
- [ ] **Feedback captured as tickets** — fill the table above during/after.
