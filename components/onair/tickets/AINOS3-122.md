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

- [ ] `AC1` The `IMP-0001…0006` removal executed: 18 script files deleted, 5 classes dropped from the label set, and every reference in an **open** ticket or active document resolved (`AINOS3-84`, `AINOS3-99`, `AINOS3-101`, `V5_DETECTOR_COVERAGE.md`, `AINOS3_118_VECTOR_BACKLOG.md`, workbook `SPARTA_Mapping`). Done tickets and `JIRA_CROSSWALK.md` keep their references — they are append-only history.
- [ ] `AC2` `audit_script_vs_stix.py --structural` fixed to group on the discriminating action, and the collision map **re-derived** — the published 10 groups / 13 probe-only are a lower bound until it is.
- [ ] `AC3` Every surviving class checked against that re-derived map; each collision resolved as **collapse** (one class) or **script-fix** (distinct, script is the limitation), with the `EX-0014.01` precedent as the standard of proof — IOB patterns decide, not footprint.
- [ ] `AC4` `EX-0012.04 [prereq]` adjudicated with a recorded reason; a class name that encodes a collection artifact is not carried forward silently.
- [ ] `AC5` v4.0 mechanism ids attached to surviving classes as cross-references, with the mapping recorded as **judgement** and its rationale — not as STIX authority, which does not exist for it.
- [ ] `AC6` A frozen class list published as a reviewable artifact, one line of justification per class, naming each for its demonstrable footprint. The count is stated against the current 24 attack classes. Nothing downstream may change membership or names after this without reopening the ticket.
- [ ] `AC7` The four derived artifacts regenerated on `csv_corpus_v3stage` with the frozen labels — ⚠ a **re-fit, ordered**: the OOF cache re-run **first**, then `classifier_tiers.json`, `cluster_taxonomy.json` and `explanation_catalog.json` derived from it (see the artifact table + the 1,696-frame contamination note above — hand-deleting the IMP rows is wrong). `cluster_taxonomy.json` written to a staging `--out-dir` (clobber hazard); the three tracked artifacts reviewed as a git diff before promotion; `AINOS3-97 AC2`'s dependency map used to confirm nothing else reads them.
- [ ] `AC8` A statement of what moved and why — measured F1 changes where a genuine degeneracy was collapsed, reported as a **taxonomy change, never a model improvement** — and `V5_DETECTOR_COVERAGE.md` updated from its "frozen pending regeneration" placeholders to the regenerated values (catch-rate table, §4 tier minima, OOF label-accuracy breakdown).
- [ ] `AC9` `AINOS3-100` and `AINOS3-101` updated to consume the `AC6` artifact. ⚠ `AINOS3-101 AC2`'s designated ROBUST test case is `IMP-0005`, which this ticket deletes — its replacement is chosen after the relabel, from whatever class is then nearest the bar.

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
