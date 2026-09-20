<!-- tickets-migrated -->

# Sprint 30 — "Ask It Again, Properly" 🔁

**Component:** `OnAIR-Security`

**Created:** 2026-09-20

**Duration:** 2 weeks (2026-09-20 → 2026-10-04)

**Capacity:** ~16 E-pts / ~7–8 T-pts (solo, realistic focus factor)

**Context:** Sprint 29 collected a clean corpus, retrained on it, and answered the `ROBUST`
question — and then the work itself found two reasons the answer could not stand. Every CSV
this project has ever recorded was two interleaved buffer snapshots (`AINOS3-125`), and the
corpus covered two of the spacecraft's four flight modes because a finding about *evaluation
variance* was read as one about *deployment coverage*.

Neither defect destroyed the collection. Blending is a deterministic re-expression, so
Sprint 29's 30 hours of data was re-derived rather than re-run. What was never collected is
BDOT, PASSIVE, and INERTIAL at depth — and that is this sprint's cost.

**Sprint goal:** Collect the two missing modes and the INERTIAL depth, on a format we now
trust and with the attack footprints verified as they are produced, then ask the `ROBUST`
question again on a corpus that can actually answer it.

⚠ **The pre-registered expectation:** headline accuracy will probably **fall**. On the v3
corpus PASSIVE is by far the weakest mode (sub-technique accuracy 0.113 on attack frames,
against SUNSAFE 0.268 and BDOT 0.277), so adding it makes the average worse. That is what a
*fairer* corpus looks like, not a regression — and a number that drops for a known reason is
worth more than one that held because a hard mode was missing.

---

## Points — two metrics

Each item carries two independent estimates:

- **E — effort points** (Fibonacci 1·2·3·5·8): relative effort × **uncertainty** ×
  coordination. Sized for risk; comparative, not time.
- **T — time points** (**8 h = 1 point = 1 ideal engineering day**): hands-on-keyboard hours ÷ 8.
  Pure duration; excludes the risk premium and unattended wall-clock (collection runs), noted
  separately.

Read the gap: **T < E** ⇒ sized up for *risk*; **T ≈ E** ⇒ big-but-known.

---

## Index

**IDs are slugs; Jira keys are the real ticket keys.** The durable slug ↔ Jira-key mapping is
maintained in **[`JIRA_CROSSWALK.md`](JIRA_CROSSWALK.md)** (cross-sprint, append-only). The
`Jira` column below is a read-only mirror.

### Committed — the corpus and the answer

| Jira | Slug | Type | Pri | E | T | Summary |
|---|---|---|---|--:|--:|---|
| AINOS3-98 | corpus-integrity | Epic | — | — | — | The corpus as a first-class, versioned artifact |
| AINOS3-125 | blended-log-format | Story | **High** | 1 | 0.25 | Only `AC8` remains — decide whether blended becomes the canonical corpus format. Gates everything below |
| AINOS3-126 | sbn-adapter-blended-output | Story | **High** | 5 | 1.5 | Make the live adapter emit the same frames the offline converter does, and **verify it** — `AC1`/`AC2`/`AC3`. the deploy (`AC4`/`AC5`) is a later, gated step |
| AINOS3-100 | corpus-rebuild-steadyflight | Story | **High** | 8 | 2.5 | `AC8` footprint check first; then `AC7` collects four per-mode runs SUNSAFE×1 → INERTIAL×4 → BDOT×5 → PASSIVE×5 (≈281 runs, verify between each) on the dual-output adapter |
| AINOS3-101 | retrain-clean-corpus | Story | **High** | 3 | 1.0 | Re-ask the `ROBUST` question on the four-mode blended corpus |
| AINOS3-122 | label-set-freeze | Story | **High** | 1 | 0.25 | `AC7` promotion, once `AINOS3-101` produces a matching classifier |

**Committed set:** E = **18** · T = **5.5** (+ collection wall-clock, **~55 h** across four runs,
tracked separately).

