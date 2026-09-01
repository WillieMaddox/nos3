---
key: AINOS3-122
slug: label-set-freeze
type: Story
epic: AINOS3-98 (corpus-integrity)
status: Committed
priority: High
estimate: E 5 / T 1.5
opened: 2026-08-28
sprints: [28]
origin: AINOS3-96 (sparta-stix-ingest)
---

# label-set-freeze — Freeze the class label set

**Summary:** As an ML engineer, I want the classifier's class list and class names settled and frozen as a reviewed artifact before any collection or retrain, because the label vector is the single input that `classifier_tiers.json`, `cluster_taxonomy.json`, `explanation_catalog.json` and the LOIO folds all derive from — so a bad class invalidates all four at once, and if it is discovered after collection the fix is another collection.

## Description

The class list has never been decided. It is an emergent property of whichever scripts happened
to be collected, and `AINOS3-96` established that this has already gone wrong in three
independent ways. `AINOS3-96` routed the class-list and class-naming decisions "to the retrain
(`AINOS3-101`) and the overlay" — **and `AINOS3-101` never absorbed them.** They are in no
ticket's acceptance criteria. This ticket is that missing owner.

It must complete **before** `AINOS3-100` (collection). `AINOS3-101` runs *after* collection, so
it structurally cannot host a decision that gates it — that is the whole reason this is a
separate ticket and not extra ACs on `AINOS3-101`.

**What is already settled**, decided with the owner and recorded in `AINOS3-96`'s 2026-08-28 log
entry, so this ticket executes rather than re-litigates:

- **The six deprecated `IMP-0001…0006` techniques are removed, not remapped.** Verified: 6 of 270
  attack-patterns are deprecated and they are exactly the v3 Impact family; they carry **zero IOB
  indicators**; and no successor mapping exists in the bundle because SPARTA replaced an
  **effect** taxonomy with a **mechanism** taxonomy. Scope: 18 script files, 5 of 24 attack classes.
- **Class names come from the demonstrable footprint**, STIX-informed but never STIX intent —
  `AINOS3-96 AC4`. 18 of 24 classes currently carry labels that claim more than the frame proves.
- **v4 mechanism ids are cross-references, not class names.** A v4.0 technique with no collected
  data is an empty class, not a coverage win.

**What this ticket must still decide**, each with evidence rather than assertion:

- **`EX-0012.04 [prereq]`** is a class whose name encodes a *collection artifact*, not a
  technique. It was never graded by `AINOS3-96` (which graded 24; the tier file holds 26 —
  the other ungraded entry is `nominal`, correctly out of scope).
- **The footprint-collision set.** `AINOS3-96` published 10 identical-footprint groups and 13
  probe-only techniques, but ⚠ **that list is a lower bound**: `audit_script_vs_stix.py
  --structural` groups on the *full* command set, so it missed `IMP-0001` ≡ `EX-0012.09`, which
  send the same `EPS SWITCH` on `0x191A` and differ only in surrounding NOOP/REQ_HK padding.
  Both are `HIGH-VAR` with a 0.00 minimum fold. The tool must be fixed to group on the
  **discriminating action** before the collision map can be trusted.
- **Probe-only classes.** `IMP-0003` and `IMP-0005` are the two class members of the probe-only
  set; both leave with the IMP removal. Confirm no others remain.

**The four derived artifacts, and why regenerating them is part of this ticket.** Four artifacts
are a pure function of `(corpus, per-frame label assignment, model recipe)`, so **any change to
the label partition — a size change or a frame reassignment — invalidates all four**; only a pure
1:1 rename escapes with a string-substitution. This ticket changes the partition (5 removals, plus
any `AC3` collapse), so all four regenerate. ⚠ This is a **re-fit, not a row-delete**: removing a
class re-routes its frames — measured, **1,696 frames whose true class survives were mispredicted
into IMP buckets** and must re-route — so the surviving classes' F1s change; hand-deleting the IMP
rows would leave stale, wrong numbers. It is **offline** (reads `csv_corpus_v3stage` + the deployed
model, no stack). Locations (not co-located):

