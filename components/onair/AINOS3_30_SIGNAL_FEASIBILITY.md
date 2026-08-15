# AINOS3-30 — Signal-adding feasibility: **NO-GO (documented NULL)** 📉

**Ticket:** AINOS3-30 · **Sprint:** 27 · **Date:** 2026-08-11 · **Type:** Story (spike-shaped)

**Question:** before committing to a retrain, does any recorded-but-unused Section-B MID
add discrimination for the weak-label classes?

**Answer:** **No — not measurably, on a single-instance corpus.** No candidate block's
contribution is distinguishable from the noise introduced by moving the train/test split.
The ticket explicitly allows a NULL as a valid outcome; this is one. **No retrain is
recommended from this evidence.**

---

## What was collected

`scenarios/run_attack_batch.py --input scenarios/batch_ainos3_30_weakclass.json` —
17 attacks, 17/17 exit 0, ~520 s each, full `make stop` + `launch-quiet` between runs,
`all_modes_dwell` bracketing. 2026-08-11 00:42Z → 03:25Z.

- **41,434 labeled rows**, 18 attack classes + 21,270 nominal
- Live schema **359 kept columns** (382-field schema, 23 excluded), sha256 `b83648dd…`
- Frozen `csv_corpus_v3stage` is **250 columns** → **109 added, 0 removed** (strict superset)
- Staged at `data/onair/csv_ainos3_30_s27/` + `data/onair/scenarios_ainos3_30_s27/`

Attack selection was driven by measured per-class F1 in `cluster_taxonomy.json`, not by
guesswork: 6 DEAD (F1 = 0.000), 3 NEAR-DEAD (< 0.07), 5 HIGH-VARIANCE, and **3 ROBUST
anchors** for contrast — without anchors a weak-class-only corpus makes per-class accuracy
uninterpretable.

---

## Candidate blocks

The 109 added columns, grouped by owning subsystem:

| Block | Cols | Feature slots | Rationale |
|---|--:|--:|---|
| `INGRESS` | 10 | 20 | `CI.*` + `TO.*` — the command-ingest family flagged by the AINOS3-82 Fayyaz benchmark |
| `SENSOR_HK` | 35 | 80 | Per-sensor app HK (CSS/FSS/IMU/MAG/ST/TORQUER) |
| `SENSOR_DEV` | 18 | 46 | Raw `*_DEV` device packets |
| `CDH` | 40 | 338 | DS + FM + LC |
| `TBL` | 6 | 12 | CFE_TBL change-detect — **known NULL**, included as a negative control |

Method: **one** feature matrix (41,434 × 1,412); every arm is a column subset of it, so the
remaining features are byte-identical across arms and the row split is the same partition
everywhere. The delta is attributable to the block and nothing else.

---

## Results

Baseline (916 slots, frozen-schema columns only) at `train_frac=0.7`:
**acc 0.6231 / macro-F1 0.5261**

| Arm | Δ acc | Δ macro-F1 |
|---|--:|--:|
| `+INGRESS` | −0.0001 | +0.0030 |
| `+SENSOR_HK` | +0.0038 | +0.0268 |
| `+SENSOR_DEV` | +0.0029 | +0.0168 |
| `+CDH` | +0.0012 | +0.0078 |
| `+TBL` | **+0.0000** | **+0.0000** |
| `+ALL` | +0.0071 | +0.0159 |

**The negative control passed.** `TBL` reproduced the Sprint-25 NULL to four decimals,
confirming the harness can detect "no information" rather than manufacturing a delta.

### The noise band — and why the first two attempts at it failed

**Attempt 1 — seed sweep. Dead instrument, discarded.** Varying `random_state` over 5 seeds
returned **±0.0000 on every arm**. That is not stability: `HistGradientBoostingClassifier`
with `early_stopping=False` is deterministic at 29k training rows (below sklearn's 200k
binning-subsample threshold), so every "seed" fit the identical model. Reporting that zero
as evidence of stability would have manufactured false confidence. The flag is retained in
the script with a docstring explaining why it is inert, so it is not re-tried.