The E is a touch over the ~16 guideline, but the **T is not** — the committed spine is
**5.5 T-pts, roughly one week of hands-on work**, and the ~55 h of collection is *unattended*
(kick off each mode, the machine runs it), so it overlaps the desk work rather than adding to
it. That leaves the back half of the two-week sprint for the second track (`AINOS3-97`) and
the stretch items, which are genuinely expected to land, not sacrificial. If anything does
slip, **`AINOS3-122 AC7` is the natural drop** — tail of the chain, gated on `AINOS3-101`
anyway, and losing it costs a promotion rather than a finding.

### Second track — expected to land (the spine is ~1 week; this fills the rest)

| Jira | Slug | Type | Pri | E | T | Summary |
|---|---|---|---|--:|--:|---|
| AINOS3-97 | quarantine-stale-corpus | Task | Medium | 3 | 0.75 | The generation-level moves; the idle-logging slice and the schema survey are done |
| AINOS3-91 | startracker-inert-fields | Spike | Medium | 2 | 0.25 | Rides the `AINOS3-100 AC7` INERTIAL collect — AC2 is answered by `AINOS3-86`, the collect confirms it at scale, then AC3–AC6 close. Near-zero marginal cost |

### Stretch

| Jira | Slug | Type | E | T | Condition |
|---|---|---|--:|--:|---|
| AINOS3-128 | interleaved-claim-audit | Spike | 3 | 1.0 | Sequences naturally *after* the retrain; several claims need the new corpus to re-derive against |
| AINOS3-127 | gate-retune-blended | Story | 5 | 1.5 | Gated on the `AINOS3-126` **deploy** and on collecting `EX-0014.02`/`EX-0012.02` — see the label-set note below |
| AINOS3-93 | overlay-column-scope-mismatch | Bug | 2 | 0.5 | Cheapest if the coverage generator is already open; more relevant now that tier claims are known to be mode-scoped |

---

## The critical path — why this order

1. **Settle the format first — `AINOS3-125 AC8`.** Whether blended is canonical is a
   one-sitting decision, and everything downstream inherits it. Collecting ~281 runs before
   deciding would risk a third representation question on top of the two Sprint 29 already
   had. The evidence is in: blending is strictly more faithful, gives the classifier
   +0.034 macro-F1, and costs one script.
2. **Build and VERIFY the dual-output adapter — `AINOS3-126 AC1`/`AC2`/`AC2b`/`AC3`.** The
   adapter emits both the raw interleaved stream (a pure tap, so it stays the same
   representation the old adapter produced — `AC2b`) and the native blend. The proof is
   per-run and deterministic: `deinterleave_csv.py(raw) == native blend`, in all four modes,
   using the collection runs themselves. ⚠ If the two ever disagree, offline results stop
   predicting live behaviour and **nothing in the system would notice** — so the deliverable
   is the equivalence evidence, not the code.
   ⚠ **Deploying is explicitly out of scope this sprint.** `AC4` requires the IF and
   classifier refitted on blended data, and those refits need the four-mode corpus step 4
   produces. Implementation and proof now; the deploy (`AC4`/`AC5`) waits on that corpus.
3. **Build the footprint check BEFORE collecting — `AINOS3-100 AC8`.** ⚠ This is the
   sequencing Sprint 29 got wrong in the other direction. `AC2`'s gate checks that an attack
   *ran*, never that the telemetry it should move actually moved, and the corpus was trained
   on regardless. Landing `AC8` first means ~281 runs are gated as they are produced instead
   of back-filled — and a generic novelty check will not do, since the probe-only techniques
   score in the same band as real attacks.