| # | artifact | path | git |
|---|---|---|---|
| 1 | OOF cache (regenerate FIRST — the others derive from it) | `data/onair/models/cluster_rescore/loio_predictions_oof_v3hybrid_full.npz` | untracked (large) |
| 2 | `classifier_tiers.json` | `data/onair/models/classifier_tiers.json` | tracked |
| 3 | `cluster_taxonomy.json` | `data/onair/models/cluster_rescore/cluster_taxonomy.json` | tracked |
| 4 | `explanation_catalog.json` | `data/onair/models/explanation_catalog.json` | tracked |

⚠ **Clobber hazard:** `eval_classifier_clusters.py` overwrites the **deployed** `cluster_taxonomy.json`
unless pointed at a staging `--out-dir`. Regenerate to staging, diff, then promote.

⚠ **Nothing here requires recollection.** Renaming, collapsing and dropping operate on the label
vector; the frames are untouched. That is precisely why it must happen before collection and not
after — the same correction costs one regeneration now and one full collection later.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [x] `AC1` The `IMP-0001…0006` removal executed: 18 script files deleted, 5 classes dropped from the label set, and every reference in an **open** ticket or active document resolved (`AINOS3-84`, `AINOS3-99`, `AINOS3-101`, `V5_DETECTOR_COVERAGE.md`, `AINOS3_118_VECTOR_BACKLOG.md`, workbook `SPARTA_Mapping`). Done tickets and `JIRA_CROSSWALK.md` keep their references — they are append-only history.
- [x] `AC2` `audit_script_vs_stix.py --structural` fixed to group on the discriminating action, and the collision map **re-derived** — the published 10 groups / 13 probe-only are a lower bound until it is.
- [x] `AC3` Every surviving class checked against that re-derived map; each collision resolved as one of **three** buckets: **collapse** (telemetry-identical *and* one technique → merge to one class), **script-fix** (distinct techniques the script conflates → repair the script), or **observability-limited** (distinct techniques, telemetry-identical, neither the script's fault nor collapsible → keep distinct as a degenerate cluster scored on cluster F1). IOB patterns decide which, not footprint, with the `EX-0014.01` precedent as the standard of proof.
- [x] `AC4` `EX-0012.04 [prereq]` adjudicated with a recorded reason; a class name that encodes a collection artifact is not carried forward silently.
- [x] `AC5` v4.0 mechanism ids attached to surviving classes as cross-references, with the mapping recorded as **judgement** and its rationale — not as STIX authority, which does not exist for it.
- [x] `AC6` ⚠ **This is the freeze.** Make the label set **explicit**: create `data/onair/models/label_set.json` as the tracked **source of truth** for the class list — replacing `train.py`'s implicit `sorted(df[label_column].unique())` (line 271), which infers classes from whatever happens to be in the corpus. A **code change plus a data artifact**, not a document. One row per class: `{id, name (AC6 footprint-based), v4_mechanism (AC5), status}` where `status ∈ confirmed | deferred | dropped`; `deferred`/`dropped` rows also carry `reason` and, for `deferred`, a `trigger` + `gating_ticket`.
      - ⚠ **Integration point corrected during execution:** `train.py:271` is the **IF** trainer; the classifier's labels come from `v3["labels"]` (`build_hybrid_classifier.py:110`), not there. The wiring is a `label_set` loader that the classifier re-fit (`AC7`) consumes to drive `exclude_labels` from `status`: `dropped` (5 IMP + `EX-0012.04 [prereq]`) and probe-only `deferred` (Group A) excluded; cluster `deferred` (Group B) stays trained as its degenerate cluster. **9 labels excluded.**
      - It is the **source** the three derived artifacts (`classifier_tiers.json`, `cluster_taxonomy.json`, `explanation_catalog.json`) are regenerated *against* (`AC7`) — they reflect it, they do not own it (they are outputs of training; this is its input).
      - It is the **register**: `deferred` rows are the parked classes; a re-freeze operates on this file and so cannot avoid reconsidering them (the deferred status is the flag). No membership, name, or status changes downstream without reopening this ticket.
      - Counts against the current 24 attack classes: `dropped` 6 (5 IMP + prereq), `deferred` 6 (DE-0003.03/.09/.10, EX-0012.03/.04/.05), `confirmed` the remainder + `nominal`.
- [ ] `AC7` The four derived artifacts regenerated on `csv_corpus_v3stage` with the frozen labels — ⚠ a **re-fit, ordered**: the OOF cache re-run **first**, then `classifier_tiers.json`, `cluster_taxonomy.json` and `explanation_catalog.json` derived from it (see the artifact table + the 1,696-frame contamination note above — hand-deleting the IMP rows is wrong). `cluster_taxonomy.json` written to a staging `--out-dir` (clobber hazard); the three tracked artifacts reviewed as a git diff before promotion; `AINOS3-97 AC2`'s dependency map used to confirm nothing else reads them.
- [x] `AC8` A statement of what moved and why — measured F1 changes where a genuine degeneracy was collapsed, reported as a **taxonomy change, never a model improvement** — and `V5_DETECTOR_COVERAGE.md` updated from its "frozen pending regeneration" placeholders to the regenerated values (catch-rate table, §4 tier minima, OOF label-accuracy breakdown).
- [x] `AC9` `AINOS3-100` and `AINOS3-101` updated to consume the `AC6` artifact. ⚠ `AINOS3-101 AC2`'s designated ROBUST test case is `IMP-0005`, which this ticket deletes — its replacement is chosen after the relabel, from whatever class is then nearest the bar.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-08-28 · created — carrying the settled decisions out of the `AINOS3-96` re-audit

Opened because the `AINOS3-115` rewrite audit found the class-list and class-naming decisions
had been routed to `AINOS3-101` by `AINOS3-96 AC4` and never picked up — they exist in no
ticket's ACs. The IMP removal decision and the two `AINOS3-96` corrections behind it are
recorded in that ticket's 2026-08-28 entry; the evidence is not repeated here.

Bundle sha256 for every STIX claim in this ticket:
`f9ce5b05270ce76677c5a7b8b14d65f223c75849587f09af482665f7ee42fffa` (now tracked — see
`AINOS3-96` [3]).

### 2026-08-29 · AC2 DONE — collision tool fixed, map re-derived; class collisions are the two known groups

`audit_script_vs_stix.py` had a **pre-existing footprint bug**: `_footprint` captured the phantom
pair `('mid','fc')` from the generic `build_ccsds_cmd(mid, fc)` **helper definition** (parameter
names, not a real send). The full-footprint grouping was accidentally shielded because per-script
NOOP diversity diluted the phantom; the moment boilerplate was stripped to expose the
*discriminating* action (the AC2 ask), the phantom became the sole shared element and over-merged
19 unrelated techniques into one false group. Fix: exclude bare lower-case MID tokens
(`^[a-z_][a-z0-9_]*$`) from the footprint, then group on the boilerplate-stripped
(NOOP/RESET/RST_COUNTERS/REQ_HK/SEND_HK/SEND_DIAG) discriminating action.

**Re-derived map (151 scripts, IMP gone, deprecated=0):**

- Full-footprint groups: 6 (was 10). Class-containing: **`EX-0012.03/04/05`** and
  **`EX-0012.12/EX-0014.01`** — the only two.
- Discriminating-action groups surfaced 2 collisions the scaffold hid — `['IA-0003','IA-0004.01','IA-0008.02','IA-0011']`
  and `['IA-0005.02','IA-0006','IA-0010']` — but **neither contains a classifier class** (all Initial-Access).

**Consequences for the freeze (feeds `AC3`):**

- The class-vs-class collision set is **exactly** the two groups above, both already adjudicated:
  `EX-0012.03/04/05` = distinct techniques / telemetry-identical → keep distinct, observability
  gap (AINOS3-96 AC6); `EX-0012.12/EX-0014.01` = separable by IOB → keep distinct, EX-0014.01 is a
  script-fix (AINOS3-116). **No hidden class collision existed.** `EX-0012.09` is now collision-free
  (its old partner `IMP-0001` was removed).
- ⚠ New signal: `DE-0003.03/.06/.09/.10` (four classes) drop into **probe-only** once the phantom
  is removed — their footprint is NOOP-only. Mechanically confirms AINOS3-96's read; relevant to
  `AC6` naming (these classes carry no distinctive attack footprint).

The re-derived collision list is the input for `AINOS3-116 AC6` (run `--degeneracy` per group).

### 2026-08-29 · AC4 DONE — drop `EX-0012.04 [prereq]`; exclude its frames

**Decision (owner): drop it.** It is not a technique — `run_attack.py:576` labels the
prerequisite *setup* phase of a chained attack `<id> [prereq]` (level-2 setup), so
`EX-0012.04 [prereq]` is EX-0012.04 run as a chain prereq. A class name that encodes the
collection harness's chaining step, not an adversary technique.

**Frame disposition: EXCLUDE from the training/eval corpus (not merge, not relabel-nominal).**
Measured on `csv_corpus_v3stage` (206,373 frames):

| | frames | note |
|---|--:|---|
| `EX-0012.04 [prereq]` | 6,159 | **87 % predicted `nominal`** (5,344) — benign-looking setup |
| `EX-0012.04` (real) | 6,603 | the actual technique class, kept |
| `nominal` | 126,441 | |

- **Merge into `EX-0012.04`** would nearly double it (6,603 → 12,762) with mostly-nominal frames,
  artificially collapsing its apparent detectability — rejected.
- **Relabel to `nominal`** would inject 6,159 attack-setup frames (13 % attack-looking) into the
  baseline, risking FP and teaching "setup = nominal" — rejected.
- **Exclude** removes only the synthetic chaining artifact; zero genuine technique data lost.

⚠ Disposition for `AC7`: filter `y_true == "EX-0012.04 [prereq]"` out of the corpus before the
re-fit. Class count 26 → 25 here (before the IMP removal already folded in). ⚠ Forward note for
`AINOS3-100`: the steady-flight collection should not auto-mint `[prereq]` classes — run prereqs
without emitting a distinct technique label, or exclude the setup window from the labelled span.

### 2026-08-29 · AC3 DONE — third bucket added; the two class collisions resolved

The `collapse` / `script-fix` binary was incomplete: a pair can be **distinct techniques that are
telemetry-identical for reasons that are neither the script's fault nor collapsible** — the fix is
observability, and the classifier already emits the *cluster* label for them (cluster-scored F1).
Added that as the third bucket, **observability-limited**. Resolution of the only two
class-vs-class collisions (from the AC2 re-derived map):

| collision | bucket | resolution |
|---|---|---|
| `EX-0012.03/04/05` | **observability-limited** | Distinct techniques (raw memory write / subscriber-table remap / scheduler-param edit) sharing one command signature (`CFE_TBL LOAD` of a non-existent file → identical failed-load footprint). The separating observable — which table changed — is **not recorded**. Keep the three classes distinct; the system emits their shared cluster label (AINOS3-96 AC6). |
| `EX-0012.12/EX-0014.01` | **script-fix** | Distinct techniques the two scripts conflate (both send `CFE_TIME SET_TIME`), but their **IOB patterns differ** — EX-0014.01's GNTM-5/9/10 GPS-input signals separate them (AINOS3-116). Repair EX-0014.01 to a real GPS-time spoof; keep distinct. |

No `collapse` outcome — neither pair is one-technique. `EX-0012.09` is collision-free (AC2).

### 2026-08-29 · AC5 DONE — v4 mechanism cross-refs for all 19 technique classes (Outcome A)

⚠ Scope clarified: this maps the **technique** to its v4 Impact-mechanism, from the SPARTA
definition — it is a taxonomy cross-ref, **not** a claim about our script's footprint (that test
is AC6). So every technique class is mapped; `nominal` is the only exempt entry (not a technique).
`x-v4-mechanism` is recorded per class as **judgement + rationale**, never as STIX authority (no
successor mapping exists — AINOS3-96). Ambiguous techniques carry the runner-up as a candidate.

