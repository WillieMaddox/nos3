# Sprint 2 — "Frame → Incident" 🛰️

**Component:** `OnAIR-Security` · **Duration:** 1 week
**Capacity:** ~13–16 E-pts / ~3.5–4 T-pts (solo) · **Status:** delivered 2026-06-10
**Created:** 2026-06-10 · **Context:** Week-2 of the "harden & communicate" plan,
following the completed Week-1 work (cluster re-score, 6.6h drift soak,
`V5_DETECTOR_COVERAGE.md`).

**Sprint goal:** Turn the validated frame-level detector into an
**incident-reporting** monitor with a **live demo**, so stakeholders see real
per-attack results instead of raw frame scores.

## Points — two metrics

- **E — effort points** (Fibonacci 1·2·3·5·8): relative effort × **uncertainty**
  × coordination. Comparative, not time.
- **T — time points** (**8 h = 1 point = 1 ideal engineering day**): estimated
  hands-on-keyboard hours ÷ 8. Pure duration; excludes the risk premium and
  unattended wall-clock (soak / collection), noted separately.

`T < E` ⇒ sized up for risk, not length; `T ≈ E` ⇒ just big-but-known.

---

## Index

| Key | Type | Pri | E | T | Summary |
|---|---|---|--:|--:|---|
| NOS3-200 | Epic | — | — | — | Incident-level security alerting |
| NOS3-201 | Story | Highest | 8 | 2.25 | One alert per attack, not a stream of per-frame flags |
| NOS3-202 | Task | High | 3 | 0.5 | Wire cluster reporting into the live classifier plugin |
| NOS3-203 | Task | High | 5 | 1.0 | Re-score the corpus at incident granularity |
| NOS3-210 | Epic | — | — | — | SPARTA demo app |
| NOS3-211 | Story | Medium | 5 | 1.25 | Demo app Tier A shows real per-technique status |
| NOS3-150 | Spike | — | — | — | (Resolved) SUNSAFE-only pivot decision |

**Totals (delivered tickets):** E = 21 · T = 5.0 (≈ 40 ideal hours).

---

## 🟪 EPIC NOS3-200 — Incident-level security alerting

**Summary:** Move detection/classification output from per-frame to per-incident.
**Description:** Operators currently receive a stream of independent per-frame
flags. This epic adds an aggregation layer that collapses a contiguous run of
anomalous frames into a single incident — with a start time, duration, attack
cluster, and accumulated confidence — and re-baselines the project's headline
metrics on incidents rather than frames.

### NOS3-201 — One alert per attack · `Story` · Highest · E 8 · T 2.25 (~18h)
**Summary:** As an operator, I want one alert per attack (start, duration,
cluster, confidence) instead of a stream of per-frame flags.
**Description:** Build an incident-aggregation layer on top of the existing
warmup/hysteresis machinery in the OnAIR plugin. It groups consecutive
anomalous frames into one incident, accumulates classifier confidence across
the window, and emits a single record when the incident closes. This is the
highest-value item of the sprint: frame-level confidence on a single attack is
already ~0.86 median, so aggregation should produce markedly stronger
incident-level calls.
**Acceptance criteria:**
- Given a corruption window, the plugin emits one incident record:
  `{t_start, t_end, duration_s, cluster, sub_technique, accumulated_confidence}`.
- Persistence + dedup thresholds configurable in `nos3_security.ini`.
- Incident confidence ≥ best single-frame confidence on the live `EX-0012.07`
  integration test (~0.86 baseline).
**Sub-tasks:** ▫ persistence/debounce window ▫ cross-frame confidence
accumulation ▫ incident side-file schema ▫ unit tests on a labeled window.
**Depends on:** NOS3-202.

### NOS3-202 — Wire cluster reporting into the plugin · `Task` · High · E 3 · T 0.5 (~4h)
**Summary:** Wire cluster reporting (`cluster_taxonomy.json`) into the live
`xgb_classifier_plugin.py` → emit `cluster + top sub-technique`.
**Description:** Week-1 produced `cluster_taxonomy.json` (the τ=0.10 mutual-
confusion clusters), but the deployed plugin still reports only the raw
sub-technique. Update the plugin to load the taxonomy and emit both the cluster
("propulsion-command-class") and the top sub-technique, so the operational
output matches the honest classification granularity. Smallest item; unblocks
the incident-label format in NOS3-201.
**Acceptance criteria:**
- Plugin loads `cluster_taxonomy.json`; render_reasoning + side-file include a
  `cluster` field.
- ini synced to `fsw/build/exe/cpu1/cf/onair/`.

### NOS3-203 — Incident-granularity corpus re-score · `Task` · High · E 5 · T 1.0 (~8h)
**Summary:** Re-score the 75-manifest corpus at incident granularity; publish
incident TP/FP as the new headline metric.
**Description:** Run the incident-aggregation logic over the existing 3-instance
labeled corpus and compute incident-level true-positive / false-positive rates
(an attack counts as caught if ≥1 incident fires in its window; a nominal
period firing an incident is a false positive). These replace the frame-level
numbers as the project's headline metrics and feed the coverage doc.
**Acceptance criteria:**
- Incident-level TP/FP table across the 3 instances committed.
- `V5_DETECTOR_COVERAGE.md` updated with incident metrics.