4. **Collect — `AINOS3-100 AC7`, as FOUR separate per-mode runs on the DUAL-OUTPUT adapter,
   verifying after each.** Each run writes both the raw interleaved stream (`csv/`) and the
   native blend (`csv_blended/`); the owner runs the collection manually and pauses between
   modes for a verify.
   1. **SUNSAFE ×1** (19 runs) → verify `blend(raw) == native` + footprints. If it passes,
      **replace** one existing offline-blended SUNSAFE instance with this live one (keep
      SUNSAFE at 5 — not a 6th, which changes the fold count). If it fails, stop and fix the
      adapter before going further.
   2. **INERTIAL ×4** (72 runs; 18 techniques/instance — `EX-0012.07` breaks the hold) →
      verify. Sharpest equivalence test: existing ×1 offline-blended, new ×4 live. ⚠ This run
      is tracker-enabled + orbit-normal, so it also supplies the repeat-window `AINOS3-91 AC2`
      needs — check `St.valid` holds near 100 % here and `AINOS3-91` can close on it.
   3. **BDOT ×5** (95 runs) → verify. First-ever `single_mode_hold_BDOT`.
   4. **PASSIVE ×5** (95 runs) → verify. First-ever `single_mode_hold_PASSIVE`.

   ≈ 281 runs, ~55 h across the four runs (BDOT/PASSIVE timed as SUNSAFE-like, unmeasured).
   The two proven modes go first so a surprise in the two never-collected ones surfaces with
   known-good examples in hand. ⚠
   `build_corpus_batch.MIN_PER_RUN_INERTIAL_EXTRA` is still 17.0 and will over-plan INERTIAL;
   the post-fix figure is ~0.
   ⚠ **The kills are the harness watchdog, not the machine** (proven 2026-09-19: no cgroup
   cap, memory PSI 0.00, zero OOM/oomd kills). The Sprint-29 collection hit them and survived
   only because `run_corpus_chunks` is resumable. **Run the collection from a normal
   terminal** — no watchdog there — and they do not occur.
5. **Retrain — `AINOS3-101`.** Same method as Sprint 29: manifest-driven LOIO, the
   three-confound decomposition, the cross-mode holdout, footprint reproducibility as the
   mechanism. ⚠ Carry forward rather than rediscover: `AC4`'s premise is refuted (more folds
   also means more training data per fold), the tier table was bimodal so the 0.85 bar's
   exact value changed nothing, and `ROBUST` was a **within-mode** claim — the three ROBUST
   classes scored 0.000 / 0.000 / 0.390 on held-out INERTIAL.
6. **Promote — `AINOS3-122 AC7`.** Blocked on `AINOS3-101` producing a classifier whose
   class list matches the artifacts being promoted. ⚠ With four modes in the corpus the
   deploy that was structurally blocked in Sprint 29 becomes possible for the first time.

⚠ **The gate-retune dependency is a label-set change, not just a collection.** `AINOS3-127`
needs `EX-0014.02` (bus spoof) and `EX-0012.02` (route severing) — the attacks
`consistency_check` and `staleness_check` exist for, and the reason both scored exactly
0.0000 in Sprint 29's A/B. **Neither is in the frozen 26-class label set.** Adding them means
re-opening `AINOS3-122`, so it is a deliberate decision rather than a line item, and it is why
`AINOS3-127` sits in stretch rather than on the spine.

---

## Open goals — tracked, not scheduled

⚠ Not a next-sprint plan. Things go faster than predicted or pivot hard, so nothing past this
sprint gets a specific plan — only a note that these exist and are not lost. They are picked
up when their gates clear, in whatever sprint that turns out to be:

- **The `AINOS3-126` deploy** (`AC4`/`AC5`) — gated on a four-mode corpus to refit the IF and
  classifier against, which this sprint produces.
- **`AINOS3-127`** gate-retune — gated on that deploy plus the two gate attacks.
- **The direction `AINOS3-101` sets.** If `ROBUST` survives a four-mode corpus on a trusted
  format, the tier table finally means what it says. If not, the lever is observability
  (`AINOS3-69`), and `AINOS3-128` re-tests the old conclusions on honest features.
- The backlog (`AINOS3-115`/`116`/`118` STIX, `AINOS3-123`, `AINOS3-94`) stands in
  `JIRA_CROSSWALK.md`; it does not need a schedule to not be forgotten.

---

## 📋 Not sprinted, and why

| Jira | Slug | Why not committed this sprint |
|---|---|---|
| AINOS3-115/116/118 | STIX coverage | Feed a future increment, not this collection. Third sprint deferred — worth a deliberate decision rather than another roll-forward. |
| AINOS3-123 | per-subsystem-consistency-primitive | Stack-dependent; competes with a ~55 h collection. |
| AINOS3-94 | coverage-table-schema | Stages 1–2 are presentational; stages 3–5 wanted mode as a first-class cell, which the four-mode corpus finally makes meaningful — better once that data is in hand. |
