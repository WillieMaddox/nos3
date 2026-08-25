# Sprint 27 Stakeholder Rollout (AINOS3-76 · EPIC AINOS3-42)

**Component:** `OnAIR-Security` · **Sprint:** 27 · **Prepared:** 2026-08-19 · **Updated:** 2026-08-23 · **Status:** ✅ delivered, signed off in Jira 2026-08-23

Instance of the recurring playbook —
[`STAKEHOLDER_ROLLOUT_TEMPLATE.md`](STAKEHOLDER_ROLLOUT_TEMPLATE.md) holds the flow,
the feedback-capture procedure and the artifact descriptions. This file holds only what
is specific to this readout.

**Artifacts as of 2026-08-22:** `V5_DETECTOR_COVERAGE.md` current to 2026-08-20 (re-derived tiers);
`app/sparta_coverage.html` rebuilt with the Sprint-27 violet markers (EX-0012 ×6,
EX-0014 ×1, DE-0005 ×1).

## ⚠ Read this before presenting

**This readout covers two sprints, not one.** AINOS3-76 (the Sprint-26 readout) slipped
twice and was never delivered, and **Sprint 27 corrected several Sprint-26 numbers
downward.** Presenting the Sprint-26 section alone would state things we now know to be
wrong. Give both sections, in order, and lead with the correction.

⚠ The violet markers on the demo show **Sprint 27 only** — they were not present for the
Sprint-26 items. Say so when you demo the matrix.

The specific claims Sprint 27 overturned:

| Sprint-26 claim | Sprint-27 finding |
|---|---|
| `EX-0012.09` (EPS switch) caught at **99 %** | **0 %** — detected by nothing in steady flight (0/3 reps). Confirmed gap, AINOS3-87 |
| INERTIAL nominal false alarms **0.00 %** | **33.6 %** — mode currently unusable for detection, AINOS3-86 |
| `EX-0012.08`, `EX-0014.04` caught by the anomaly detector | Caught by the **rule layer** (R14, R1); IF lift ≈ 0. Attribution corrected, not detection lost |
| Hybrid classifier gains INERTIAL **+0.058** | Contested — the same routing *costs* 20.9 pts on the `EX-0012.{03,04,05}` cluster (AINOS3-78). Net still positive; the INERTIAL half is what's in question |
| "Next bet: extra MIDs revive the DEAD classes" | **NULL result** (AINOS3-88). More recorded telemetry did **not** improve attack naming |
| One-line briefing summary (15/23 techniques ≥ 50 %) | **Withdrawn 2026-08-14.** Use the replacement in `V5_DETECTOR_COVERAGE.md` § "One-line summary" |
| **4 techniques are ROBUST — "trust the label"** (`DE-0003.01`, `DE-0003.10`, `EX-0008.02`, `IMP-0005`) | **ROBUST is now EMPTY.** None of the four met the rule we published for it ("F1 ≥ 0.85 on every split"); `DE-0003.01` actually scored **0.03**. Tiers re-derived 2026-08-20 and 16 of 24 moved. The classifier itself got **better** — this is a correction to the claim, not a regression |

> **The ROBUST row is the hardest of the seven — prepare for it.** The other six say
> *"we measured something new and it changed."* This one says *"we published a claim our
> own data never supported, for months."* Do not soften it, and expect the follow-up
> question: **"what else is like this?"** The honest answer is that we went looking — the
> AINOS3-80 provenance audit tagged all 18 headline figures, `AINOS3-89` is open precisely
> because per-technique catch rates still disagree with measurement, and the tier column
> is now *derived from an artifact* rather than hand-maintained, so this specific failure
> cannot recur silently. What we cannot claim is that we have found everything.
>
> Have the counterweight ready in the same breath, because it is true and it is buried
> under the correction: **the classifier is materially better than the old tiers implied**
> — macro mean-F1 **0.282 → 0.364**, and folds scoring a flat zero fell from **39/78 to
> 21/78**. Fifteen classes improved. The downgrades are honesty, not decay.

**One inconsistency is visible on screen.** The `EX-0012.09` panel shows the
CONFIRMED-GAP note next to an incident recall of **3/3 (100 %)** — a stale figure from the
pre-correction corpus that has not been re-derived. If someone spots it, the honest answer
is "that number predates the correction and is queued for re-measurement (AINOS3-89)", not
a defence of it.

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
  independent runs** `[live-soak]`. `EX-0012.09` (EPS switch) is caught by **nothing**. Two
  techniques credited to the anomaly detector are actually caught by the rule layer.
