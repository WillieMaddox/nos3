# AINOS3-80 — Metric provenance audit 🔖

**Ticket:** AINOS3-80 · **Sprint:** 27 · **Date:** 2026-08-11 · **Type:** Spike

**Why:** the incident-label accuracy sat at an in-sample **76.9 %** for two months before
being corrected to the honest out-of-fold **42.3 %**. This audit sweeps every other
published number for the same trap and tags each with its provenance.

**Result:** **2 material findings, 1 minor.** Most headline numbers survive the audit —
but one documented methodology claim is false, and the deployed anomaly detector's
training corpus is unrecorded, which makes some claims *unverifiable* rather than wrong.

---

## The provenance vocabulary

Four tags, used from here on:

- **`[OOF]`** — out-of-fold. Measured on data held out of the fit that produced the
  prediction (leave-one-instance-out, or a held-out calibration split).
- **`[live-soak]`** — measured on independently collected nominal flight data, never used
  in any fit.
- **`[in-sample]`** — measured on data the model was fitted on. Optimistic by
  construction; must never be presented as operational.
- **`[design-target]`** — a parameter the system was *configured* to hit, not a
  measurement of whether it hits it.

---

## Findings

### F1 — MATERIAL: the IF threshold is calibrated **in-sample**, and the doc says otherwise

`V5_DETECTOR_COVERAGE.md` §D asserts:

> Incident detection is IF-gate-driven and already honest (the threshold is calibrated on
> **held-out** nominal).

**That claim is false.** The calibration artifact's row counts are *identical* to the
model's training row counts, in all four modes:

| Mode | IF train rows | Calibration rows | Same? | `actual_fp_rate` |
|---|--:|--:|:--:|--:|
| MODE_BDOT | 296 | 296 | ✅ | 0.01014 |
| MODE_INERTIAL | 19,641 | 19,641 | ✅ | 0.00998 |
| MODE_PASSIVE | 14,367 | 14,367 | ✅ | 0.01002 |
| MODE_SUNSAFE | 53,094 | 53,094 | ✅ | 0.01000 |

(`iforest_per_mode_v5_invariant_bolstered.pkl::n_train_rows_per_scenario` vs
`…calibration.json::diagnostics[*].n_rows`.) An independent nominal corpus matching the
training set to the row in all four modes is not plausible; the threshold was picked as
the 1 % quantile of the model's **own training scores**. `actual_fp_rate ≈ 0.0100` is
therefore a fitted quantile — it is true by construction and measures nothing.

**How much does it matter?** ⚠ **Amended 2026-08-11 after the AINOS3-81 soak — the first
version of this finding was too generous.** It originally read that the threshold
"generalised conservatively and the operational claim stands." A 7 h fresh-launch soak run
hours later measured the in-sample target against live nominal per mode:

| Mode | in-sample calib FP | measured raw FP | ratio |
|---|--:|--:|--:|
| BDOT | 0.0101 | 0.0000 | 0.0× |
| **INERTIAL** | 0.0100 | **0.0753** | **7.5×** |
| PASSIVE | 0.0100 | 0.0002 | 0.0× |
| SUNSAFE | 0.0100 | 0.0094 | 0.9× |

Conservative for BDOT / PASSIVE / SUNSAFE — **optimistic by 7.5× for INERTIAL**, whose
operational (post-hysteresis) FP of 0.54 % is 27× the documented band and against a
documented value of 0.00 %. Only SUNSAFE, with by far the most training rows (53,094),
lands where the calibration promised. So the in-sample calibration is not a documentation
nit: it produced a materially wrong threshold in one of four modes, and hysteresis has been
silently absorbing the error. See [`AINOS3_81_HYBRID_DRIFT_SOAK.md`](AINOS3_81_HYBRID_DRIFT_SOAK.md).

**Fix applied:** the "held-out" sentence is corrected in `V5_DETECTOR_COVERAGE.md`, and
"calibrated at 1 % FP" is retagged `[design-target]` rather than presented as a measured
rate. The soak numbers remain the authority and are tagged `[live-soak]`.

