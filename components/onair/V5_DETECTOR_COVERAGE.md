# NOS3 OnAIR Security Monitor — What It Catches / What It Doesn't

**Audience:** mission, security, and program stakeholders (no ML background assumed).
**Scope:** the v5 anomaly detector + v3 attack classifier currently deployed in
the OnAIR plugin against the NOS3 cFS flight software.
**Last updated:** 2026-06-09. Numbers are from attack scripts empirically
validated against live FSW (31 SPARTA entries) and from calibrated nominal
soaks — not from simulation assumptions.

---

## Bottom line

The monitor is a **two-stage on-board sentry** watching ~250 spacecraft
telemetry fields at ~5 Hz:

1. **Stage 1 — "Is something wrong?"** A per-flight-mode anomaly detector
   (Isolation Forest) raises an alarm when telemetry leaves the envelope it
   learned from nominal flight. **Tuned to ≤ 1 % false-alarm rate; measured
   0.0–0.2 % in steady-state flight.**
2. **Stage 2 — "What kind of attack?"** When Stage 1 alarms, an attack
   classifier (gradient-boosted trees) labels the event with a SPARTA
   technique (e.g. *EX-0012.07 propulsion command*). **~63 % correct
   technique identification on novel runs.**

**What this means operationally:**

| Question | Answer |
|---|---|
| Will it cry wolf? | Rarely — under 1 alarm per ~5 hours of nominal flight. |
| Will it catch a real attack? | **Yes — at the incident level, 93 % of genuinely detectable state-change attacks raise an alert** (vs ~61 % of individual frames; one alert per attack is what matters). Detection is strongest in SUNSAFE; weaker in other modes. |
| Will it tell me *which* attack? | For ~8 techniques, yes with high confidence. For others it narrows to a *family* of indistinguishable techniques. A handful it cannot label at all (documented below). |
| Does Stage 2 catch things Stage 1 misses? | **No.** Stage 2 only *sharpens* what Stage 1 already flagged — it does not widen the net. |

---

## What it catches well

### 1. Nominal flight without false alarms (all four ADCS modes)

Every alarm during a known-nominal soak is, by definition, a false positive.
Measured steady-state false-positive rate (post warm-up + hysteresis):

| ADCS mode | False-alarm rate | Evidence |
|---|---|---|
| SUNSAFE | **0.20 %** | 855 K frames / 44 h soak |
| PASSIVE | **0.00 %** | 226 K frames / 8 h soak |
| BDOT | **0.00 %** | 47 K frames / 157 min soak |
| INERTIAL | **0.00 %** | 35 K frames / 116 min soak |

All four modes sit well under the 1 % design target. An earlier worry that
two modes (INERTIAL, BDOT) were "too noisy to use" was **disproved** — the
spikes were a ~2-minute transient right after a mode change, not steady drift.

**Long-uptime stability (6.6 h SUNSAFE soak, 2026-06-09).** A predecessor
detector (v2) was suspected of drifting to 50–97 % false alarms after 4–6 h of
continuous uptime. v5 does **not**: across 100 K frames / 6.6 h the operational
false-alarm rate stayed at **0.01 %**, with no progressive climb. The internal
anomaly-score margin settles during the first ~2 h then **plateaus** (1st-
percentile score holds ≈ 0.06–0.08 against a ~0 alarm threshold) — i.e. it
stops shrinking, rather than marching toward the threshold. One brief excursion
near T+6 h (0.4 % raw) self-recovered within minutes and was suppressed to
0.04 % by hysteresis. The long-uptime drift concern is considered **closed for
SUNSAFE**.

### 2. Attack detection — strong in SUNSAFE

In SUNSAFE mode, **15 of 23 state-changing techniques are caught ≥ 50 %** of
their corruption window, many at or near 100 %:

| Technique | Catch rate | Technique | Catch rate |
|---|--:|---|--:|
| EX-0012.07 propulsion | **100 %** | EX-0008.02 RTS | 91 % |
| EX-0012.08 ADCS | **100 %** | IMP-0005 destruction | 75 % |
| IMP-0003 denial | **100 %** | EX-0012.05 scheduler | 64 % |
| EX-0012.09 EPS | 99 % | EX-0012.04 app tables | 63 % |
| EX-0014.04 PNT spoof | 98 % | IMP-0006 theft | 62 % |
| EX-0014.03 sensor spoof | 91 % | IMP-0001 deception | 61 % |
| EX-0008.01 ATS | 91 % | IMP-0002 disruption | 58 % |
| EX-0012.12 system clock | 57 % | | |

### 3. Incident-level detection — the operational view

The percentages above are *frame-level* (what fraction of an attack's frames
were flagged). Operators don't act on frames — they act on **incidents** ("an
alert began at T and lasted N seconds"). The monitor now collapses a
hysteresis-confirmed run of flagged frames into one incident, and an attack
counts as caught if it raises **at least one** incident. Re-scoring the labeled
corpus at this granularity:

| Metric | Value |
|---|---|
| Incident recall — genuinely detectable state-change attacks | **92.8 % (77/83)** |
| Incident recall — all SPARTA techniques (incl. undetectable-by-design) | 67.8 % (78/115) |
| Incident label accuracy (of detected; **out-of-fold**) | **34.6 %** (in-sample was 76.9 %) |

**The jump from ~61 % (frame) to ~93 % (incident) is the whole point of the
incident layer:** even a brief burst of flagged frames during an attack raises
exactly one alert, so attacks that are "only" caught 60 % of their frames are
caught ~100 % of the time as *events*. The residual gap is the
structurally-undetectable techniques (Sections B & C), not tuning. Only four
detectable attacks miss in some runs (`DE-0003.09`, `EX-0012.04`/`.04-prereq`,
`EX-0012.08`).

> **False-alarm caveat — read this.** The corpus also produced 766 "false
> incidents," but that number is **not** the operational false-alarm rate. The
> attack corpus's nominal windows use a different command cadence
> (`all_modes_dwell` @ 30 s) than the detector's training baseline, which the IF
> flags heavily by construction. The real nominal false-alarm rate is the soak
> number — **0.01 %** (Section 1) — not the corpus number.

### 4. Attack identification — confidence tiers

When Stage 1 alarms, the classifier names the technique. Reliability varies by
technique, so we report it in tiers (measured by leave-one-instance-out
cross-validation — i.e. accuracy on a spacecraft run the model never saw):

- **ROBUST (trust the label):** `DE-0003.01`, `DE-0003.10`, `EX-0008.02`,
  `IMP-0005` — F1 ≥ 0.85 on every split.
- **STABLE-MID (good as a top-3 suggestion):** `IMP-0002`, `IMP-0003`,
  `IMP-0006`, plus the `nominal` label.
- **HIGH-VARIANCE (label is a hint, not a verdict):** `EX-0008.01`,
  `EX-0012.07/.08/.09`, `EX-0014.04` — correct on some runs, not others.
- **DEAD (cannot be labeled as-is):** see next section.

Overall technique-identification accuracy is **~63 %** (top-1, novel run) —
calibrated, not overfit (held-out and cross-validated numbers agree within
~1 point).

---

## What it does NOT catch (the honest limits)

### A. Detection is structurally tied to SUNSAFE mode

The other modes carry little attack signal in the current corpus. **Operational
alerts should be expected almost exclusively while the FSW is in SUNSAFE.** In
BDOT/PASSIVE/INERTIAL an attack may execute with little or no Stage-1 alarm.
This is the single most important operational caveat.

### B. Two kinds of "unlabelable" attacks — and they are different

The classifier has a set of DEAD techniques (F1 ≈ 0). Investigating *where*
their telemetry actually goes reveals **two distinct failure modes** that
matter differently:

1. **Sibling-ambiguous — telemetry-identical to another technique.** These
   are not really failures: two or more SPARTA sub-techniques produce the
   *same* on-board footprint, so asking the model to split them is asking the
   impossible. Derived empirically from the confusion matrix (two classes are
   clustered only when each one's frames land on the *other* — genuine mutual
   indistinguishability, not a rare class dumping one-way onto a reliable one):
   - `EX-0012.03` ≡ `EX-0012.04` ≡ `EX-0012.05` — propulsion / app-table /
     scheduler command family
   - `EX-0012.12` ≡ `EX-0014.01` — system-clock vs time-spoof

   **Fix (no model change):** report the *cluster* ("propulsion-command-class
   attack") instead of the exact sub-technique. Re-scoring the same model at
   this granularity lifts top-1 accuracy **0.627 → 0.660 (+3.3 pts)** and
   class-balanced macro-F1 **0.301 → 0.339**, with no retraining. The lift is
   modest because only two small command-injection families are genuinely
   indistinguishable — so the real value is **correct expectation-setting**
   (don't promise ".03 vs .04" resolution that the telemetry can't support),
   not a large metric bump.

2. **Nominal-ambiguous — no distinct on-board signal at all.** Techniques like
   `DE-0003.03/.08/.09`, `EX-0014.03`, `EX-0012.08` produce telemetry that
   looks like *nominal* flight. Clustering cannot help these — only better
   detection or subscribing to additional telemetry (MIDs deliberately pruned
   from the current feature set) would. These are genuine coverage gaps.

### C. Some attacks are structurally unobservable

By design, the monitor only sees the MIDs in `nos3_security_tlm.json`. A
4-class signal taxonomy describes what is and isn't observable:

| Signal class | Meaning | Examples |
|---|---|---|
| **ON_BOARD** | Visible — at least one watched field changes | IMP-0002/3/5, DE-0003.06/09/10 |
| **OBFUSCATION** | Real, but the attack hides itself (e.g. RESET zeroes the counter before the next HK packet); only an EVS event trail survives | IMP-0001, DE-0003.01/02/08 |
| **UNSUBSCRIBED** | Target subsystem's housekeeping is **not** monitored — on-board acknowledgement is structurally invisible | IMP-0006, DE-0003.03/11 |
| **CONCEPTUAL** | No-op / description-only technique — nothing to detect | DE-0003.04/05/07/12 |

UNSUBSCRIBED and CONCEPTUAL attacks are **out of scope** for telemetry-based
detection by construction, not by failure.

### D. Incident aggregation — built; label accuracy now measured out-of-fold

The monitor aggregates flagged frames into **incidents** (Section 3) — start,
duration, cluster, accumulated confidence — using the same hysteresis the IF
plugin uses for alerts. This lifted effective detection from ~61 % (frame) to
~93 % (incident).

Incident **detection** is IF-gate-driven and already honest (the threshold is
calibrated on held-out nominal). Incident **labelling** had only ever been
measured in-sample. Re-scoring the same `csv_corpus_v3stage` corpus with
leave-one-instance-out, out-of-fold predictions (NOS3-302) gives the honest
figure: **34.6 % label accuracy of detected attacks, versus 76.9 % in-sample** —
the in-sample number was more than 2× optimistic. Incident detection recall is
identical either way (78/115), exactly as expected: only the label source
changed, not the IF gate.

The label collapse is tier- and mode-dependent:
- **By tier** (coherent with §4): ROBUST clusters keep their labels out-of-fold
  (`EX-0008.02` 100 %, `IMP-0005` 100 %, the `IMP-0001/2/3/6` family ~67 %);
  HIGH-VARIANCE and DEAD clusters collapse (`EX-0012.08/.09`, `EX-0014.03/.04`
  → 0 %). The aggregate is dragged down by the many always-*detected*-but-not-
  *labelable* HIGH-VAR attacks.
- **By mode** — two views that must not be confused:
  - *Incident-level* (attack attributed to its **first** corruption-frame's
    mode): PASSIVE 48 % (26/54), INERTIAL 4 % (1/23), no SUNSAFE attacks. This
    view is **misleading**: the corpus uses `scenario_all_modes_dwell`, so one
    attack's window spans every mode and is attributed to wherever it *started*
    (mostly PASSIVE, where the FSW boots/locks), and incident voting then
    recovers the label from the *good* frames in other modes.
  - *Frame-level* (each frame's actual mode — the operationally real "attacked
    while persistently in mode X" question): **PASSIVE 0.148 cluster-acc is the
    WORST**, vs INERTIAL 0.341, SUNSAFE 0.395, BDOT 0.419. This **confirms** the
    original NOS3-301 premise (PASSIVE is the weak mode). It is **intrinsic, not
    compositional**: the same cluster labels worse in PASSIVE (e.g.
    `EX-0012.{03,04,05}` 0.29 PASSIVE vs 0.44/0.50/0.52 elsewhere) — a single
    global classifier underfits PASSIVE's quiescent telemetry regime.

**NOS3-301 (closed — negative result):** all three mode-aware approaches were
evaluated by LOIO over the frozen corpus and **none** raise PASSIVE label
accuracy (PASSIVE cluster-acc: baseline 0.148 → mode-feature 0.146, per-mode
heads 0.120, mode-rebalanced 0.150). A PASSIVE-only specialist scoring *below*
the global model shows the global 0.148 is propped up by cross-mode transfer:
PASSIVE labeling is an **information limit, not a modeling one**, so no
mode-aware architecture on the current 894 features closes it. The real fix must
add *signal* (extra discriminating MIDs — NOS3-321 — or temporal features), not
rearrange the model. Per-mode heads *do* help the higher-signal modes
(INERTIAL +0.06, SUNSAFE +0.06, ROBUST +0.07, overall +0.01); that upside is
filed as **NOS3-305** (selective hybrid, backlog).

Bottom line: today, trust an incident's *existence* far more than its *label*,
and treat **PASSIVE labels as low-confidence regardless of model**. (Source:
`data/onair/models/cluster_rescore/incident_rescore_oof.json`; out-of-fold
predictions in `cluster_rescore/loio_predictions_oof_v3stage.npz`; mode-aware
sweep in `data/onair/models/mode_aware/`.)

### E. Stage 2 sharpens, it does not widen

The classifier runs **only** on frames Stage 1 already flagged (it skips ~89 %
of frames this way). It therefore **cannot** detect an attack the anomaly
detector missed. The detection net is Stage 1; Stage 2 only attaches a label.

### F. Blind window after every ADCS mode switch (NOS3-303)

The detector suppresses alerts for **~124 s (600 frames) after each mode
switch**, to ride out the switch transient. So **detection is reliable only in a
mode held longer than ~124 s** — an attack confined to a briefly-held mode may
raise no alert. Measured over a 36-switch nominal soak, the transient itself
settles in **~36 s (~175 frames)**, so most of that blind window is avoidable;
reducing the warmup to **~250 frames (~52 s)** cuts the blind window by ~58 %
with margin over the transient.

---

## Coverage matrix (SPARTA techniques)

Catch rate = SUNSAFE corruption-window flag rate. Tier = classifier
reliability. Signal = observability class.

| Technique | Catch (SUNSAFE) | Classifier tier | Signal | Note |
|---|--:|---|---|---|
| EX-0008.01 ATS | 91 % | HIGH-VAR | ON_BOARD | |
| EX-0008.02 RTS | 91 % | **ROBUST** | ON_BOARD | reliably caught & labeled |
| EX-0012.03 prop cmd | < 25 % | sibling | ON_BOARD | ≡ .04/.05 cluster |
| EX-0012.04 app tables | 63 % | DEAD→sibling | ON_BOARD | ≡ .03/.05 family |
| EX-0012.05 scheduler | 64 % | sibling | ON_BOARD | ≡ .03/.04 family |
| EX-0012.07 propulsion | 100 % | HIGH-VAR | ON_BOARD | always detected |
| EX-0012.08 ADCS | 100 % | HIGH-VAR | ON_BOARD | always detected; label unstable across runs |
| EX-0012.09 EPS | 99 % | HIGH-VAR | ON_BOARD | |
| EX-0012.12 system clock | 57 % | sibling | ON_BOARD | ≡ EX-0014.01 |
| EX-0014.01 time spoof | 26 % | DEAD→sibling | ON_BOARD | ≡ EX-0012.12 |
| EX-0014.03 sensor spoof | 91 % | nominal-amb. | ON_BOARD | detected, not labelable |
| EX-0014.04 PNT spoof | 98 % | HIGH-VAR | ON_BOARD | |
| IMP-0001 deception | 61 % | low-stable | OBFUSCATION | counter telescoping |
| IMP-0002 disruption | 58 % | **STABLE-MID** | ON_BOARD | |
| IMP-0003 denial | 100 % | **STABLE-MID** | ON_BOARD | |
| IMP-0005 destruction | 75 % | **ROBUST** | ON_BOARD | reliably caught & labeled |
| IMP-0006 theft | 62 % | STABLE-MID | UNSUBSCRIBED | detected via side effects |
| DE-0003.01 disable logging | < 25 % | **ROBUST** | OBFUSCATION | labelable when flagged |
| DE-0003.02 clear logs | < 25 % | low-stable | OBFUSCATION | counter telescoped |
| DE-0003.03 | < 25 % | DEAD (nominal) | UNSUBSCRIBED | out of scope |
| DE-0003.06 | < 25 % | DEAD (nominal) | ON_BOARD | one-way confusion only |
| DE-0003.08 | < 25 % | DEAD (nominal) | OBFUSCATION | telescoped |
| DE-0003.09 | < 25 % | DEAD (nominal) | ON_BOARD | NOOP-only |
| DE-0003.10 | < 25 % | **ROBUST** | ON_BOARD | labelable when flagged |

*(DE-0003.04/05/07/11/12 are CONCEPTUAL/UNSUBSCRIBED — out of scope for
telemetry detection.)*

---

## Provenance & caveats

- **Detection / FP numbers:** per-mode Isolation Forest
  `iforest_per_mode_v5_invariant_bolstered`, calibrated to 1 % FP; soak FP
  rates measured on nominal-flight side-files.
- **Classification numbers:** v3 classifier
  `xgb_attack_classifier_v3`, leave-one-instance-out over a 3-instance,
  mode-balanced corpus (independently reproduced 2026-06-09 at
  0.627 ± 0.040, matching the deployed 0.645 ± 0.036).
- **Attack realism:** all cited techniques were executed against live NOS3 FSW
  and confirmed to actually change spacecraft state; no number here derives
  from an unvalidated script.
- **Known undertraining:** the BDOT detector is trained on few samples (296
  rows). It produces no false alarms but also little attack signal — low
  operational impact, since attacks don't manifest in BDOT.

---

## One-line summary for a briefing slide

> *In SUNSAFE flight the monitor reliably flags real attacks (15/23 techniques
> ≥ 50 %, many ~100 %) at under 1 % false alarms, and names ~8 of them with
> high confidence; outside SUNSAFE, and for a documented set of
> telemetry-identical or unmonitored techniques, coverage is limited by design
> rather than by tuning.*
