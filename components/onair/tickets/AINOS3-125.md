---
key: AINOS3-125
slug: blended-log-format
type: Story
epic: AINOS3-98 (corpus-integrity)
status: Backlog
priority: High
estimate: E 3 / T 1.0
opened: 2026-09-19
origin: AINOS3-101 (retrain-clean-corpus)
---

# AINOS3-125 — De-interleave OnAIR's double buffer into a single coherent stream

**Summary:** As an ML engineer, I want recorded telemetry expressed as one coherent stream instead of two interleaved buffer snapshots, so that delta features describe the spacecraft rather than the recorder, and so the corpus format is the one this project should have had from the start.

## Description

`sbn_adapter.DataSource` keeps two buffers. The listener thread writes each arriving
message into the *write* buffer, `currentData[(read_index + 1) % 2]`, and every frame
`get_next()` flips `read_index` and returns the other one. The two are never reconciled —
the upstream comment says so outright:

> "The double buffer does not clear between switching. If fresh data doesn't come in, stale
> data is returned (delayed by 1 frame)"

So each buffer is an independent, partially-stale snapshot and every CSV this project has
ever recorded is **two interleaved sub-streams**. Measured on the rebuild corpus: 49 of 454
non-constant columns alternate on >50 % of steady-state rows (`SCH.SlotsProcessedCount`
flips 1899 ↔ 2699 on 95.9 % of rows), and lag-1 deltas — what every model actually
consumes — carry **4–6× the noise** of same-buffer deltas.

⚠ **Parity subsampling is NOT the fix**, and measuring that mattered: on discrete
baseline fields, **55.6 %** of the novel values an attack produces appear in ONE parity
only, including values that persist for 47 frames. Keeping one sub-stream would discard
over half the footprint evidence.

The correct transform is per-buffer change detection: a field is news only when it changed
**against its own buffer's previous frame**; everything else carries forward. Each output
row is then the most recent *genuine* value from both sub-streams.

⚠ This ticket covers the **offline** transform and the corpus rebuilt through it. Changing
the live adapter is `AINOS3-126`, and re-tuning the gates that compensate
for the artifact is `AINOS3-127`.

## Acceptance criteria

- [x] `AC1` A converter that rebuilds one coherent stream by per-buffer change detection, with strict-alternation assumed and content-based buffer assignment run always as a CHECK (schema-v1 telemetry disagrees on 0.012 % of rows; older generations 0.17–0.21 %).
- [x] `AC2` ⚠ The `[0]` sentinel is WRITTEN for fields no buffer ever delivered but never ADOPTED over good telemetry. Both properties are required: four tools key on the literal sentinel and two fail **silently** on a blank — `build_corpus_manifest.py:177` scores `""` as 1 (uncontrolled) not 0 (no data), deflating the INERTIAL capture gate, and `analyze_inertial_fp.py:195` routes it to the UNCONTROLLED arm, corrupting the `AINOS3-86` FP figure.
- [x] `AC3` One recording generation at a time (`--schema-from`): `data/onair/csv` holds **11** distinct MID lists (250 … 479 columns) and blending across them is meaningless.
- [x] `AC4` The schema-v1 corpus converted — 148 files, 1,070,391 rows, all 113 `AINOS3-100` runs covered — with `.meta.json` sidecars carrying `derived_from` / `transform` provenance, and a blended corpus manifest (113 accepted, same rejections, same schema sha).
- [x] `AC5` ⚠ Plugin side-files (`attack_class_`, `iforest_out_`, `rule_gate_out_`, `consistency_out_`, `staleness_out_`, `incident_`) are deliberately NOT reproduced. They record live detector decisions on the interleaved frames and cannot be derived; regenerating them would let `attach_iforest_scores` and `analyze_inertial_fp` join fabricated history as if it were a live record.
- [x] `AC6` A guard so this class of defect cannot recur silently: `loader.list_clean_csvs` compares headers BETWEEN files (it only ever checked row alignment WITHIN one), keeps one schema, and counts the rest. Previously a bare `load()` over `data/onair/csv` outer-joined 11 generations into hundreds of fabricated zero columns and said nothing.
- [x] `AC7` The benefit measured rather than assumed, on all three consumers — see the Log.
- [ ] `AC8` ⚠ Decide and record whether the blended representation becomes the **canonical** corpus format. The evidence says yes on faithfulness and modestly on performance; that is a decision, not a measurement.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-09-19 · Built, and measured on all three consumers

#### In plain terms

Every log this project has recorded was really two interleaved snapshots taking turns, so
consecutive rows never described the same instant. A converter now rebuilds a single
coherent stream. It helps the classifier a little, the anomaly detector almost not at all,
and the rule gates not measurably — the honest read is that this is the format we should
always have had, not a performance unlock.

**Tooling:** `deinterleave_csv.py` (+ `--schema-from`, `--resume`, atomic `.part` writes),
`compare_if_blended.py`, `compare_gates_blended.py`, the `loader` schema guard with 6 tests.

**Classifier** (same 17-class label set, same v5 delta-only mask, same v3 hyper-parameters,
same 5 folds — only the input differs):

| | Interleaved | Blended |
|---|--:|--:|
| LOIO accuracy | 0.6128 | 0.6140 |
| macro-F1 technique | 0.3851 | **0.4192** |
| macro-F1 cluster | 0.5045 | **0.5401** |
| tiers R/S/H/D | 3 / 1 / 11 / 2 | 3 / 1 / 12 / **1** |

`EX-0008.01`/`.02` gain **+0.059** on their fold minimum (0.887 → 0.95), `EX-0012.08`
climbs DEAD → HIGH-VAR. ⚠ But `EX-0012.03`/`.04` lose **−0.108**, and the mean Δ across
all classes is **−0.008**: macro-F1 up, fold-minima slightly down, because the minimum is a
worst-fold statistic and blending changed which fold is worst.

**IF** (train on instances 1–4 nominal, hold out 5, matched 1 % FP budget): recall
**0.0086 → 0.0149**. Doubled, and meaningless — only `EX-0012.07` moved (0.067 → 0.182),
the one attack that perturbs physics. ⚠ **The predicted mechanism was wrong:** I expected
blending to TIGHTEN the nominal distribution; its spread widened (std 0.050 → 0.057). And
this corpus is the wrong test bed — 15 of 16 techniques are command/counter attacks
`AINOS3-121` already showed the IF is blind to.

**Gates** (real plugin classes replayed, not a reimplementation): rule_gate detection
0.5308 → 0.5365, noise. ⚠ `consistency_check` and `staleness_check` score 0.0000 in BOTH
arms — not a miss, but because the attacks they exist for (`EX-0014.02` bus spoof,
`EX-0012.02` route severing) are **absent from this corpus**. The gate leg is therefore
one gate unchanged and two untested. ⚠ Also: the 13.7 % rule_gate "FP" is an artifact of
the replay harness labelling prerequisite attacks as nominal, not a real false-alarm rate.

**Where that leaves it.** Blending is strictly more faithful and cost one script, so it
should be the corpus format. It is not the unlock — which is consistent with `AINOS3-69`:
the binding constraint is observability, not signal cleanliness.