### F2 — MATERIAL: the deployed IF's training corpus is **unrecorded**

`iforest_per_mode_v5_invariant_bolstered.pkl` stores `n_train_rows_per_scenario`,
`schema`, `config`, and score statistics — but **no record of which data it was trained
on**: no CSV directory, no manifest list, no file identifiers, no collection dates. No
document in the repo records the `train.py` invocation either; the only description is a
prose comment in `nos3_security.ini` ("the 11-baseline v5 corpus + bolstered PASSIVE
manifest").

**Consequence:** for any metric measured against a corpus, we **cannot verify** that the
IF's nominal training rows are disjoint from it. That affects the per-technique catch
rates and the incident-recall figures. The circumstantial evidence favours disjointness —
the training data is described as dedicated *baseline* runs rather than attack runs, and
the row counts (87,398 total) don't match the frozen attack corpus (206,373) — but
"probably disjoint" is not a provenance record.

This is **not** a claim that those numbers are wrong. It is a claim that they are
currently **unfalsifiable**, which for a detector we are asking stakeholders to trust is
its own problem.

**Recommended fix (ticket it):** persist training inputs in the model artifact, exactly as
the classifier already does — `xgb_attack_classifier_v3_hybrid.pkl::config` records
`n_instances_per_class: 3` and `training_dates: [2026-05-16, 2026-05-29_batch1,
2026-05-29_batch2]`. The IF should carry the same. Until then, any re-derivation of the
IF requires re-collecting a baseline corpus from scratch.

### F3 — MINOR: headline hybrid LOIO accuracy is quoted 0.001 high

`V5_DETECTOR_COVERAGE.md` quotes the deployed hybrid at **0.646**; the artifact records
`loio_accuracy_mean: 0.6453` (folds 0.6913 / 0.6405 / 0.6042, std 0.0357), which rounds to
**0.645**. Trivial in magnitude, but it is a headline number and the fix is free.

Note the fold spread deserves more prominence than the mean does: **±0.036 across three
instances** means the difference between the hybrid (0.645) and the v3 global head (0.627)
is smaller than the instance-to-instance variation. The paired-fold comparison is still
valid — the same folds were used for both — but the *absolute* figure should always be
quoted with its spread.

### F4 — the uncertainty estimate is part of the provenance

New this sprint, from AINOS3-30: a metric can be correctly out-of-fold while its **error
bar** resamples the wrong thing. Bootstrapping the test rows of a single-instance corpus
gave a `+0.0270` block effect with a 95 % CI of `[+0.0167, +0.0373]` that excluded zero;
re-fitting across five train/test split points showed the same effect **flipping sign**
(std 0.0365 > mean 0.0216). The bootstrap CI was ~3× too narrow because it held fixed the
two things that actually vary — which rows train, and which instance produced them.

**Convention consequence:** a provenance tag on a point estimate is not sufficient. An
interval must state *what was resampled*, and resampling test rows is nearly always the
wrong answer for this project's corpora.

---

## Metric-by-metric register

### `V5_DETECTOR_COVERAGE.md`

| # | Metric | Value | Provenance | Verdict |
|---|---|---|---|---|
| 1 | Per-mode FP (SUNSAFE / PASSIVE / BDOT / INERTIAL) | 0.20 / 0.00 / 0.00 / 0.00 % | `[live-soak]` | ⚠ **INERTIAL does not reproduce** — AINOS3-81 measures 0.54 %. The other three reproduce or improve. |
| 2 | Long-uptime FP (6.6 h SUNSAFE) | 0.01 % | `[live-soak]` | ✅ honest |
| 3 | "Tuned to ≤ 1 % false-alarm rate" | 1 % | `[design-target]` | ⚠ **F1** — was implied to be measured; it is a configured target calibrated in-sample |
| 4 | Per-technique catch rate (SUNSAFE table, 15/23 ≥ 50 %) | various | `[unverifiable]` | ⚠ **F2** — attack rows are certainly unseen (the IF trains on nominal only), but training-set disjointness cannot be confirmed |
| 5 | Frame-level detection | ~61 % | `[unverifiable]` | ⚠ **F2**, same basis |
| 6 | Incident recall — detectable state-change | 92.8 % (77/83) | `[unverifiable]` | ⚠ **F2**, same basis |
| 7 | Incident recall — all techniques | 67.8 % (78/115) | `[unverifiable]` | ⚠ **F2**, same basis |
| 8 | Incident **label** accuracy | 42.3 % | `[OOF]` | ✅ honest — the Sprint-26 correction; v3 global head 34.6 % on identical folds |
| 9 | Technique-identification top-1 | 0.646 → **0.645 ± 0.036** | `[OOF]` | ⚠ **F3** — rounding, and the spread should travel with it |
| 10 | v3 global-head baseline | 0.627 | `[OOF]` | ✅ matches `cluster_taxonomy.json` (0.6274) |
| 11 | Cluster-granularity lift | 0.627 → 0.660 | `[OOF]` | ✅ matches artifact |
| 12 | Macro-F1 technique / cluster | 0.301 → 0.339 | `[OOF]` | ✅ matches artifact |
| 13 | Per-mode calibration ECE | ~10× tighter | `[OOF]` | ✅ held-out — artifact records `n_eval = n/2` per mode |
| 14 | Per-mode heads gain (INERTIAL/SUNSAFE +0.06, ROBUST +0.10) | | `[OOF]` | ✅ paired folds |
| 15 | Frame-level per-mode cluster-acc (PASSIVE 0.148 worst) | | `[OOF]` | ✅ honest; already carries its "two views must not be confused" caveat |
| 16 | "766 false incidents" | 766 | `[in-sample]`-ish | ✅ already explicitly caveated as *not* the operational rate |
| 17 | Mode-switch blind window | ~124 s → ~36 s transient | `[live-soak]` | ✅ measured over a 36-switch nominal soak |
| 18 | Per-leaf SPARTA split | 42 / 26 / 0 / 109 = 177 | `[census]` | ✅ a count, not a model metric |

### Coverage overlay (`app/nos3_coverage.js`, `app/sparta_coverage.html`)

| Metric | Provenance | Verdict |
|---|---|---|
| Per-technique `label_ok` | `[OOF]` (hybrid rescore) | ⚠ correct source, **but the artifact displays no provenance label at all** — grepping the generated JS and HTML returns zero occurrences of "out-of-fold", "in-sample", or "live-soak" |
| `incident_recall_headline` | `[unverifiable]` per **F2** | as above |

**Fix applied:** `gen_nos3_coverage.py` now emits a `provenance` block into
`NOS3_COVERAGE_META`, so the numbers carry their tags into the rendered overlay.

---

## The convention (added to `V5_DETECTOR_COVERAGE.md`)

> **Provenance convention.** Every metric in this document carries a tag: `[OOF]`
> out-of-fold · `[live-soak]` independent nominal flight · `[in-sample]` measured on
> fitted data · `[design-target]` a configured parameter, not a measurement. An untagged
> number is a bug. Intervals must state what was resampled — resampling test rows alone
> understates uncertainty on a single-instance corpus.

---

## Follow-ups to ticket

1. **Record IF training provenance** (from **F2**) — persist the csv-dir / manifest list /
   collection dates into the model pickle, mirroring the classifier's `training_dates`.
   Until this exists, findings 4–7 stay `[unverifiable]`.
2. **Re-derive the IF threshold on held-out nominal** (from **F1**) — split the baseline
   corpus, calibrate on the held-out half, and confirm the threshold lands near the
   current one. Cheap, and converts a `[design-target]` into a real measurement.
3. **Quote 0.645 ± 0.036, not 0.646** (from **F3**) — done in the doc; keep the spread
   attached in the stakeholder rollout (AINOS3-76).
