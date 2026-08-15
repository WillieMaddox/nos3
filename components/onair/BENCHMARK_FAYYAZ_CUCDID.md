# Benchmark — CuCD-ID (Fayyaz et al. 2026) vs the OnAIR-Security detector 🔬

**Ticket:** AINOS3-82 · **Sprint:** 27 · **Date:** 2026-08-11

**Subject:** Fayyaz, Afrasiabi, Yang & El-Khatib, *"CubeSat cybersecurity dataset for
intrusion detection (CuCD-ID): Labelled NOS3/cFS telemetry (raw + augmented) with COSMOS
reproduction scripts"*, **Data in Brief 65 (2026) 112598**,
[doi:10.1016/j.dib.2026.112598](https://doi.org/10.1016/j.dib.2026.112598). Dataset:
Mendeley Data [doi:10.17632/7n2d42pm3n.3](https://doi.org/10.17632/7n2d42pm3n.3), CC BY 4.0.

This is the closest published benchmark to our work — same simulator (NOS3 + cFS), same
ground-system family (COSMOS), SPARTA-aligned attack scenarios, and an independent group
(Ontario Tech). It is a rare chance to sanity-check our numbers against someone else on
the same stack.

---

## TL;DR

- **We could not produce an apples-to-apples accuracy comparison, and that is the finding,
  not a shortfall.** Their feature space (CCSDS packet headers + 20 s arrival-time window
  statistics + host cgroup memory) and ours (raw + delta over 359 spacecraft-telemetry
  columns, including GNC dynamics) are **almost entirely disjoint**. Our classifier cannot
  consume their table and theirs cannot consume ours.
- **Their released table is trivially separable, by several independent routes at once.**
  Reproducing with our own model family: all-features accuracy is **1.0000**; the
  flight-software **memory columns alone give 1.0000**; a single wall-clock feature
  (`TimeRadians`) alone gives **0.8818** on a balanced 5-class task (chance 0.20);
  **5 of 22 individual columns reach ≥ 0.95 on their own.**
- **Their recommended train/test split does not fix the leak it warns about.** Accuracy is
  identical (1.0000) under a random split and under their README's per-class chronological
  split, because each class is *one contiguous collection run* and the split cuts *inside*
  that run.
- **Leave-one-instance-out is structurally impossible on the release** (one run per class;
  our corpus has three). This is the single most important methodological difference
  between the two datasets and the strongest external endorsement of our LOIO discipline
  — the same discipline that took our own incident-label figure from an in-sample 76.9 %
  to the honest **42.3 % OOF**.
- **All four of their attack classes map onto leaves we already detect**, three of them via
  a deployed rule that fires on the exact mechanism their script uses (R5, R11, R6/R7).
- **Worth borrowing:** their command-ingress feature family (CCSDS header + arrival-time
  window statistics) is a genuine observability gap on our side and is directly testable
  right now — `CI.usCmdCnt` / `TO.usCmdCnt` entered our schema in Sprint 25/26 and are in
  the AINOS3-30 candidate block. Also their nine augmentation noise categories.

---

## 1. What CuCD-ID is

| Property | CuCD-ID |
|---|---|
| Simulator | NOS3 1.7.2 + cFS, Ubuntu 22.04.4, Docker 26.1.3, stock mission profile |
| Ground system | COSMOS **v4** (4.5.1) Script Runner |
| Instrumentation point | **CI Lab ingress** — per-packet, at the command-ingest interface |
| Raw table | 25,000 rows × 31 columns (30 features + `Label`), exactly 5,000 per class |
| Augmented table | 22,465 rows × 23 columns, 9 documented noise categories, `SEED=7` |
| Classes | 5: command_flooding, data_injection, defence_impairment, normal, storage_exhaustion |
| Feature families | CCSDS header metadata; 20 s sliding-window traffic statistics; error counters; Linux cgroup memory metrics of the FSW process |
| Reproduction | 5 COSMOS v4 Script Runner `.txt` scripts, one per scenario, 5,000 commands each |
| Companion IDS paper | *Computers and Security* (Elsevier), embedded TinyML, NSGA-III + CASH |

**Integrity verified.** Both published SHA-256 hashes match the downloaded files exactly.
Note a shipped defect: `Data/Metadata/checksums.txt` carries the hashes but **no filenames
on the hash lines**, so the `sha256sum -c checksums.txt` its own README prescribes cannot
run. `benchmark_fayyaz.py` verifies by position instead.

**The companion paper's numbers are not in hand.** It is paywalled (SSRN returns 403). A
web summary attributes F1 87.66–99.59 % to this group, but the classes it names (DoS,
fuzzy injection, replay; "time-based" and "data-based" models) do not match CuCD-ID's five
and read like CAN-bus IDS work. **Treated as unverified and not used here.** Everything
below rests on the Data-in-Brief, the repository README, and our own reproduction.

---

## 2. Method comparison

| Dimension | CuCD-ID / Fayyaz et al. | OnAIR-Security (ours) |
|---|---|---|
| Vantage point | Command **ingress** (CI Lab), per uplink packet | Telemetry **egress** (SBN subscription), per 1 Hz frame |
| What it sees | Packet headers, inter-arrival timing, host memory | Spacecraft state: ADCS/GNC dynamics, per-app HK counters, device flags, table/route state |
| Features | 30 (22 non-constant) | 894 (raw + delta over 359 kept telemetry columns) |
| Physics / dynamics | **None** | Core of the Stage-1 detector |
| Model | Embedded TinyML, NSGA-III feature selection + CASH | Per-ADCS-mode Isolation Forest gate → selective per-mode hybrid HistGB classifier |
| Architecture | Single-stage classifier | 5 gates: per-mode IF, rule-gate (R1–R13), consistency-check, staleness-check, incident aggregator |
| Class granularity | 5 scenario classes | 26 SPARTA techniques / 22 clusters |
| Nominal definition | A scripted 5,000-command NOOP-polling loop @ 0.1 s | Genuine idle operations across 4 ADCS modes |
| Collection runs per class | **1** | **3** (mode-balanced instances) |
| Evaluation protocol | Per-class chronological split (README Option 1) | Leave-one-instance-out (LOIO), out-of-fold |
| False-positive measurement | Not possible (no idle baseline) | Multi-hour nominal soak: **0.01 %** over 6.6 h |

The two systems are not competitors — they are **complementary halves of the same
problem**. They watch what comes *up* the link; we watch what the spacecraft *does* as a
result. Neither can see the other's evidence.

---

## 3. Their five classes mapped to our SPARTA leaves

| CuCD-ID class | Their mechanism | Our SPARTA leaf | Our status |
|---|---|---|---|
| command_flooding | 5,000 diverse cFS commands (CFE/FM/CF/TO/LC), 250 "flush" pauses of 20–22 s to break the 20 s window | **EX-0013** (flooding); the log-pressure variant is **DE-0010** | Validated; DE-0010 caught via **R2** (EVS rate) |
| data_injection | 5,000 `MM_POKE` writes to 4-byte offsets in the `NOVATEL_OEM615` GPS struct | **EX-0012.03** (memory write) delivering an **EX-0014.03/.04** effect | Validated; EX-0014.03/.04 are two of our **DEAD** label classes |
| defence_impairment | 176 LC actionpoints → PASSIVE/DISABLED, CS validation disabled, periodic stat resets as cover | **DE-0001** (disable fault management) | Detected via **R5** (monitor-state), AINOS3-73 |
| storage_exhaustion | 5,000 FM file copies into `/cf` until the partition fills | **EX-0010** (file operations) / **IMP-0003** (denial) | Detected via **R11** (FM command burst), AINOS3-71 |
| normal | 5,000 health-check commands, 20-command cycle, 0.1 s pacing | *no equivalent* — this is a command storm, not idle ops | n/a |

Their taxonomy is **four attack leaves**; our classifier discriminates **26 techniques in
22 clusters**, inside a coverage matrix where 42 SPARTA leaves are detected overall. Any
accuracy comparison must state this: a balanced
5-class problem and a 26-class imbalanced one are not the same task, and near-100 % on the
former says nothing about the latter.

Two of their four attacks (`data_injection` → EX-0014.03/.04) land squarely on classes our
classifier scores **F1 = 0.000** on. That is not a contradiction — see §5.

---

## 4. Evaluation-honesty cross-check (the experiment)

This is the acceptance criterion that ties to `metric-provenance-audit` (AINOS3-80): do
they split so as to avoid the sliding-window leakage they themselves warn about?

**Their README is admirably explicit** — "**Do NOT use random splits.** Telemetry data is
inherently temporal" — and it documents the sliding-window leakage risk by name. So the
awareness is there. The question is whether the *released table* permits a split that
actually removes the leak.

We reproduced with our own model family (`HistGradientBoostingClassifier`, identical
hyperparameters to our deployed v3 classifier) so the numbers sit on our scale:

| Arm | Features | Split | Accuracy | Macro F1 |
|---|--:|---|--:|--:|
| A1 all (non-constant) | 22 | random stratified 80/20 | **1.0000** | 1.0000 |
| A2 all (non-constant) | 22 | README Option 1 (per-class chronological) | **1.0000** | 1.0000 |
| A3 `TimeRadians` only | 1 | random | **0.8818** | 0.8779 |
| A4 memory columns only | 8 | random | **1.0000** | 1.0000 |
| A5 behaviour only (no clock, no memory) | 13 | random | 0.9998 | 0.9998 |
| A6 behaviour only | 13 | README Option 1 | 0.9998 | 0.9998 |

Single-feature sweep — **5 of 22 columns reach ≥ 0.95 alone** (chance = 0.20):

| Column | Accuracy alone |
|---|--:|
| `MemoryFileMB` | 0.9930 |
| `SlidingWindowMeanIntervalSec` | 0.9840 |
| `SlidingWindowMinIntervalSec` | 0.9830 |
| `SlidingWindowMaxIntervalSec` | 0.9746 |
| `MemoryAnonMB` | 0.9682 |
| `MessageCountInWindow` | 0.9228 |
| `TimeRadians` | 0.8818 |

### What this means

**The release contains one contiguous collection run per class.** Run-length encoding the
`Label` column returns exactly 5 runs of 5,000 — so class identity is perfectly confounded
with *session* identity. Three consequences, all measured above:

- **The clock is a label.** Per-class `TimeRadians` arcs barely overlap; `data_injection`
  occupies [5.156, 5.321] and is **disjoint from every other class**. Three class pairs are
  separable by wall-clock alone, with no reference to attack behaviour. A single clock
  feature gets 88 %.
- **The host's memory baseline is a label.** `MemoryFileMB` — the page-cache size of the
  flight-software cgroup — alone reaches 99.3 %, and the 8 memory columns together reach
  100 %. That is a fingerprint of *when the process was recorded*, not of an attack.
- **Their recommended split does not remove either.** Option 1 sorts by `TimeRadians` and
  holds out the trailing 20 % *of each class*. Because each class is one run, train and
  test remain inside the same session, so the class ↔ session association survives intact
  — accuracy is unchanged at 1.0000.

**One honest qualification.** A5 shows the behaviour-only features *also* reach 0.9998, so
we cannot claim the accuracy is *entirely* session artifact. The defensible claim is
narrower and still damaging: **the dataset admits at least three mutually redundant
near-perfect solutions, at least two of which are session artifacts rather than attack
behaviour — and no split of the released table can tell you which one a model used.** A
reported accuracy on this table is therefore uninterpretable as a detection capability.

The behaviour features separating perfectly is itself a symptom: each class is a distinct
*scripted command mix* (a 5,000-command flood vs a 0.1 s NOOP poll vs 5,000 `MM_POKE`s), so
the packet-rate statistics trivially tell the scripts apart. The task as posed is closer to
"which script produced this packet" than "is this spacecraft under attack."

### Two further protocol notes

- **README Option 2** ("Labels-wise split (leave-one-out): train on 4 classes, test on 1
  held-out class") is not a valid supervised multi-class protocol — the held-out class's
  label never appears in training, so a standard classifier scores 0 on it by construction.
  It only makes sense for open-set / novelty detection.
- **README Option 3** (`LeaveOneGroupOut` over `attackTypes_ids`) is not runnable on the
  release as shipped: there is no run/group identifier column in the CSV. This is exactly
  the column that would be needed for LOIO — and exactly what having only one run per class
  makes meaningless anyway.

### How our discipline compares

| | CuCD-ID | Ours |
|---|---|---|
| Runs per class | 1 | 3 |
| LOIO possible | **No** | Yes |
| Headline metric provenance | in-session chronological split | **out-of-fold, LOIO** |
| Nominal FP measurable | No (no idle baseline) | Yes — 0.01 % over a 6.6 h soak |

Our own numbers, tagged: technique-level top-1 **0.646** (deployed hybrid, LOIO OOF) vs
0.627 (v3 global head, identical folds); cluster-level **0.660**; incident recall **92.8 %**
(77/83 genuinely-detectable state-change attacks) and 67.8 % (78/115 all techniques);
incident-label accuracy **42.3 %** (OOF — the figure that replaced an in-sample-optimistic
76.9 %).

Ours look far worse than their ~100 %. **They are measuring a different, much easier thing,
under a protocol that cannot exclude session artifacts.** That is the whole point of the
comparison.

---

## 5. Why no head-to-head number exists

The ticket's stretch goal was to score our classifier on their data, or run their scripts
for a direct number. We downloaded the dataset and it is **still not possible**, for a
structural reason worth recording:

- **Disjoint feature spaces.** Our 894 features are raw + delta over spacecraft telemetry
  (`ADCS_GNC.*`, `CFE_*_HK.*`, `TO.*`, device flags). Their 30 are CCSDS header fields,
  packet arrival statistics, and host memory. There is **no overlapping column**. Our model
  has nothing to consume in their table; theirs has nothing to consume in ours.
- **Different sampling unit.** They emit one row per *packet*; we emit one row per 1 Hz
  *telemetry frame*. Even the time axis doesn't align.
- **Their `normal` is not our nominal.** A 5,000-command NOOP storm would trip several of
  our rule-gate command-rate rules. Scoring our detector against their "normal" would
  produce meaningless false positives that reflect the scenario definition, not the
  detector.

Note also the direction of the mismatch on `data_injection`: their pipeline classifies it
easily because 5,000 `MM_POKE`s have an unmistakable **ingress** signature, while ours
scores F1 = 0.000 on EX-0014.03/.04 because we only see the **effect** on a GPS telemetry
field that our feature vector barely distinguishes from noise. Same attack, opposite
outcome, purely because of where the sensor sits. This is the clearest evidence yet for
`AINOS3-69`'s standing conclusion that **our binding constraint is observability, not
model capacity.**

---

## 6. What to borrow

1. **Command-ingress features (highest value).** Their entire discriminative power on
   `data_injection` and `command_flooding` comes from a vantage point we don't model.
   `CI.usCmdCnt`, `CI.usCmdErrCnt`, `TO.usCmdCnt` are already in our 359-column schema (AINOS3-72)
   and *absent* from the frozen 250-column corpus — so they are in the AINOS3-30 candidate
   block and testable **this sprint**. Their result is a prior that this family should lift
   exactly the classes we call DEAD. Feeds AINOS3-83 directly.
2. **Arrival-time window statistics.** Inter-arrival mean/min/max/stddev over a fixed window
   is a cheap feature family we do not compute. Worth a candidate block of its own, though
   note their own leakage warning applies to us too if we ever window across a label
   boundary.
3. **The nine augmentation noise categories** (white noise, analog outliers, gaps, trends,
   signal shifts, frequency changes, sensor dropout, magnitude warping, window time warping)
   with their per-feature eligibility matrix. A principled, reusable robustness harness —
   more disciplined than ad-hoc jitter, and their `SEED=7` regeneration script is released.
4. **Class-balanced framing for the classifier stage** (not for detection). Their 5,000/class
   balance is wrong for measuring FP rate but is a clean way to report per-class
   discriminability without prevalence effects.

**What not to borrow:** their split protocol, their `normal` scenario definition, and any
practice of publishing accuracy from a single collection run per class.

---

## 7. Honest limits of this comparison

- We never saw the companion IDS paper's actual results. Everything here compares against
  the **dataset and our own reproduction on it**, not against their published detector.
  If the paper becomes available, the numbers in §4 should be re-read against it.
- Our reproduction uses **our** model family, not their NSGA-III + CASH TinyML pipeline. The
  arms are internally consistent and the leakage conclusions are about the *data*, not their
  model — but they are not a reproduction of their result.
- Their augmented table was not analysed here; only the raw table. The augmented set removes
  8 invariant columns and adds noise, which may blunt (but cannot remove) the session
  confound, since `TimeRadians` and the memory columns are retained.
- The CuCD-ID authors documented the leakage risk themselves and shipped reproduction
  scripts and checksums — this is a more transparent release than most. The critique here is
  of what the released structure *permits*, not of concealment.

---

## 8. Reproduce

```bash
curl -L -o /tmp/cucdid.zip \
  https://data.mendeley.com/public-api/zip/7n2d42pm3n/download/3
unzip /tmp/cucdid.zip -d data/onair/external/
mv "data/onair/external/CubeSat Cybersecurity Dataset for Intrusion Detect" \
   data/onair/external/cucdid_v3

~/.virtualenvs/nos3/bin/python components/onair/training/benchmark_fayyaz.py \
  --data-dir data/onair/external/cucdid_v3 \
  --out-json data/onair/models/benchmark_fayyaz.json
```

`data/onair/external/` is git-ignored — the dataset is CC BY 4.0 and redistributable, but
it is not ours to vendor. Full results, including the structural diagnostics and the
complete single-feature sweep, land in `data/onair/models/benchmark_fayyaz.json`.