| class | v4 mechanism | rationale (candidate) |
|---|---|---|
| DE-0003.01 Vehicle Command Counter | IMP-0010 Data Manipulation | falsify a telemetered counter value |
| DE-0003.02 Rejected Command Counter | IMP-0010 Data Manipulation | suppress/falsify a counter |
| DE-0003.03 Command Receiver On/Off | IMP-0008 State/Mode | toggle receiver operational mode |
| DE-0003.06 Telemetry Downlink Modes | IMP-0011 Command & Data Flow | alter downlink path/delivery *(cand. IMP-0008)* |
| DE-0003.08 Received Commands | IMP-0010 Data Manipulation | edit stored command records |
| DE-0003.09 System Clock for Evasion | IMP-0014 Timing/Sync | bias the clock to shift the timeline |
| DE-0003.10 GPS Ephemeris | IMP-0010 Data Manipulation | falsify ephemeris data |
| EX-0008.01 Absolute Time Sequences | IMP-0007 Native Functionality Abuse | trigger the stock SC ATS engine |
| EX-0008.02 Relative Time Sequences | IMP-0007 Native Functionality Abuse | trigger the stock SC RTS engine |
| EX-0012.03 Memory Write/Loads | IMP-0012 Software/Firmware | raw memory write to the implementation *(cand. IMP-0009)* |
| EX-0012.04 App/Subscriber Tables | IMP-0011 Command & Data Flow | subscriber tables govern message routing *(cand. IMP-0009)* |
| EX-0012.05 Scheduling Algorithm | IMP-0009 Configuration | scheduler parameter/config edit *(cand. IMP-0007)* |
| EX-0012.07 Propulsion Subsystem | IMP-0009 Configuration | propulsion parameter edit |
| EX-0012.08 ADCS | IMP-0008 State/Mode | script forces ADCS SET_MODE *(cand. IMP-0009 gains)* |
| EX-0012.09 EPS | IMP-0008 State/Mode | toggle a power-switch state *(cand. IMP-0009)* |
| EX-0012.12 System Clock | IMP-0014 Timing/Sync | SET_TIME alters the time reference |
| EX-0014.01 Time Spoof | IMP-0014 Timing/Sync | spoof the time input |
| EX-0014.03 Sensor Data | IMP-0010 Data Manipulation | inject false sensor data |
| EX-0014.04 PNT Spoof | IMP-0010 Data Manipulation | forge externally-sourced GNSS data |
| nominal | — | not a technique |

