# Stakeholder Rollout — TEMPLATE (EPIC AINOS3-42)

> **This file is the recurring playbook. Do not fill it in.** Copy it to
> `SPRINT_<N>_STAKEHOLDER_ROLLOUT.md` at the start of each rollout, then edit the copy.
> Everything here is sprint-independent; anything you find yourself dating or naming a
> technique in belongs in the copy, not here.
>
> AINOS3-42 is the standing epic; AINOS3-43 was the first instance (Sprint 3). File each
> readout as a fresh child ticket and record its key in `JIRA_CROSSWALK.md`.

**How to use this template**

1. `cp STAKEHOLDER_ROLLOUT_TEMPLATE.md SPRINT_<N>_STAKEHOLDER_ROLLOUT.md`
2. Fill the `<<...>>` placeholders. Delete any section that genuinely does not apply —
   an empty section reads as "we had nothing", which is rarely true and never useful.
3. Rebuild the demo so the violet markers match the sprint being presented:
   `python3 app/gen_nos3_coverage.py && python3 app/build_overlay.py`
4. After the session, work the feedback table through its three steps (below).

---

## The two artifacts

These are prepared ahead of every rollout and are the same two each time:

- **The doc:** `components/onair/V5_DETECTOR_COVERAGE.md` — the honest "catches /
  doesn't" reference (per-mode false-alarm rates, detection list, classifier tiers, the
  two DEAD-class failure modes, drift result, blind-window limit). Check its
  **"Last updated"** header actually names the sprint you are presenting.
- **The demo:** `app/sparta_coverage.html` — open in any browser (offline, `file://`
  friendly). The NOS3 overlay badges each SPARTA technique with real detection status
  and, in the coverage panel, a **"Top fields (why)"** column (the SHAP-derived telemetry
  drivers, AINOS3-38/AINOS3-40). Techniques whose assessment changed in the current
  sprint carry a **violet dot + left bar**; hover the dot for what changed.
  > The HTML is a **version-controlled deliverable**, not a build artifact — the file is
  > hand-authored and only the inlined NOS3 overlay block inside it is generated. After
  > changing coverage data, rebuild and commit it.

> ⚠ **The violet markers are scoped to one sprint.** They are cleared at sprint kickoff,
> so they show what changed *in the sprint being presented* — not everything that ever
> changed. If a rollout covers more than one sprint, say so out loud, because the markers
> will only reflect the most recent one.

## ⚠ Read this before presenting

*Keep this section only if it applies. It applies whenever a previous readout slipped, or
where this sprint's work contradicts something already told to stakeholders.*

**Did any previously-presented number change?** If yes, lead with that, do not bury it.
Presenting a superseded figure and being corrected in the room costs more credibility than
the correction itself ever does. The honest framing — *"we audited our own results and
several did not survive"* — is a stronger position than the alternative, and it is the one
thing in the readout that cannot be reconstructed later if you skip it.

| Previously presented | Current finding |
|---|---|
| `<<claim as stakeholders last heard it>>` | `<<what it is now, and the owning ticket>>` |

**Is anything on screen going to contradict what you are saying?** Generated panels can
retain stale figures from an earlier corpus. Find these *before* the session by clicking
through the techniques you plan to show. For each one, note the honest answer — *"that
number predates the correction and is queued for re-measurement under `<<key>>`"* — rather
than discovering it live.

## What changed in Sprint `<<N>>`

*The substance of the readout. Group by what the audience cares about, not by ticket
order. For each item: what changed, what it means operationally, and the evidence class
(`[OOF]` / `[live-soak]` / `[in-sample]` / `[design-target]` / `[unverifiable]` — the
AINOS3-80 provenance convention). Null and negative results belong here too; a documented
NULL that redirects the roadmap is a result, not an absence of one.*

- `<<new detections / closed blind spots — what an attacker can no longer do unseen>>`
- `<<corrected or withdrawn measurements — say plainly which direction they moved>>`
- `<<coverage verdicts resolved (out-of-scope / not-applicable count as answers)>>`
- `<<what was tried and did not work, and what that rules out>>`

## Suggested 5-minute flow

1. **Bottom line first** (coverage doc "Bottom line"): the two-stage detector —
   per-mode IsolationForest (detection) + classifier (labeling) + incident aggregation
   (one alert per attack, with a reason) — **plus the parallel rule layer** that catches
   the validated Section-A techniques the dynamics model is structurally blind to.
2. **Demo the matrix** — open the SPARTA HTML, show the overlay: per-technique status,
   classifier tier, signal class, top telemetry fields, and the **violet markers** for
   what changed this sprint.
3. **Walk three contrasting techniques.** Always three, always contrasting — one alone
   reads as cherry-picking:
   - a **strong catch** — `<<technique>>`, detected + labeled + explained;
   - a **known miss or confirmed gap** — `<<technique>>`, to show we publish the misses;
   - an **honest limit** — a DEAD / unlabelable class (sibling-ambiguous vs
     nominal-ambiguous, coverage doc §B).
