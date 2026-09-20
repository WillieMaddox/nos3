---
key: AINOS3-101
slug: retrain-clean-corpus
type: Story
epic: AINOS3-98 (corpus-integrity)
status: Ready
priority: High
opened: 2026-08-23
sprints: [28, 29]
---

# AINOS3-101 — Retrain + re-derive tiers on the clean corpus — is `ROBUST` reachable?

**Summary:** As an ML engineer, I want the classifier retrained and its confidence tiers re-derived on the clean, steady-flight corpus with the frozen label set, so we can answer — with a like-for-like control — whether any class reaches the `ROBUST` bar, which Sprint 27 found the current corpus never supported.

## Description

Sprint 27 established that the `ROBUST` tier (min LOIO F1 ≥ 0.85 across all folds) was **never
supported by its own data** — it was asserted, then found empty once tiers were *derived* rather
than declared. Sprint 28 then found the compounding cause: 83 % of the attack corpus sat inside
the detector's post-mode-switch blind window, so the fold minima that set every tier were built
largely from unusable frames.

This ticket is the retrain that tests whether a corpus without those two defects — collected
under the steady-flight protocol (`AINOS3-100`) and labelled against the frozen class set
(`AINOS3-122`) — can put any class into `ROBUST`. It runs **after** collection; it does not
itself collect.

⚠ **Depends on three upstream freezes, and inherits their discipline:**

- **`AINOS3-122`** settles the class list and names. The five deprecated-`IMP` classes are
  gone and class names track the demonstrable footprint, so this retrain trains on a label set
  that no longer over-promises. It must consume that frozen set, not re-derive its own.
- **`AINOS3-100`** supplies the clean corpus and its manifest.
- **`AINOS3-99`** justifies the instance count, which sets how many folds the `min` runs over.