⚠ Five carry a flagged candidate (DE-0003.06, EX-0012.03/04/08/09) — the pick is stated but the
runner-up is recorded so the choice is visible, not silent. These are cross-references for
forward v4 context; they do **not** become class names (AC6).

### 2026-09-01 · AC6 DONE — the freeze: `label_set.json` created + `label_set.py` loader

The class label set is now **explicit**. `data/onair/models/label_set.json` (tracked) is the
source of truth — a 26-row ledger of every original class with its disposition; the three derived
artifacts are regenerated *against* it (`AC7`), not the other way round. Validated: its 26 ids
match the corpus label set exactly (`label_set.py --check`).

| status | n | classes |
|---|--:|---|
| **confirmed** | 14 | `nominal`, DE-0003.01/.02/.06/.08, EX-0008.01/.02, EX-0012.07/.08/.09/.12, EX-0014.01/.03/.04 |
| **deferred** | 6 | Group A (probe-only, *excluded* from training, gated `AINOS3-115`): DE-0003.03/.09/.10 · Group B (telemetry-degenerate, *trained as cluster*, gated `AINOS3-119`): EX-0012.03/.04/.05 |
| **dropped** | 6 | IMP-0001/0002/0003/0005/0006, `EX-0012.04 [prereq]` |

Each row: `{id, name (footprint-based, AC6), v4_mechanism (AC5), status, training}`; deferred/dropped
carry `reason`, deferred also `trigger` + `gating_ticket`. `training_excludes` = 9 (dropped +
Group-A). Names settled per the 2026-08-29 draft + the owner's decisions: keep DE-0003.06 (repair
candidate), defer DE-0003.03/.09/.10 and EX-0012.03/.04/.05, drop the prereq.

