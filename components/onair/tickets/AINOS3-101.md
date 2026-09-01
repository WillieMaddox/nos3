---
key: AINOS3-101
slug: retrain-clean-corpus
type: Story
epic: AINOS3-98 (corpus-integrity)
status: Backlog
priority: Medium
opened: 2026-08-23
sprints: [28]
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

- [ ] `AC1` Retrain and re-derive tiers on the clean corpus; report whether `ROBUST` is reachable.
- [ ] `AC2` ⚠ A designated near-bar test case reported explicitly against the 0.85 bar. The **previous** designee, `IMP-0005` (min F1 0.8481), is **removed** — it was a deprecated-`IMP` class whose script was probe-only (NOOP-only, self-declared "CONCEPTUAL"), so its near-`ROBUST` score was a corpus artifact, not a real detection. The replacement is chosen **after** the relabel, from whichever surviving class is then nearest the bar; naming it is part of this ticket, not inherited.
- [ ] `AC3` ⚠ The like-for-like control is produced — tiers re-derived on `csv_corpus_v3stage` restricted to the same mode scope — or the comparison confounds cleaner data with narrower scope.
- [ ] `AC4` ⚠ The 0.85 bar is **not** moved; more instances make `ROBUST` harder (min over more folds).
- [ ] `AC5` Deployment, if any, follows the `AINOS3-37` discipline: one-line ini change, one-line rollback, live-verified, build tree synced. **Not deploying is a valid outcome.**
- [ ] `AC6` ⚠ **Consume the frozen label set** (`data/onair/models/label_set.json`, `AINOS3-122 AC6`): the retrain reads its class list and `training_excludes()` (via `label_set.py`) rather than inferring labels from the corpus — `dropped` + probe-only `deferred` (Group A) excluded, cluster `deferred` (Group B) trained. ⚠ **This ticket owns the true 17-class DEPLOY** the `AINOS3-122 AC7` interim regeneration did not: retrain **and redeploy the classifier `.pkl`** (currently `xgb_attack_classifier_v3_hybrid.pkl`, still 26-class) so the live plugin stops predicting the removed classes, then promote the derived artifacts to match. Promoting `AINOS3-122`'s staging artifacts without this pkl retrain would leave the live 26-class classifier predicting labels the 17-class `cluster_taxonomy.json` has no entry for.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
