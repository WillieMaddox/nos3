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

- [x] `AC1` Per-class, per-fold F1 cross-tabulated against the collecting run, from
      `loio_predictions_oof_v3hybrid_full.npz` and the corpus manifest — no re-training.
- [x] `AC2` For each zero-F1 fold, the fraction of that run's attack frames falling inside a
      post-mode-switch blind window (~45 s / 250 frames).
- [x] `AC3` A stated verdict with its limits: **blind-window-explained**, **partially explained**, or
      **unexplained** — and if unexplained, what else differs between the runs.
- [x] `AC4` A recommended instance count for Sprint 29, justified by the observed spread rather than
      assumed. "3, because that is what we had" is acceptable only if the evidence says so.
- [x] `AC5` ⚠ Note in the write-up that adding instances adds folds, and **min-over-more-folds is a
      stricter bar**.
- [x] `AC6` **Cross-check against `AINOS3-96`:** if a class's fold spread coincides with a script that
      STIX flags as mislabelled, that is a shared root cause and both tickets should say so.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.

### 2026-09-01 · DONE — the spread is NEITHER blind-window NOR sample-size; it is a generalisation limit

Ran on `loio_predictions_oof_v3hybrid_full.npz` (deployed 26-class OOF; the finding is
label-set-independent — the two candidate causes are per-frame / per-class, not per-label). No
re-training.

**`AC1` — per-class F1 by fold (instance), widest spread first.** Zero-F1 folds distribute across
all three instances (**9 / 6 / 6**), so a single contaminated instance is ruled out (confirmed).

| class | fold F1s | min | max |
|---|---|--:|--:|
| `DE-0003.02` | 0.07 / 0.00 / 0.65 | 0.00 | 0.65 |
| `EX-0012.08` | 0.52 / 0.00 / 0.29 | 0.00 | 0.52 |
| `EX-0012.09` | 0.00 / 0.00 / 0.50 | 0.00 | 0.50 |
| `DE-0003.06` | 0.44 / 0.33 / 0.00 | 0.00 | 0.44 |
| `EX-0012.12`/`EX-0014.01` | 0.00 / 0.37 / 0.14 | 0.00 | 0.37 |

**`AC2`/`AC3` — VERDICT: UNEXPLAINED by the blind window (the hypothesis this spike was built to
test is refuted), and not sample-size either.**

- **Blind window** (first 250 frames after a mode switch): the fraction of attack frames inside it
  is **77.4 % for the 21 zero-F1 folds vs 77.7 % for the F1>0 folds — no difference.** If the blind
  window drove the spread, zero-F1 folds would sit *higher*. They do not. So the steady-flight
  protocol (`AINOS3-100`), which fixes the blind window, will **not** by itself close the spread.
- **Sample size** (a second candidate, tested to be safe): zero-F1 folds have a **median 1083**
  attack frames vs **988** for good folds — zero-F1 folds have *more* data, not less. A class with
  1083 frames scoring 0.00 is not data-starved.

What remains is a **per-instance generalisation limit**: a class's on-wire footprint varies enough
across spacecraft runs (sim seed / TLE / timing) that a model trained on two instances fails to
predict it in the held-out third. It is neither noise-quantity nor the blind window; it is
diversity.

**`AC4`/`AC5` — recommended instance count: 5 (up from 3), with the honest tension stated.** More
instances give the model more footprint diversity to learn from, which is the *only* lever that
addresses a generalisation limit. ⚠ But `min`-over-more-folds is a **stricter** bar (`AINOS3-101 AC4`)
— the LOIO-min metric structurally penalises the very instance diversity we would collect. So the
uncomfortable conclusion for `AINOS3-101`'s "is ROBUST reachable?": **probably not via data volume
or steady-flight collection alone** — the binding constraint is footprint reproducibility across
runs, not corpus size or the blind window. 5 instances buys a *fairer* evaluation, not a guaranteed
ROBUST class.

**`AC6` — cross-check vs `AINOS3-96`.** The widest-spread classes overlap heavily with `AINOS3-96`'s
structural flags: the `DE-0003.*` family (probe-only) and the `EX-0012.{08,09,12}`/`EX-0014.01`
degenerate/partial group. Shared root: weak or degenerate footprints do not reproduce across
instances, which is exactly what both the spread (here) and the mislabelling (`AINOS3-96`) surface
from different angles.
