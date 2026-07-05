# NOS3 OnAIR Security Monitor — Stakeholder Rollout (NOS3-322)

A presenter's guide for walking stakeholders through **what the detector catches
/ what it doesn't**, demoing the live coverage overlay, and capturing feedback as
backlog tickets. The two artifacts to present are already prepared:

- **The doc:** `components/onair/V5_DETECTOR_COVERAGE.md` — the honest
  "catches / doesn't" reference (per-mode FP, SUNSAFE detection list, classifier
  tiers, the two DEAD-class failure modes, drift result, blind-window limit).
- **The demo:** `app/sparta-standalone 1.html` — open in any browser (offline,
  `file://` friendly). The NOS3 overlay badges each SPARTA technique with real
  detection status and, in the coverage panel, a **"Top fields (why)"** column
  (the SHAP-derived telemetry drivers, NOS3-311/312). Rebuilt 2026-07-05 so it
  reflects the current model + explanations.
  > The HTML is a **local build artifact** (git-ignored; regenerated from the
  > tracked `nos3_coverage.js` + `nos3_overlay.js`). If it's missing or stale,
  > rebuild: `python3 app/gen_nos3_coverage.py && python3 app/build_overlay.py`.

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
     (NOS3-306); the attack-specific field is within the top-N.
4. **The honest limits** (coverage doc "What it does NOT catch", A–F): SUNSAFE-
   tied detection, unlabelable classes, unobservable attacks, out-of-fold label
   accuracy, and the ~52 s post-mode-switch blind window (NOS3-303, just reduced
   from ~124 s).
5. **Next bets** — the open backlog (NOS3-305 hybrid, NOS3-321 extra MIDs to
   revive DEAD classes, NOS3-330 next-ML spike) — and ask which matter most.

## Feedback capture (→ turn each into a ticket)

| # | Stakeholder | Feedback / question | Type (gap · feature · doc · priority) | → Candidate ticket |
|---|-------------|---------------------|---------------------------------------|--------------------|
|   |             |                     |                                       |                    |

After the session, file the captured rows as backlog tickets (mirror the
`SPRINT_3_PLAN.md` format: Summary + Description + Type) and link them back here.

## Status

- [x] Doc ready (`V5_DETECTOR_COVERAGE.md`, current).
- [x] Demo ready + current (`sparta-standalone 1.html` rebuilt with explanations).
- [ ] **Presentation delivered** — owner action (cannot be automated).
- [ ] **Feedback captured as tickets** — fill the table above during/after.