⚠ **Integration correction:** my AC6 text named `train.py:271` as the read point — wrong; that is
the IF trainer. The classifier's labels come from `v3["labels"]`. So the file is consumed via
`components/onair/training/label_set.py` (`load_label_set` / `training_excludes` / `trained_classes`
/ `deferred`), which the classifier re-fit (`AC7`) calls. AC6 text corrected above.

The deferred register now lives entirely in this file's `status` column — no standing epic (the
approach was rejected after review) and the C1 re-check is enforced as `AINOS3-115 AC6` and
`AINOS3-119 AC5`. **This is the freeze.** Membership, names, and status change only by reopening
this ticket.

### 2026-09-01 · AC7 regenerated to STAGING (not promoted); AC8 "what moved"

All four label-derived artifacts re-fit on `csv_corpus_v3stage` reading the frozen label set
(`label_set.py training_excludes()` → 9 labels dropped), written to
`data/onair/models/label_set_regen/` — **deployed artifacts untouched**, so promotion is a
reviewable git diff. OOF was a real 46-min LOIO re-fit (3 folds, 17 trained labels, 183,902 OOF
preds); taxonomy re-derived from that OOF via `recluster_from_cache.py` (no second re-fit); tiers
derived from both; explanation catalog re-built (16 attack classes, no IMP/prereq). ⚠ The
explanation catalog still uses the **deployed 26-label hybrid pkl** restricted to the surviving
classes — a true 17-label explanation needs the classifier redeploy (AINOS3-101), not AC7.

