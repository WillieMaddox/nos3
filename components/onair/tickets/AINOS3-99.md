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

The derived tiers (`data/onair/models/classifier_tiers.json`, 26 classes,
3 LOIO folds) show enormous per-instance spread:

| class | fold F1s | min | max | tier |
|---|---|--:|--:|---|
| `IMP-0001` | `[0.00, 0.66, 0.80]` | 0.00 | 0.80 | HIGH-VAR |
| `EX-0012.09` | `[0.00, 0.00, 0.50]` | 0.00 | 0.50 | HIGH-VAR |
| `DE-0003.02` | `[0.07, 0.00, 0.65]` | 0.00 | 0.65 | HIGH-VAR |
| `EX-0012.08` | `[0.52, 0.00, 0.29]` | 0.00 | 0.52 | HIGH-VAR |
| `IMP-0003` | `[0.94, 0.11, 0.71]` | 0.11 | 0.94 | HIGH-VAR |

A class reaching 0.80 on one spacecraft run and 0.00 on another is not information-limited —
it is **instance-limited**. A single contaminated instance is already **ruled out**: zero-F1
folds distribute across all three instances (**9 / 6 / 6** of 26 classes).

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