- **A blind spot closed (AINOS3-77).** Forcing an ADCS mode change re-arms the detector's
  warmup, so a mode-force attack evaded Stage 1 *by construction*. Rule-gate **R14** now
  flags any confirmed mode transition, plus a **mode-flap** sub-rule for an attacker holding
  the detector off by flipping modes repeatedly. Live-verified: the rule fired and the
  anomaly detector saw nothing — blind spot proven and closed in one test.
  **rule-gate is now R1–R14.**
- **No long-run drift (AINOS3-81).** A 7 h nominal soak found **no degradation** — the
  detector's score margin *widened* `[live-soak]`. The old v2 drift pathology is closed for
  good. The same soak surfaced the INERTIAL false-alarm problem.
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
- **The confidence tiers were re-derived, and the old ones were never supported
  (2026-08-20).** The overlay was still showing v3 classifier artifacts three weeks after
  the hybrid went live. Fixing that exposed something worse than staleness: the four
  techniques published as **ROBUST — "trust the label"** did not meet the rule we
  published for them, and the rules for the other three tiers had never been written down
  anywhere. `DE-0003.01` averaged **F1 0.03** while carrying the "trust the label" badge.
  Tiers are now **derived from LOIO folds by a script**, with the rule stated for all four
  tiers, and the coverage overlay reads that artifact rather than hardcoded strings — so
  the column can no longer drift from the model without anyone noticing. **ROBUST is
  currently empty**; the 0.85 bar was deliberately not lowered to populate it. Same pass
  confirmed the cluster taxonomy is **unchanged** under the hybrid.
- **Two changes were withdrawn before shipping.** A proposed eclipse-window alarm suppression
  would have destroyed **67 % of attack detection** — caught only because the attack-side
  check was run first. A proposed sensitivity change delivered **zero improvement at 2.6× the
  false alarms** once re-tested on corrected data.

## This readout's three techniques (flow step 3)

- **Strong catch:** `EX-0012.07` propulsion — ~80 % of attack frames vs ~1 % nominal,
  replicated three times. Strong on **detection**; be precise that the *label* is not —
  it tiers HIGH-VAR (min F1 0.14 across runs). Its explanation is now a good demo of the
  hybrid regen: the top field moved from a scheduler counter to
  `ADCS_DI.Payload.Imu.wbn`, the angular rate that *is* the propulsion signature.
- **Confirmed gap:** `EX-0012.09` EPS switch — detected by nothing. Use this one; it is
  the clearest demonstration that we publish misses, not just hits.
- **Honest limit:** the `EX-0012.{03,04,05}` sibling cluster — telemetry-identical
  techniques the model is being asked to split (coverage doc §B.1).

## This readout's limits (flow step 4)

Beyond the standing limits in the coverage doc:

- the **~52 s post-mode-switch blind window** — now closed for the mode-force case by R14;
- **INERTIAL's 33.6 % false-alarm rate**, which makes that mode presently unusable for
  detection;
- **no technique's label is reliable on every run** — the ROBUST tier is empty. Six are
  usable on every run as a strong suggestion (`EX-0008.01/.02`, `IMP-0002/0005/0006`,
  `DE-0003.10`); three cannot be labeled at all. Detection is the strong half of this
  system, naming is the weak half, and the tier table now says so honestly.

## This readout's ask (flow step 5)

The signal lever (AINOS3-88) returned a NULL, so the open backlog is now:

| Jira | Item | Why it may go first |
|---|---|---|
| AINOS3-86 | INERTIAL false alarms (33.6 %) | **High** — likely blocks several other measurements |
| AINOS3-87 | EX-0012.09 EPS gap | the only technique detected by nothing |
| AINOS3-89 | catch-rate provenance disagreement | until explained, no per-technique number can be quoted confidently |
| AINOS3-78 | hybrid routing fix (SUNSAFE only) | recovers the cluster loss for −0.23 pts overall |

**AINOS3-68** (DeepSAD) stays gated — the gate was not cleared. Ask which of these matter
most, and whether more independent collection runs are worth the wall-clock.

## Feedback capture

