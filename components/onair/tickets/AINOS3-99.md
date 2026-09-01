---
key: AINOS3-99
slug: fold-variance-triage
type: Spike
epic: AINOS3-98 (corpus-integrity)
status: Open
priority: Medium
opened: 2026-08-23
sprints: [28]
---

# AINOS3-99 — Explain the per-instance F1 spread holding the tier column down

**Summary:** As an ML engineer, I want to know which *runs* produce the zero-F1 LOIO folds, because the tier rule takes the **minimum** across folds, so a handful of bad runs — not the model's average ability — is what is holding `ROBUST` empty.

## Description

The derived tiers (`data/onair/models/classifier_tiers.json`, 3 LOIO folds) show
enormous per-instance spread:

| class | fold F1s | min | max | tier |
|---|---|--:|--:|---|
| `EX-0012.09` | `[0.00, 0.00, 0.50]` | 0.00 | 0.50 | HIGH-VAR |
| `DE-0003.02` | `[0.07, 0.00, 0.65]` | 0.00 | 0.65 | HIGH-VAR |
| `EX-0012.08` | `[0.52, 0.00, 0.29]` | 0.00 | 0.52 | HIGH-VAR |
| `EX-0012.12` | `[0.00, 0.37, 0.14]` | 0.00 | 0.48 | HIGH-VAR |
| `DE-0003.06` | `[0.44, 0.33, 0.00]` | 0.00 | 0.44 | HIGH-VAR |

A class reaching 0.65 on one spacecraft run and 0.00 on another is not information-limited —
it is **instance-limited**. A single contaminated instance is already **ruled out**: zero-F1
folds distribute across all three instances.

⚠ **The example rows were changed 2026-08-28.** They previously led with `IMP-0001` and
`IMP-0003`, two of the five deprecated-`IMP` classes removed from the label set (see
`AINOS3-122` and `AINOS3-96`'s 2026-08-28 entry). The point is unchanged — non-IMP
classes show the same 0.00→0.65 spread — but the **class count and the per-instance zero-F1
distribution are now stale**: they were `26 classes` / `9·6·6 of 26`, computed over the old
label set, and are re-derived only when `classifier_tiers.json` is regenerated on the frozen
labels. `AC1`/`AC2` below therefore run on the **post-freeze** artifact, not the 26-class one.

That leaves the useful question — is the spread explained by the **blind-window collection
defect**? The answer sizes Sprint 29's collection, which is why a 2-hour desk spike runs a
sprint ahead of the ~15 h of wall-clock it governs.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Per-class, per-fold F1 cross-tabulated against the collecting run, from
      `loio_predictions_oof_v3hybrid_full.npz` and the corpus manifest — no re-training.
- [ ] `AC2` For each zero-F1 fold, the fraction of that run's attack frames falling inside a
      post-mode-switch blind window (~45 s / 250 frames).
- [ ] `AC3` A stated verdict with its limits: **blind-window-explained**, **partially explained**, or
      **unexplained** — and if unexplained, what else differs between the runs.
- [ ] `AC4` A recommended instance count for Sprint 29, justified by the observed spread rather than
      assumed. "3, because that is what we had" is acceptable only if the evidence says so.
- [ ] `AC5` ⚠ Note in the write-up that adding instances adds folds, and **min-over-more-folds is a
      stricter bar**.
- [ ] `AC6` **Cross-check against `AINOS3-96`:** if a class's fold spread coincides with a script that
      STIX flags as mislabelled, that is a shared root cause and both tickets should say so.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
