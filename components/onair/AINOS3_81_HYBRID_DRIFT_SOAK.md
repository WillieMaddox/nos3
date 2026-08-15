# AINOS3-81 — Hybrid drift soak: **no drift, but an INERTIAL false-positive regression** ⏱️

**Ticket:** AINOS3-81 · **Sprint:** 27 · **Date:** 2026-08-11 · **Type:** Task

**Run:** fresh `make stop` + `launch-quiet` at 06:04Z, four sequential ADCS-mode legs,
**7 h 00 m**, all legs exit 0. 140,631 frames. Side files
`*_2026-08-11T06-05-26_pid11.csv`. Deployed models confirmed loaded at startup:
`selective per-mode hybrid (AINOS3-37): 2 per-mode head(s) for ['MODE_INERTIAL',
'MODE_SUNSAFE']; global head for all other modes; 4 calibrated mode(s)`.

SUNSAFE ran last and longest by design, putting its window at roughly **uptime T+3h → T+7h**
— the band where the invalidated v2 detector was suspected of drifting.

---

## Headline

| Question | Answer |
|---|---|
| Does the deployed hybrid drift over a long soak? | **No.** SUNSAFE margin *widens* with uptime. |
| Does per-mode FP hold in the documented 0.0–0.2 % band? | **No — INERTIAL is out**, at 0.54 %. |
| Do the parallel gates hold 0-FP? | **Effectively yes** — 2 rule-gate edges in 7 h; staleness and consistency clean. |
| Does the classifier mislabel nominal as an attack? | **No.** 0 false attack labels in 2,203 gated frames. |

---

## 1. Drift — PASS

`analyze_soak_drift.py`, 30-min bins, first 2 min of each mode dropped (mode-entry transient).

**SUNSAFE, 4 h leg** (`alert` = operational FP, post-warmup + hysteresis):

| Window | frames | raw_fp | alert_fp | score_p01 |
|---|--:|--:|--:|--:|
| T+0–30 | 10,080 | 0.0290 | 0.0001 | −0.0592 |
| T+30–60 | 10,080 | 0.0001 | 0.0000 | 0.0610 |
| T+60–90 | 10,080 | 0.0000 | 0.0000 | 0.0522 |
| T+90–120 | 10,080 | 0.0000 | 0.0000 | 0.0522 |
| T+120–150 | 10,080 | 0.0000 | 0.0000 | 0.0592 |
| T+150–180 | 10,080 | 0.0280 | 0.0006 | −0.0305 |
| T+180–210 | 10,080 | 0.0000 | 0.0000 | 0.0803 |
| T+210–240 | 10,080 | 0.0000 | 0.0000 | 0.0856 |

**overall alert_fp = 0.0001 · NO DRIFT.** The 1st-percentile score margin does not merely
plateau — it **rises** from 0.052 to 0.086 across the leg, i.e. the detector moves *away*
from its threshold as uptime accumulates. Two brief raw excursions (leg entry, and one at
T+150–180) both self-recover and are suppressed to ≤0.06 % by hysteresis.

This reproduces the 2026-06-09 v5 result (6.6 h, 0.01 %, no progressive climb) and extends
it to the deployed hybrid. **The v2 long-uptime drift pathology remains closed.**

BDOT and PASSIVE are flat at 0.0000 alert FP across their legs.

---

## 2. Per-mode false positives — INERTIAL FAILS the documented band

| Mode | frames | raw FP | **alert FP** | doc claims | verdict |
|---|--:|--:|--:|--:|---|
| BDOT | 20,851 | 0.0000 | **0.0000** | 0.00 % | ✅ reproduces |
| PASSIVE | 19,897 | 0.0002 | **0.0000** | 0.00 % | ✅ reproduces |
| SUNSAFE | 80,742 | 0.0094 | **0.0002** | 0.20 % | ✅ better than documented |
| **INERTIAL** | 19,300 | **0.0753** | **0.0054** | **0.00 %** | ❌ **does not reproduce** |

INERTIAL's operational FP is **0.54 %** — under the 1 % design target, but **27× the
documented 0.0–0.2 % band's upper bound**, against a documented value of 0.00 %.

**It is not drift.** Across the leg, alert FP goes 0.0063 (T+0–30) → 0.0044 (T+30–60) —
flat-to-declining. This is a **steady-state level**, not a trend.

### Root cause: the INERTIAL threshold is mis-calibrated

This is AINOS3-80 **F1** (the threshold is calibrated in-sample on the model's own training
scores) showing up as a measured consequence:

| Mode | threshold | in-sample calib FP | this soak's raw FP | ratio |
|---|--:|--:|--:|--:|
| BDOT | −7.04e-03 | 0.0101 | 0.0000 | 0.0× |
| INERTIAL | −2.15e-05 | 0.0100 | **0.0753** | **7.5×** |
| PASSIVE | −5.00e-05 | 0.0100 | 0.0002 | 0.0× |
| SUNSAFE | −2.46e-05 | 0.0100 | 0.0094 | 0.9× |