Procedure — the three steps, the `#` and `Type` conventions, and the worked examples — lives in [`STAKEHOLDER_ROLLOUT_TEMPLATE.md`](STAKEHOLDER_ROLLOUT_TEMPLATE.md).
Capture here:

| Jira | Slug | # | Stakeholder | Feedback / question | Type |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

## Ideas for next sprint. (Questions to be answered, things to do, bugs to fix, etc.)

### I am not sure which of these need their own ticket, can be grouped into a single ticket, or don't require a ticket at all (e.g. memory update, housekeeping task, etc.)

The main feedback I get from stakeholders is,
1. "Less red and yellow, more green"
2. "Less HIGH-VAR and DEAD, more ROBUST". 
We had ROBUST classifications before. What will it take to make them (and possibly other sub-techniques) yet ROBUST again? This is a high level goal that we should be improving consistently or always be striving for at least. If that means we go back to the drawing board on something in order to do it right, I'm all for it. Better to have a brief setback and get on the right path than to keep on a path going nowhere.

---

With regard to the sparta coverage sub-technique tables:
1. Which of the columns are IF related and which are classifier related?
2. Why does DE-0003.08 show its verdict as not detected and have HIGH-VAR, while DE-0003.09 has a partial verdict but DEAD?
3. The "Classifier Tier" column is missing a summary description in the footer below the table.
Update in `V5_DETECTOR_COVERAGE.md` and `sparta_coverage.html`.

---

I spent a few hours researching the Sparta website and found some very interesting information I think will be very useful in helping to achieving our goals.
Probably the most interesting page and the one most relevant to our work is the Sparta Indicators of Behavior page, https://sparta.aerospace.org/related-work/iob.
A complete understanding of these IOBs, I believe, will make problem solving, debugging and data analysis that much easier across almost every task associated with this project. Two topics on this page I find most interesting:
1. Best practice guidelines for spacecraft subsystem logging to SPARTA techniques. Links are provided to a pdf of the guide as well as a detailed and comprehensive spreadsheet. I've already taken the liberty of downloading them for you. See the `data/sparta/` directory. Both files may help us improve significantly the quality of our log data. For example, our logging methods have gone through a number of changes and as a result left us with a mix of inconsistent log data. Or the spreadsheet may provide critically helpful telemetry currently unknown to us. The list goes on and on. Be sure to understand the details of every sheet contained in the file (~20 sheets).
2. STIX patterns, how they relate to the Indicators of Behavior and how to use them. According to the SPARTA user guide, https://sparta.aerospace.org/resources/user-guide:
>Structured Threat Information Expression (STIX™) is a language and serialization format used to exchange cyber threat intelligence (CTI). The SPARTA dataset is available in STIX 2.1.
>STIX is a machine-readable format providing access to the SPARTA knowledge base. It is the most granular representation of the SPARTA data, and all other representations are derived from the STIX dataset.
>The SPARTA STIX representation is most easily manipulated in Python using the stix2 library https://github.com/oasis-open/cti-python-stix2#installation. 
>However, because STIX is represented in JSON, other programming languages can easily interact with the raw content.
>To download SPARTA you may either make a call to the API directly, or utilize the dropdown menu as described on the website https://sparta.aerospace.org/resources/working-with.

We may be able to use STIX to verify the correctness of and/or fix current attacks, generate new attacks, or gain deeper understanding about the whole attack/anomaly design space.
Needless to say, consume and understand this page, specifically Logging and STIX as mentioned above. Moving forward, routinely check if any of its contents can help solve or make better new or existing items. Treat it as a reference source. 

---

Clean up the log data.  In a recent comment, you said, "...scored on the frozen corpus collected before we found the collection defect." I know you don't like deleting data, but more data isn't always better especially when it contains incorrect or dirty data. At the very least, move the data to a "stale" folder if you're not ready to delete it just yet.

## Status

- [x] Doc ready (`V5_DETECTOR_COVERAGE.md`, current to 2026-08-19).
- [x] Demo ready (`sparta_coverage.html` rebuilt 2026-08-19 with Sprint-27 markers).
- [x] Sprint-27 corrections folded in — this readout covers Sprints 26 **and** 27.
- [x] Pre-flight click-through — one known stale figure (`EX-0012.09` 3/3); check the rest.
- [x] **Presentation delivered** — owner action. Slipped from Sprint 26 and Sprint 27; it is the only open item in Sprint 27.
- [x] **Feedback captured** — table above worked through Step 3.