**Attempt 2 — test-set bootstrap. Real, but measures the wrong term.** 400 resamples of the
test rows, model and split held fixed:

| Arm | macro-F1 | 95 % CI | Δ vs baseline | Δ 95 % CI |
|---|--:|---|--:|---|
| baseline | 0.5254 | [0.5113, 0.5388] | — | — |
| `+SENSOR_HK` | 0.5524 | [0.5376, 0.5657] | **+0.0270** | [+0.0167, +0.0373] |
| `+ALL` | 0.5415 | [0.5289, 0.5552] | **+0.0161** | [+0.0068, +0.0244] |

Both CIs **exclude zero** — which looks like a clean win, and is a trap. Resampling test
rows holds constant the two things that actually vary: which rows trained the model, and
which collection instance produced them.

**Attempt 3 — split sweep. The instrument that answers the question.** Refit at
`train_frac ∈ {0.60, 0.65, 0.70, 0.75, 0.80}`, which resamples *which rows train*:

| train_frac | baseline | `+SENSOR_HK` | `+ALL` |
|---|--:|--:|--:|
| 0.60 | 0.3992 | 0.4824 | 0.4925 |
| 0.65 | 0.5443 | 0.5707 | 0.5706 |
| 0.70 | 0.5261 | 0.5529 | 0.5420 |
| 0.75 | 0.5267 | 0.5007 | 0.5266 |
| 0.80 | 0.5615 | 0.5593 | 0.5986 |

Delta vs baseline, per split:

| Arm | 0.60 | 0.65 | 0.70 | 0.75 | 0.80 | mean | std | |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| `+SENSOR_HK` | +0.0832 | +0.0264 | +0.0268 | −0.0260 | −0.0022 | +0.0216 | 0.0365 | **sign flips** |
| `+ALL` | +0.0933 | +0.0263 | +0.0159 | −0.0001 | +0.0371 | +0.0345 | 0.0319 | **sign flips** |

**Both arms flip sign, and in both cases the standard deviation exceeds the mean.** The
bootstrap CI of [+0.0167, +0.0373] was roughly **3× too narrow** — it excluded zero only
because it never varied the thing that matters.

The baseline itself swings **0.3992 → 0.5615** (16 points of macro-F1) purely from moving
the cut point. At that level of instability the corpus cannot resolve a 2-point block
effect, and the large bidirectional per-class swings (`EX-0014.03` +0.315 against
`DE-0003.09` −0.222, on test supports of 65–98 rows) are split artifacts, not signal.

---

## Per-block verdicts

| Block | Verdict |
|---|---|
| `TBL` | **NULL, confirmed.** +0.0000 exactly. Reproduces Sprint-25. Stays dormant. |
| `SENSOR_HK` | **Not shown.** Largest nominal delta, but sign-flips across splits (std 0.0365 > mean 0.0216). |
| `SENSOR_DEV` | **Not shown.** Smaller than `SENSOR_HK`, same noise band. Prior expectation (redundant with the fused `ADCS_DI` view) is not contradicted. |
| `CDH` | **Not shown.** +0.0078 on 338 added slots — the worst signal-per-feature of any block. |
| `INGRESS` | **UNTESTED — not refuted.** See below. |

### `INGRESS` could not be tested by this corpus

All 10 `CI.*` / `TO.*` columns are **numerically constant 0** across all 41,434 rows
(`TO.usMsgSubCnt` is constant 50). Three findings, in order of how much they were nearly
got wrong:

1. A first census called these columns "live" because it compared **raw strings**, where
   OnAIR's not-yet-sampled placeholder `'[0]'` reads as a second distinct value. Artifact.
   Numeric coercion is the correct test.
2. A suspected AINOS3-72 recording regression is **refuted**:
   `message_headers.py::TO_HkTlm_t` matches `fsw/apps/to/fsw/src/to_hktlm.h` field-for-field,
   and `usMsgSubCnt` reads a plausible 50, so the struct parses correctly.