The in-sample calibration promised 1 % raw FP in every mode. Live nominal delivers 0 %,
7.5 %, 0 %, 0.9 %. Only SUNSAFE — the mode with by far the most training rows (53,094) —
lands where the calibration said it would.

**⚠ This corrects a claim in the AINOS3-80 audit.** That audit concluded the in-sample
threshold "generalised conservatively." That holds for BDOT, PASSIVE and SUNSAFE, and is
**false for INERTIAL**, where it is optimistic by 7.5×. The audit has been amended.

---

## 3. Incident-level false alarms — the operational impact

Every incident in a nominal soak is a false alarm. 81 were raised, all labelled
`cluster=nominal`:

| Mode | false incidents | per hour |
|---|--:|--:|
| BDOT | 0 | 0.0 |
| PASSIVE | 0 | 0.0 |
| SUNSAFE | 10 | 2.5 |
| **INERTIAL** | **71** | **71.0** |

The coverage doc's operational promise is *"Will it cry wolf? Rarely — under 1 alarm per
~5 hours of nominal flight."* In SUNSAFE that is off by ~12×; **in INERTIAL it is off by
~355×**. Median incident length is 9 frames (~1.6 s), so these are short bursts rather
than sustained alarms — but they are alarms.

The classifier labels all of them `nominal`, so a consumer that filters on
`cluster != nominal` sees none of them. Whether the deployed overlay/operator view does
that filtering is **not verified here** and should be checked before this is called benign.

---

## 4. Parallel gates — clean

| Gate | Result over ~141 K frames |
|---|---|
| staleness-check | **0** alerts |
| consistency-check | **0** violations |
| rule-gate | 25 frames of `R2:evs`, **2 edges** in 7 h |

The 2 R2 edges confirm the fresh-launch discipline works: on long-uptime stacks accumulated
RADIO EVS spam pins R2 open continuously. A fresh launch keeps it at 2 events in 7 hours.

---

## 5. Classifier + calibration behaviour

| Mode | frames | IF-gated → scored | mean `top1_prob` | min | false attack labels |
|---|--:|--:|--:|--:|--:|
| BDOT | 20,851 | 0 | — | — | 0 |
| INERTIAL | 19,299 | 1,454 | 0.999 | 0.986 | **0** |
| PASSIVE | 19,898 | 4 | 1.000 | 1.000 | **0** |
| SUNSAFE | 81,072 | 745 | 0.999 | 0.977 | **0** |

**All 2,203 gated frames were labelled `nominal`** — the classifier never invented an
attack during 7 h of nominal flight. Calibrated confidences sit in range and are correct,
though effectively **saturated at ~1.0**: on this data the calibration has no discriminative
headroom, so "confidence" carries no information beyond the label itself. That is expected
when every scored frame is genuinely nominal, but it means this soak does **not** exercise
the calibration's mid-range and should not be cited as evidence the calibration is
well-behaved under attack.

---

## 6. Tooling defect found

`analyze_soak_drift.py` defaults to `--hz 4.2`. Measured against legs of known wall-clock
duration, the true rate is **~5.6 Hz**:

| Mode | frames | leg seconds | Hz |
|---|--:|--:|--:|
| BDOT | 20,851 | 3,600 | 5.79 |
| INERTIAL | 19,300 | 3,600 | 5.36 |
| PASSIVE | 19,897 | 3,600 | 5.53 |
| SUNSAFE | 80,872 | 14,400 | 5.62 |

At 4.2 Hz the tool's uptime bins are mislabelled by ~33 % — a "T+30–60 min" bin actually
covers ~T+22–45 min. All figures above were produced with `--hz 5.6`. The default should be
corrected, or better, derived from the side file rather than assumed. (The coverage doc's
"~5 Hz" prose is right; the tool default is the stale value.)

---

## Verdict against the acceptance criteria

- ✅ **≥6 h fresh-launch soak; per-mode FP + calibrated-confidence distributions reported** — 7 h, all four modes.
- ✅ **No progressive drift** — confirmed, margin widens rather than shrinks.
- ❌ **FP in the measured 0.0–0.2 % band** — INERTIAL at 0.54 % (raw 7.5 %). *"If drift appears, ticket it"* — this is not drift but it is a reproducibility failure against a published number, so it is ticketed below.
- ✅ **Folded into the coverage doc** with provenance `[live-soak]`.

## Follow-ups to ticket

1. **Re-calibrate the INERTIAL threshold on held-out nominal** (high). Merges with
   AINOS3-80 follow-up 2. Current INERTIAL raw FP is 7.5× its calibration target; hysteresis
   is doing the work the threshold should. This is the single highest-value fix here.
2. **Correct the documented INERTIAL FP** (done below) — 0.00 % does not reproduce.
3. **Verify operator-facing filtering of `cluster=nominal` incidents** (medium) — 71
   false incidents/hour in INERTIAL is only benign if nothing surfaces them.
4. **Fix `analyze_soak_drift.py --hz`** (low) — derive the rate from the data.
5. **Re-soak INERTIAL after re-calibration** to confirm the fix.