**AC8 — what moved, reported as a taxonomy change, not a model result:**

| metric | deployed (26) | staging (17) | reading |
|---|--:|--:|---|
| raw OOF frame-accuracy (attack) | 28.2 % | 21.9 % | composition artifact — the removed IMP classes were relatively well-predicted, inflating the old average |
| **fair** (both scored on the same 17 classes) | 23.1 % | 21.9 % | **−1.2 pts, within noise** — the relabel removed junk, not signal |
| tier counts | 7 STABLE-MID / 16 HIGH-VAR / 3 DEAD | 2 STABLE-MID / 14 HIGH-VAR / 1 DEAD | ROBUST **still empty** either way |
| notable slip | EX-0008.01 STABLE-MID (0.71) | → HIGH-VAR (0.50) | fewer neighbours to absorb its errors |
| CFE_TBL cluster | `{03,04,05}` | `{03,04}` + `{05}` alone | degeneracy structure shifted on the 17-label refit; tighter clusters score lower (0.39→0.06) |

The honest headline: **the freeze is metric-neutral on the surviving classes** (−1.2 pts fair);
the scary-looking raw drops are composition + taxonomy recompute, exactly what AC8 says to expect.
No class reached ROBUST — unchanged.

**Not yet done (awaiting owner go):** the `V5_DETECTOR_COVERAGE.md` placeholder→real-number update
(rest of AC8), and **promotion** of the staging artifacts over the deployed ones. `AC7`/`AC8`
stay unchecked until reviewed + promoted.