4. **The honest limits** (coverage doc "What it does NOT catch", A–F): the classifier
   cannot detect what Stage 1 missed, unlabelable classes, unobservable attacks,
   out-of-fold label accuracy, the post-mode-switch blind window, and
   `<<any mode or condition currently outside its design band>>`.
5. **Next bets — and this is where the ask is.** List the open backlog with keys, say
   which is blocking others, and ask *which of these matter most to you*. A rollout that
   ends without a prioritisation answer has not earned its slot.

## Feedback capture

Three steps, deliberately separated — **capture is not triage**.

**Step 1 — during the session: capture verbatim.** Fill only `#`, `Stakeholder`,
`Feedback`, `Type`. Leave `Jira` and `Slug` empty. Do not edit what was said into what you
think was meant, and do not stop to decide whether something deserves a ticket; that
judgement is Step 2 and doing it live loses the wording.

- **`#`** is a within-session ordinal (1, 2, 3…), not a global ID. It exists so the room
  can say "back to 3" and so the eventual ticket can cite *"raised as feedback #3 in the
  `<<date>>` readout"*. It restarts each session.
- **`Type`** is what kind of response the feedback demands, which decides Step 2:
  | Type | Means | Usually becomes |
  |---|---|---|
  | `gap` | "you don't catch X" / "that number looks wrong" | a new detector or measurement ticket |
  | `feature` | "can it also do Y" | a new capability ticket |
  | `doc` | "this is confusing / explain Z" | an edit to `V5_DETECTOR_COVERAGE.md`, often no ticket |
  | `priority` | "do B before A" | **no new ticket** — a re-rank of existing backlog items |

**Step 2 — after the session: triage and assign a slug.** Decide which rows become
tickets. Each one that does gets a **slug** here, written as Summary + Description + Type
per the Jira rule. Rows that don't become tickets stay in the table with the reason — a
`priority` row pointing at an existing key, or a `doc` row marked "folded into coverage
doc".

**Step 3 — create in Jira, then close the loop.** Jira assigns the key. Add the row to
`JIRA_CROSSWALK.md` (key · slug · type · epic · summary · `Backlog`), then fill the key
back into the `Jira` column below so this table and the crosswalk agree.

> **On the slug:** it is *not* optional, it is just *late*. Every ticket needs one — it is
> the stable local handle that plan headings and `check_ticket_titles.py` key off, and a
> crosswalk row without one is invisible to that check. But inventing slugs
> mid-conversation produces bad ones, so they are assigned at Step 2, not Step 1.

| Jira | Slug | # | Stakeholder | Feedback / question | Type |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

**Worked examples** (illustrative — delete from the sprint copy once real rows exist):

| Jira | Slug | # | Stakeholder | Feedback / question | Type |
|---|---|---|---|---|---|
| AINOS3-89 | catch-rate-provenance-gap | 1 | *(ops lead)* | "The EPS panel says detected by nothing but shows 3/3 incident recall. Which is it?" | `doc` |
| *(new)* | inertial-alarm-suppression | 2 | *(console operator)* | "A 33.6 % false-alarm rate in INERTIAL would bury my console. Can it be muted per-mode until it's fixed?" | `gap` |
| — | — | 3 | *(program)* | "Close the EPS gap before any more model work." | `priority` |

Row 1 lands on an **existing** ticket — the question is already known and owned, so no new
key. Row 2 is genuinely new: it gets a slug at triage, a Summary + Description, and a
fresh key from Jira. Row 3 creates **nothing** — it re-ranks an existing ticket above the
rest of the backlog, and the row stays as the record of who asked and why.

## Status

- [ ] Doc ready (`V5_DETECTOR_COVERAGE.md` current to this sprint).
- [ ] Demo ready (`sparta_coverage.html` rebuilt; violet markers match this sprint).
- [ ] Pre-flight click-through done — no stale figures will contradict the narration.
- [ ] **Presentation delivered** — owner action (cannot be automated).
- [ ] **Feedback captured** — table filled through Step 3, crosswalk rows added.

---

## Past rollouts

| Sprint | File | Delivered |
|---|---|---|
| 27 | [`SPRINT_27_STAKEHOLDER_ROLLOUT.md`](SPRINT_27_STAKEHOLDER_ROLLOUT.md) | ⏳ pending (covers Sprints 26 + 27) |
| ≤ 26 | — | Sprints 24–26 shared a single rolling `STAKEHOLDER_ROLLOUT.md`, overwritten each time. Those plans still cite that filename; it was split into this template + per-sprint copies on 2026-08-19, so only the Sprint-26 content survived (folded into the Sprint-27 readout). |