---

## 🟪 EPIC NOS3-210 — SPARTA demo app

**Summary:** Make the stakeholder demo app reflect real detector results.
**Description:** The `app/` demo currently shows static SPARTA matrices. This
epic wires it to the validated detection/classification data and builds out the
sketched A/B/C interaction ladder, starting with Tier A.

### NOS3-211 — Demo app Tier A with real results · `Story` · Medium · E 5 · T 1.25 (~10h)
**Summary:** As a stakeholder, I want the demo app to show real detection status
per SPARTA technique (Tier A of the A/B/C ladder).
**Description:** Implement Tier A of the May-15 demo-feedback ladder and drive
each technique cell from real data in `V5_DETECTOR_COVERAGE.md` (detection
flag-rate, classifier tier, signal class) instead of placeholders. Tier B/C are
out of scope (see NOS3-223).
**Acceptance criteria:**
- Tier A ladder implemented; per-technique cells driven by real coverage data.
- No console errors; Tier B/C explicitly deferred.
**Stretch goal** (depends on NOS3-203 for live incident data).

---

## ✅ Resolved — no work this sprint

### NOS3-150 — SUNSAFE-only pivot decision · `Spike` · Resolved · E — · T —
**Summary:** Decide whether to pivot to a SUNSAFE-only detector if other modes
are too noisy or v5 drifts.
**Description:** The Week-1 6.6h drift soak (0.01% FP, no drift) and the
all-modes soak protocol (INERTIAL/BDOT steady-state ≤0.00%) resolve this spike:
the "pivot to SUNSAFE-only" fallback is **not triggered**. Sprint proceeds as
planned; the SUNSAFE-routed detection caveat stays documented, not "fixed."

---

## 📋 Backlog (deferred — pulled in only if capacity frees up)

### NOS3-220 — Recover nominal-ambiguous DEAD classes · `Story` · E 8 · T 2.5 (~20h)
**Summary:** Subscribe extra MIDs so the nominal-ambiguous DEAD classes become
detectable/classifiable. *(Promoted to Sprint 3 as NOS3-321.)*
**Description:** Week-1 showed `DE-0003.03/.08/.09` and `EX-0014.03` are
*nominal-ambiguous* — their attack frames are indistinguishable from nominal in
the current 894-feature space because the discriminating MIDs
(`CFE_TBL.LastFileLoaded`/`LastUpdatedTable`, CryptoLib SA state, etc.) were
pruned by csv-format-v2. Add those MIDs to `nos3_security_tlm.json`,
re-collect + retrain, and measure whether these classes separate.

### NOS3-221 — TCN-as-feature for EX-0008 ATS/RTS · `Story` · E 5 · T 1.5 (~12h)
**Summary:** Add TCN reconstruction-error as an XGBoost feature scoped to the
EX-0008 family.
**Description:** The Phase-4 spike found a global TCN reaches 0.96 recall on
EX-0008 ATS/RTS where v3 XGBoost is instance-noisy. Re-attempt TCN-as-feature
limited to the EX-0008 family (the prior global v4-TCN-feature net-regressed
DE-0003.10). Goal: lift `EX-0008.01` out of HIGH-VARIANCE without harming the
ROBUST classes.

### NOS3-222 — 4th corpus instance · `Task` · E 3 · T 0.75 (~6h active; ~5h wall-clock)
**Summary:** Collect a 4th corpus instance to tighten LOIO variance.
**Description:** Run `run_attack_batch.py` once more (~5h wallclock) to add a
4th LOIO fold. Low value — LOIO variance is already characterized at ±3.6% — so
this is a Task, and stays in backlog unless a specific class's confidence
interval needs tightening.

### NOS3-223 — Demo app Tier B/C · `Story` · E 3 · T 1.0 (~8h)
**Summary:** Implement Tier B/C of the demo-app A/B/C ladder.
**Description:** Extends NOS3-211 (Tier A) with the deeper interactive layers
sketched in the May-15 demo. Deferred until Tier A is validated with
stakeholders.

---

## Definition of Done (sprint)

- Incident records emitted live + offline; incident-level TP/FP documented.
- Plugin reports clusters; ini synced to `fsw/build/exe/cpu1/cf/onair/`.
- Demo app shows real results; no console errors.
- `V5_DETECTOR_COVERAGE.md` updated with incident metrics.

---

## Capacity note

Committed E (8 + 3 + 5 + 5 = **21**) / committed T (**5.0** ≈ 40 ideal hours)
both exceed a solo 1-week velocity (~13–16 E / ~3.5–4 T). Actual commitment was
**NOS3-201 / 202 / 203 (E 16 / T 3.75)** with **NOS3-211 as stretch** — all four
ultimately delivered.

## Suggested execution order (as run)

1. **NOS3-202** (smallest, unblocks the rest) — plugin cluster reporting.
2. **NOS3-201** — incident aggregation layer.
3. **NOS3-203** — incident-granularity corpus re-score.
4. **NOS3-211** (stretch) — demo app Tier A wired to real results.