### 2026-09-01 · AC8 DONE — coverage doc updated; incident metric DEFERRED to Sprint-29

`V5_DETECTOR_COVERAGE.md` updated from its "frozen pending regeneration" placeholders to the
regenerated 17-class values: §4 tier minima, the per-technique table (8 rows: EX-0008.01 tier
slip, the EX-0012.03/04/05 deferred+split notes, DE-0003.03/.09/.10 marked DEFERRED), and the
banner. Frame-level accuracy is near-neutral on the survivors (fair 23.1 %→21.9 %, −1.2 pts).

⚠ **Incident-label-accuracy metric DEFERRED, with a traced cause — not baked in.** The fair
same-16-classes incident number moves **28.6 %→21.4 %**, but that is **3 of 56 detected incidents**
and every one is mechanically traceable (not a model-quality regression):

| incident | Δ | cause |
|---|:--:|---|
| EX-0012.03, .04 | −2 | **cluster split** (AC7): `{03,04,05}`→`{03,04}`+`05` tightened the cluster → a formerly same-cluster prediction is now "wrong" |
| EX-0012.07, .12 | −2 | **class removal** (AC1/AC6): frames that used to predict a removed class re-route to a wrong surviving class, flipping the incident majority |
| EX-0014.04 | +1 | class removal helped this one |

⚠ Also corrected a slip in the first read: the raw −7.2 pt figure double-counted the dropped
`EX-0012.04 [prereq]` attack (a base-name strip folded it into trained `EX-0012.04`); the true
fair delta is −3 incidents. On a 56-incident corpus Sprint 27 already judged too small here, this
is not trustworthy, so the incident figures (42.3 %/34.6 %) stay the **deployed 26-class** values,
re-derivation deferred to the Sprint-29 rebuild (`AINOS3-100`/`AINOS3-101`). Owner decision.

Staging artifacts remain in `data/onair/models/label_set_regen/` — **not promoted**; the live
overlay still reads the 26-class artifacts.

### 2026-09-01 · AC1 signed off — removal executed, references resolved, workbook left by decision

The `IMP-0001…0006` removal is complete: 18 scripts deleted, the 5 classes recorded `dropped` in
`label_set.json`, and every IMP reference in the open tickets / active docs (`AINOS3-84`,
`AINOS3-99`, `AINOS3-101`, `V5_DETECTOR_COVERAGE.md`, `AINOS3_118_VECTOR_BACKLOG.md`) resolved —
the remaining occurrences are removal-notes that *document* the removal, which is what "resolved"
means, not stale data. ⚠ **Workbook `SPARTA_Mapping` left unedited by owner decision (2026-09-01):**
`logging_workbook.json` is a verbatim extraction of Aerospace's spreadsheet; editing it would
falsify an external source. Same principle as the append-only Done tickets and crosswalk.

### 2026-09-01 · AC7 stays OPEN — gated on AINOS3-97 + AINOS3-101 (not our incomplete work)

The regeneration is done (staging, validated), but two of AC7's own clauses are gated on other
tickets, so AC7 cannot sign off standalone:

- **dependency-map check** → `AINOS3-97 AC2` (Open) — until the artifact→corpus map exists,
  "nothing else reads these" is unverified.
- **promotion** → `AINOS3-101` — promoting the 17-class artifacts while the live classifier `.pkl`
  still predicts 26 classes would mismatch the taxonomy (a live IMP prediction has no entry). The
  pkl retrain+redeploy is `AINOS3-101 AC6`. The git-diff review of the three tracked artifacts
  (sized: tiers 433 / taxonomy 295 / explanation 472 changed lines) happens at that promotion.

Staging artifacts stay in `data/onair/models/label_set_regen/`, unpromoted; the live overlay reads
the 26-class artifacts until `AINOS3-101`.