⚠ **The honest-comparison trap.** A cleaner corpus that is also *narrower in mode scope* would
make `ROBUST` look reachable for the wrong reason. The like-for-like control (`AC3`) is what
separates "cleaner data helped" from "we just evaluated on an easier slice."

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Retrain and re-derive tiers on the clean corpus; report whether `ROBUST` is reachable. ⚠ **Temper the prior:** `AINOS3-99` found the per-instance F1 spread is neither blind-window nor sample-size driven but a **generalisation limit** (a class's footprint varies across runs), and `min`-over-folds structurally penalises that diversity — so `ROBUST` (min F1 ≥ 0.85 across folds) is **probably not reachable via corpus size or steady-flight collection alone**. A `ROBUST`-empty outcome here is the expected result, not a failure; the honest deliverable is *why*, tied to footprint reproducibility.
- [ ] `AC2` ⚠ A designated near-bar test case reported explicitly against the 0.85 bar. The **previous** designee, `IMP-0005` (min F1 0.8481), is **removed** — it was a deprecated-`IMP` class whose script was probe-only (NOOP-only, self-declared "CONCEPTUAL"), so its near-`ROBUST` score was a corpus artifact, not a real detection. The replacement is chosen **after** the relabel, from whichever surviving class is then nearest the bar; naming it is part of this ticket, not inherited.
- [ ] `AC3` ⚠ The like-for-like control is produced — tiers re-derived on `csv_corpus_v3stage` restricted to the same mode scope — or the comparison confounds cleaner data with narrower scope.
- [ ] `AC4` ⚠ The 0.85 bar is **not** moved; more instances make `ROBUST` harder (min over more folds). ⚠ **The bar was not moved, but this AC's premise is REFUTED by its own experiment:** 3 → 5 folds took `ROBUST` from 1 to 3, because more folds also means a larger training set per fold (4 instances vs 2) and that gain outweighs the `min`-over-more-folds penalty. See the 2026-09-13 result.
- [ ] `AC5` Deployment, if any, follows the `AINOS3-37` discipline: one-line ini change, one-line rollback, live-verified, build tree synced. **Not deploying is a valid outcome.**
- [~] `AC6` ⚠ **Consume the frozen label set** (`data/onair/models/label_set.json`, `AINOS3-122 AC6`): the retrain reads its class list and `training_excludes()` (via `label_set.py`) rather than inferring labels from the corpus — `dropped` + probe-only `deferred` (Group A) excluded, cluster `deferred` (Group B) trained. ⚠ **This ticket owns the true 17-class DEPLOY** the `AINOS3-122 AC7` interim regeneration did not: retrain **and redeploy the classifier `.pkl`** (currently `xgb_attack_classifier_v3_hybrid.pkl`, still 26-class) so the live plugin stops predicting the removed classes, then promote the derived artifacts to match. Promoting `AINOS3-122`'s staging artifacts without this pkl retrain would leave the live 26-class classifier predicting labels the 17-class `cluster_taxonomy.json` has no entry for. ⚠ **PARTIAL — the label-set half is done, the DEPLOY half is BLOCKED and cannot be closed by this ticket.** The retrain consumes `label_set.py` and produced a 17-class model. But the live plugin routes FOUR ADCS modes and the `AINOS3-100` corpus holds only SUNSAFE + INERTIAL, so the 17-class model has no PASSIVE/BDOT training data; deploying it would trade a label-set mismatch for a worse one. Needs a four-mode corpus — a Sprint-30 collection item, not a modelling one.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-09-13 · READY — upstream inputs are all in place

#### In plain terms

Everything this work depends on is now in place: the freshly collected data, the frozen list of
attack names, and the frozen list of data columns.

Every dependency this ticket declares is now satisfied. Starting position:

**The corpus (`AINOS3-100`, Done).** `data/onair/corpus/rebuild_2026-09-10/corpus_manifest.json`
— **113 accepted runs / 413,472 frames / 19 techniques**. SUNSAFE **19 x 5 instances** (95 runs),
INERTIAL 18 (all 100 % capture). AC1 alert-eligible **97.2 %** against the 84.4 % pilot
reference; the corpus this replaces lost **83 %** of attack frames inside the detector's blind
window. Every run is `schema-v1` verified, no duplicate cells, and the manifest carries per-run
provenance (CSV, frames, attack windows, capture fraction, FSW build sha, git rev).

⚠ **Mode scope is exactly what `AC3` exists to control for.** This corpus is SUNSAFE-deep
(5 instances) and INERTIAL-shallow (1 instance, 18 techniques). The like-for-like control must
restrict `csv_corpus_v3stage` to the **same** mode scope, or a `ROBUST` result confounds cleaner
data with a narrower slice — the trap named in the Description.

⚠ **`EX-0012.07` has no INERTIAL run**, deliberately: the attack fires thrusters to ~141 deg/s
and breaks the INERTIAL hold by physics (77.2 % capture, gate-rejected). Its INERTIAL absence is
a property of the technique, not a collection gap.

⚠ **`EX-0012.08` self-masks.** It flaps ADCS mode 12–64 times per run (every other technique: 0),
re-arming the 250-frame post-switch blind window, so **46–72 % of its own attack frames are
alert-ineligible**. A weak `EX-0012.08` score is not evidence of model failure;
`mode_switch_count` is recorded per run in the manifest.

**The label set (`AINOS3-122`).** `data/onair/models/label_set.json`, frozen 2026-09-01. The
corpus was generated FROM it, so the 6 `dropped` classes cannot appear. `AC6` still owns the
true 17-class **deploy** — the live `xgb_attack_classifier_v3_hybrid.pkl` is still 26-class.

**The schema (`AINOS3-124`).** `schema-v1`, 470 columns,
`recorded_schema_sha256 = ff8a9e294362a02ab71a497c308a85d9f4ca4d42b29fd9401ce06206eccc926e`.
Pin this, not the sidecar's `schema_sha256` — that one hashes the tlm metadata FILE and does not
move when the CSV prune moves.

**Instance count (`AINOS3-99`).** 5 SUNSAFE instances means `min`-over-5-folds, a **stricter**
bar than the 3 folds behind the last tier table. Expect `ROBUST` to stay empty; `AC1`
pre-registers that as the expected outcome and asks for *why*, tied to footprint reproducibility.

⚠ **Operational, not technical:** background jobs on this machine are killed intermittently with
"system is running low on memory" for reasons never identified across four investigated
hypotheses. Checkpoint or make long retrains resumable. Do not spend time re-diagnosing it —
[`AINOS3-100`](AINOS3-100.md) records what was already ruled out.

### 2026-09-13 · RESULT — `ROBUST` is reachable, but mostly for reasons other than the clean corpus

#### In plain terms

Three attack types now score well enough to be called trustworthy — but the control experiments
show that is mostly not down to the cleaner data. Two of the three earn their rating simply from
having more training data available, and all three fall apart when tested on the other flight
mode, two of them scoring zero. So "trustworthy" really means "trustworthy in SUNSAFE".

Compared fairly, the clean data does not produce *more* trustworthy attack types — it produces
*different* ones, rescuing one from hopeless while costing another its top rating. The ticket had
predicted that adding data groups would make the standard harder to reach; the opposite happened,
because more groups also means more training data per model.

Two further findings: the planned model swap is blocked, because the live system covers four
flight modes while the new data covers only two; and the first full run of the experiment was
thrown away after it was found to be letting the model see absolute clock and orbit values.

⚠ **The pre-registered expectation was wrong in its headline and wrong in its
mechanism, and the controls are what show it.** Three classes clear the 0.85 bar
on the clean corpus. `AC3` then decomposes that result, and most of it is *not*
corpus cleanliness.

**A defect in this ticket's own harness, caught before it was reported.** The
first full run of every cell was discarded. `eval_classifier_clusters.py` inherits
v3's feature recipe for free by passing v3's *pickled* schema to `build_features`,
and that schema carries the 22 `V5_DELTA_ONLY_COLUMNS` — absolute time references
and the deterministic NOS3 orbit — whose raw values are suppressed so the model
cannot learn the sim epoch and TLE. This retrain derives a FRESH schema (schema-v1
is 470 columns, v3's corpus was 360), so the mask had to be re-applied explicitly
and was not. The retrain would then have differed from v3 in model RECIPE as well
as data — the `AC3` confound arriving through a different door. Fixed with an
explicit `--delta-only-preset v5` default; parity is confirmed empirically, since
the v3stage cell now builds **894** features, exactly the count in v3's deployed
pickle. A test pins the preset against that pickle so the two cannot drift.

#### The four cells

| Cell | Source | Mode scope | Folds | Classes | LOIO acc | ROBUST (attack) |
|---|---|---|--:|--:|--:|--:|
| `rebuild_5fold` (headline) | rebuild | SUNSAFE | 5 | 17 | 0.613 ± 0.037 | **3** |
| `rebuild_3fold` | rebuild | SUNSAFE | 3 | 17 | 0.573 ± 0.033 | 1 |
| `v3stage_sunsafe_3fold` | v3stage | SUNSAFE | 3 | 13 | 0.757 ± 0.013 | 1 |
| `v3stage_allmodes_3fold` | v3stage | all 4 | 3 | 17 | 0.682 ± 0.025 | 0 |

`nominal` is excluded from the ROBUST column — it is not an attack label. Full
tables in [`AINOS3_101_TIER_COMPARISON.md`](../AINOS3_101_TIER_COMPARISON.md).

#### `AC1` — is `ROBUST` reachable? Yes, with three qualifications

- `EX-0014.03` min F1 **0.925**, `EX-0008.01`/`EX-0008.02` min **0.887** (scored as
  a merged cluster, which is the label the system emits — not a per-technique claim).
- ⚠ **Two of the three come from fold count, not corpus quality.** At 3 folds the
  same clean corpus yields ONE. Fold count moves two things at once: more folds to
  take a `min` over (harder) and a training set of 4 instances instead of 2
  (easier). The second dominates.
- ⚠ **`AC4`'s premise is refuted.** The ticket pre-registers that "more instances
  make `ROBUST` harder". 3 → 5 folds took `ROBUST` from 1 to 3. The `min`-over-more-
  folds penalty is real but smaller than the training-data gain.
- ⚠ **All three collapse off-mode.** See the cross-mode holdout below.

#### `AC3` — the like-for-like control, and what each confound is worth

Holding fold count and mode scope fixed (`rebuild_3fold` vs `v3stage_sunsafe_3fold`),
the clean corpus does **not** produce more `ROBUST` classes — one each. What it
changes is *which* classes, and it lifts the weak end substantially:

| Class | v3stage SUNSAFE 3-fold | rebuild 3-fold | Effect |
|---|--:|--:|---|
| `EX-0014.03` | 0.000 (DEAD) | 0.884 (ROBUST) | corpus rescues it outright |
| `EX-0012.09` | 0.000 | 0.493 | corpus |
| `EX-0012.12`/`EX-0014.01` | 0.079 | 0.521 | corpus |
| `EX-0012.03`/`EX-0012.04` | 0.000 | 0.340 | corpus |
| `EX-0008.02` | 1.000 (ROBUST) | 0.758 | corpus *costs* it the tier |

⚠ **The control is not perfectly like-for-like, and the direction of the bias
matters.** Restricting v3stage to SUNSAFE keeps only ~16.9k of 60.6k rows per fold
and drops four classes entirely (`DE-0003.01/.02/.06/.08` have no SUNSAFE frames
there), so its tier table covers **13** classes against the rebuild's **17**. Its
higher raw accuracy (0.757 vs 0.573) is a smaller and easier problem, not evidence
the old corpus is better. Mode scope on its own is worth a lot: v3stage goes from
**0** ROBUST across 4 modes to 1 attack class (plus `nominal`) on SUNSAFE alone.

#### The finding that most limits the result — cross-mode collapse

The headline model, scored on the held-out INERTIAL slice (80,404 frames, never
seen): accuracy 0.7791 but macro-F1 **0.1927** (cluster 0.2827), and the accuracy
is inflated by `nominal` at 75 % of frames.

| Class | SUNSAFE min F1 | INERTIAL F1 |
|---|--:|--:|
| `EX-0014.03` | 0.925 | **0.000** |
| `EX-0008.02` | 0.887 | **0.000** |
| `EX-0008.01` | 0.887 | 0.390 |

`ROBUST` as derived is a **within-mode** claim. The published tier prose says
"trust the label — reliable on EVERY run"; what this corpus supports is "on every
SUNSAFE run". Two of three score zero one mode over — worse than most `HIGH-VAR`
classes manage inside SUNSAFE.

#### `AC1` — *why*, measured on the data rather than inferred

`footprint_reproducibility.py` measures each class's footprint directly, with no
model: the signed set of features displaced > 3 robust sigma from that run's own
nominal median, compared pairwise across instances (Jaccard).

- Spearman(reproducibility, fold-min F1) = **+0.611**; the magnitude-weighted
  cosine variant **+0.728**, over 16 classes. The tier table is largely reading
  footprint reproducibility, as `AINOS3-99` argued.
- ⚠ **But reproducibility is not the whole mechanism.** `EX-0014.03` is `ROBUST`
  on a *low* 0.326 — its footprint varies run to run yet stays distinguishable
  from every sibling. `EX-0012.12` has the *highest* reproducibility (0.696) and
  min F1 only 0.364, because it is merged with `EX-0014.01`. Fold-minimum F1 is
  governed by **reproducibility AND separability**, and the clean corpus improved
  the second: `EX-0014.03` is *more* reproducible in v3stage (0.692) where it is
  DEAD than in the rebuild (0.326) where it is ROBUST.
- Footprints are sparse — 4–14 of 1768 features move per class (`EX-0012.07` is
  the outlier at 59; it perturbs physics).

#### `AC2` — the near-bar class, and why the bar's value does not matter

**`EX-0012.12`**, min F1 **0.3639**, short of 0.85 by 0.4861 — scored on its
cluster with `EX-0014.01`. ⚠ It is "nearest" only in the sense of being the
highest below the bar: excluding `nominal`, the rebuild tier table is **bimodal**,
with nothing between **0.364** and **0.887**. Any bar from ~0.40 to ~0.88 produces
the identical partition. `AC4` says do not move the bar; the stronger statement is
that moving it would change nothing, so the `ROBUST` set is not an artifact of
where the threshold sits.

#### `AC6` — the 17-class deploy is BLOCKED, and not by this ticket

⚠ The live plugin routes **four** ADCS modes (`RoutingModeMap` = PASSIVE / BDOT /
SUNSAFE / INERTIAL) and the deployed hybrid's global head was trained on the v3
corpus spanning all four. The `AINOS3-100` corpus contains **SUNSAFE and INERTIAL
only**. A 17-class model trained on it has never seen a PASSIVE or BDOT frame, so
deploying it would fix the label-set mismatch by introducing a worse one — half the
routed modes classified by a model with no data for them. The cross-mode holdout
above is the evidence that this is not a theoretical worry.

**Recommendation: do not deploy** (`AC5` names this a valid outcome). The live
26-class pkl keeps predicting six removed classes until a corpus covering all four
modes exists. That is a real inconsistency, and it now has a named cause rather
than an owner-less gap.

#### Corpus defect found — for `AINOS3-98`/`AINOS3-100`

`ADCS_GNC.DT` reads **1.5e284** in 6 frames of 413,472 (one instance-4 run; normal
value 0.1). Harmless to a tree model, which bins by rank, but it makes any
mean/variance statistic infinite and overflows a float32 cast to `inf`. Both were
hit here. The measurement now uses median/MAD, and the cache cast clamps rather
than overflowing. ⚠ `build_corpus_manifest.py` does not check for non-finite or
out-of-range telemetry; a future corpus should.

#### Artifacts

- `data/onair/models/rebuild29/{sunsafe_5fold,rebuild_3fold,control_v3stage_sunsafe,control_v3stage_allmodes}/`
  — each with `loio_predictions.npz`, `cluster_taxonomy.json`, `classifier_tiers.json`.
- `sunsafe_5fold/classifier.pkl` — 17-class, 1768-feature, SUNSAFE-trained. The
  evaluation artifact of record; **not** a deploy candidate, per `AC6` above.
- `sunsafe_5fold/holdout_inertial.json`, `footprint_reproducibility.json`.
- New tooling: `retrain_clean_corpus.py`, `footprint_reproducibility.py`,
  `compare_tier_runs.py`, `score_holdout.py`; 29 tests across
  `test_retrain_clean_corpus.py` and `test_footprint_reproducibility.py`.

#### Operational note

The environment reaped the training process every few minutes throughout, with
435 GB free, ~5 GB resident and no cgroup limit — consistent with what
[`AINOS3-100`](AINOS3-100.md) recorded and was told not to re-diagnose. Fold-level
checkpointing was not sufficient (no 29-minute fold could finish between two
kills), so `retrain_clean_corpus.py` checkpoints **inside** the fold via
`warm_start` every 25 boosting iterations. A test pins that block-fitting is
bit-identical to a single fit (max probability delta exactly 0.0), so a resumed
fold is the same model the tier table describes.

### 2026-09-19 · ⚠ RESET — the 2026-09-13 result is SUPERSEDED, not retracted

Reopened on owner direction. Every AC is unchecked again. The result above is **left in
place deliberately**: it is an accurate account of what the interleaved corpus said, and the
contrast with the redo will be worth having.

#### In plain terms

The answer we produced was computed on data recorded in a broken format — every log was two
snapshots interleaved — and on only two of the spacecraft's four flight modes. Both are now
being fixed, so the whole question has to be asked again.

**Two independent reasons it cannot stand:**

1. ⚠ **The representation was defective.** `AINOS3-125` established that every
   recorded CSV is two interleaved buffer snapshots and that lag-1 deltas — the features
   this retrain consumed — carry **4–6× the noise** of same-buffer deltas on 49 columns. A
   like-for-like rerun on blended data moves macro-F1 **0.3851 → 0.4192** and shifts
   individual classes by up to ±0.108 on their fold minimum, which is more than enough to
   move a class across the 0.85 bar. The tier table is the deliverable, so the tier table
   being unstable under the fix is disqualifying.
2. ⚠ **The mode scope was wrong.** `AINOS3-100 AC7` now requires BDOT ×5, PASSIVE ×5 and
   INERTIAL ×4 more. The retrain ran on SUNSAFE ×5 + INERTIAL ×1, and the deploy block in
   `AC6` was itself a consequence of that gap.

**What survives and should be carried into the redo, not rediscovered:**

- The **method**: manifest-driven LOIO, the three-confound decomposition (`AC3`), the
  cross-mode holdout, footprint reproducibility as the mechanism for `AC1`'s *why*.
- The **`AC4` refutation**: 3 → 5 folds took ROBUST from 1 to 3, because more folds also
  means more training data per fold. The AC's premise is wrong regardless of representation.
- The **bimodality**: nothing sat between 0.364 and 0.887, so the 0.85 bar's exact value
  changed nothing. Worth re-testing, but it is a structural observation rather than a
  numeric one.
- ⚠ The **cross-mode collapse** (ROBUST classes scoring 0.000 on INERTIAL) — this is the
  finding most likely to survive, and the one that most constrains what ROBUST can mean.

**Blocked on:** `AINOS3-100 AC7` (four-mode corpus) and `AINOS3-125 AC8` (whether
blended becomes the canonical format). Do not restart until both land, or the redo inherits
a third representation question.