3. The actual explanation: the full `to`/`ci` apps are **idle by design** in this stack —
   commands flow via `:5012` and telemetry via SBN, neither of which touches full-TO's
   routes. The all-zero baseline is exactly the *static-in-nominal* precondition R12/R13
   were built on, so it **corroborates** AINOS3-72 rather than contradicting it.

The real limitation: **no attack in this corpus commands the full TO/CI apps.**
`EXF-0003.02` is the one that does and it was not in the weak-class list. The
Fayyaz-derived ingress hypothesis therefore remains open.

---

## Provenance of these numbers — READ BEFORE QUOTING

Every technique in this corpus executes **exactly once**, so leave-one-instance-out is
impossible and the absolute accuracies are **within-instance, single-run** figures:
optimistic, and **not comparable** to the LOIO out-of-fold numbers in
`V5_DETECTOR_COVERAGE.md` (deployed hybrid 0.646). That the baseline's 0.6231 sits near the
LOIO 0.627 is a **coincidence**, not agreement.

Only the arm-to-arm deltas were ever the deliverable, and the split sweep shows even those
are not resolvable at this corpus size.

Tags: split-sweep and bootstrap figures are **within-instance**; the `V5_DETECTOR_COVERAGE.md`
figures they must not be mixed with are **LOIO out-of-fold**. Feeds AINOS3-80.

---

## Recommendation

1. **No retrain.** No block earns a place in the feature vector on this evidence.
2. **`TBL` stays dormant.** Second independent NULL. The AINOS3-68 (DeepSAD) gate stays
   uncleared — this spike was its trigger condition and did not fire.
3. **Collect a second instance before re-running (AINOS3-45).** This is the binding
   constraint, not feature design. With ≥ 2 instances, LOIO becomes possible and the noise
   band shrinks to something that can resolve a 2-point effect. The tooling is now a
   re-invocation: same batch JSON, same ablation script.
4. **Test `INGRESS` properly** by including `EXF-0003.02` (and any technique that commands
   full TO/CI) in the next corpus. Until then the Fayyaz ingress lead is open, and it is
   still the most promising one — it is the only hypothesis backed by an independent group's
   result on the same simulator.
5. **AINOS3-69's standing conclusion holds.** The binding constraint is **observability, not
   model capacity** — and now also **corpus size**. Adding 109 recorded columns to the
   feature vector changed nothing measurable; what is missing is attacks that move them and
   instances that let us tell.

### Incidental findings

- **15 of 109 added columns are constant** across the corpus: all 6 `CFE_TBL` (known), 4
  `TORQUER` (`CommandErrorCount`, `DeviceEnabled`, `DeviceErrorCount`, `TorquerPeriod`), and
  5 `ST_DEV` star-tracker fields (`IsValid`, `Q0`–`Q3`). The star-tracker quaternions being
  inert is worth a separate look — that is an ADCS-relevant sensor reporting nothing.
- **AINOS3-83 partially answered.** Its first AC asks whether a full-`ci` command-ingest
  counter moves under `:5012`-injected commands. Across 17 attacks and 41,434 frames:
  **no**. That points its remaining work at "document the bypass and close out-of-scope,"
  unless genuine ground-link commanding is tested separately.

---

## Reproduce

```bash
# corpus (~2.7 h, restarts the stack 17 times)
python3 components/onair/training/scenarios/run_attack_batch.py \
  --input components/onair/training/scenarios/batch_ainos3_30_weakclass.json \
  --out data/onair/batch_ainos3_30_weakclass_results.json

# ablation + both noise instruments (~66 min)
~/.virtualenvs/nos3/bin/python components/onair/training/ablation_ainos3_30_s27.py \
  --split-sweep 0.6,0.65,0.7,0.75,0.8 --bootstrap 400 \
  --sweep-arms baseline,baseline+SENSOR_HK,baseline+ALL \
  --out-json data/onair/models/ablation_ainos3_30_s27.json
```
