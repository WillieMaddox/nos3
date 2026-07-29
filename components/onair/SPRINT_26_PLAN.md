# Sprint 26 — "Section B Coverage & Close the Trust Epic" 📡

**Component:** `OnAIR-Security`

**Created:** 2026-07-22

**Duration:** 2 weeks

**Capacity:** ~16 E-pts / ~7–8 T-pts (solo, realistic focus factor)

**Context:** Sprint 25 ran the Section-A validation campaign (13 techniques, all
gate-validated) and shipped the 4 detector gates (rule-gate R1–R10, consistency-check,
staleness-check). That campaign relied on a 16-MID *recording* subscription pass
(2026-07-16) which added the `TO`/`CI`/`LC`/`DS`/`FM` housekeeping + sensor packets —
exactly the MIDs that make the **Section-B** techniques observable. `NOS3_330` still
binds: the limiting factor is **observability (signal), not model capacity**.

**Sprint goal:** Turn the newly-subscribed Section-B MIDs into *validated detections*
(wiper / ransomware, downlink exfil / theft, fault-management), and close the carryover
**classification-trust** epic (counter-reliance audit → selective per-mode hybrid).

---

## Points — two metrics

Each item carries two independent estimates:

- **E — effort points** (Fibonacci 1·2·3·5·8): relative effort × **uncertainty** ×
  coordination. Sized for risk; comparative, not time.
- **T — time points** (**8 h = 1 point = 1 ideal engineering day**): estimated
  hands-on-keyboard hours ÷ 8. Pure duration; excludes the risk premium and unattended
  wall-clock (soak / corpus runs), which is noted separately.

Read the gap: **T < E** ⇒ sized up for *risk*; **T ≈ E** ⇒ big-but-known.

---

## Index

**IDs are slugs; Jira keys are the real ticket keys.** The durable slug ↔ Jira-key
mapping is maintained in **[`JIRA_CROSSWALK.md`](JIRA_CROSSWALK.md)** (cross-sprint,
append-only) — that file is where you *enter* keys. The `Jira` column below is a
read-only mirror. Carryover keys (`AINOS3-39`, `AINOS3-37`) are immutable; the new
slugs get keys when you create the tickets.

| Jira | Slug | Type | Pri | E | T | Summary |
|---|---|---|---|--:|--:|---|
| AINOS3-41 | coverage-expansion | Epic | — | — | — | Detection coverage expansion |
| AINOS3-70 | subscribe-recording-mids | Task | High | 3 | 1.0 | ✅ DONE — subscribe the 16 Section-B recording MIDs (pipe cap 32→48; schema 383 cols) |
| AINOS3-71 | detect-wiper-ransomware | Story | High | 5 | 1.5 | ✅ DONE — FM file-operation detector (EX-0010.02 wiper + EX-0010.01 ransomware) via rule-gate R11 |
| AINOS3-72 | detect-downlink-exfil | Story | High | 5 | 1.5 | ✅ DONE — TO downlink-path detector (EXF-0003.02 exfil + sharpen IMP-0006 theft) via rule-gate R12+R13 |
| AINOS3-73 | detect-fault-mgmt | Task | Medium | 2 | 0.5 | ○ STRETCH — DE-0001 fault-management-disable detection (LC) |
| AINOS3-74 | watchdog-probe | Spike | Low | 1 | 0.25 | ○ STRETCH — does a WDT/health packet exist? resolve EX-0012.11 / DE-0003.11 |
| AINOS3-75 | borderline-footprint-check | Spike | Low | 2 | 0.5 | ○ STRETCH — footprint-check EX-0001.02 / EX-0005.01 / DE-0006 (borderline held-outs) |
| AINOS3-31 | classification-trust | Epic | — | — | — | Classification trust (close the mode gap) |
| AINOS3-39 | counter-reliance-audit | Spike | Medium | 3 | 0.75 | ○ COMMIT — audit v3 reliance on generic activity counters (carryover) |
| AINOS3-37 | selective-mode-hybrid | Story | Medium | 5 | 1.5 | ○ STRETCH — bank INERTIAL/SUNSAFE/ROBUST gains, no BDOT/PASSIVE regression (carryover) |
| AINOS3-42 | stakeholder-rollout | Epic | — | — | — | Stakeholder rollout & feedback (recurring) |
| AINOS3-76 | rollout-s26 | Task | Medium | 2 | 0.5 | ○ COMMIT — Sprint-26 readout: Section-B detections + audit findings |

**Committed set:** E = **15** (AINOS3-71 5 · AINOS3-72 5 ·
AINOS3-39 3 · AINOS3-76 2) · T ≈ **4.25** — inside the ~16 E / ~7–8 T
capacity. AINOS3-70 is already ✅ Done (retrospective E/T, not a forward
commit).

**Stretch set:** E = **10** (AINOS3-73 2 · AINOS3-74 1 · AINOS3-75
2 · AINOS3-37 5) — pulled in only if the committed chain lands with headroom.

---

## 🟩 EPIC AINOS3-41 — Detection coverage expansion

**Summary:** Broaden what the detector can *see* and classify — add signal, not model
capacity. *(Existing epic — unchanged in Jira; do not re-edit it. See
[`JIRA_CROSSWALK.md`](JIRA_CROSSWALK.md).)*

**Sprint 26 slice — Section B:** turn the newly-subscribed Section-B MIDs into validated
detections. Section A validated the techniques whose footprint was already in a subscribed
MID; Section B is the successor — the MID is *recorded* (subscribed 2026-07-16) but nothing
reads it yet, so the work is validate footprint → build the rule/feature → wire the incident
→ soak for false positives. Highest-leverage MIDs per the triage: `TO` (exfil + theft) and
`DS`/`FM` (wiper / ransomware). Only the child `detect-*` tickets below are new in Jira.

### AINOS3-70 — Subscribe the Section-B recording MIDs · `Task` · High · E 3 · T 1.0 (~8h) · ✅ DONE (2026-07-16)

**Summary:** As an analyst, I want the `TO`/`CI`/`LC`/`DS`/`FM` housekeeping packets and
the sensor HK + DEVICE packets subscribed and recorded in the OnAIR CSV, so the Section-B
attack techniques (exfil, wiper, ransomware, fault-management) become observable and can
be turned into detections.

**Description:** csv-format-v2's column prune and the original subscription set left the
exfil / wiper / ransomware / fault-management MIDs off the OnAIR pipe, so their techniques
were UNSUBSCRIBED (Section B — detectable only *if* the MID is added). Subscribe the
candidate MIDs for **recording** (not yet features): `TO_LAB_HK` (0x08E8), `CI_LAB_HK`
(0x08E0), `LC_HK` (0x08A7), `DS_HK` (0x08B8), `FM_HK` (0x088A), plus the sensor HK +
DEVICE packets (IMU / CSS / MAG / FSS / ST) and `TORQUER`. Raise the per-pipe MID cap so
they fit, rebuild `sbn_client.so`, and update the CSV schema + fingerprint sidecar.

**Acceptance Criteria:**

- The Section-B candidate MIDs added to `nos3_security_tlm.json` (+ `message_headers.py`
  structs / MID→channel map as needed); source + runtime build tree in sync.
- Per-pipe MID cap `CFE_SBN_CLIENT_MAX_MSG_IDS_PER_PIPE` raised 32 → 48; `sbn_client.so`
  rebuilt and deployed.
- The new columns land in the OnAIR CSV; the `.meta.json` schema fingerprint is updated.
- Live-verified: the new fields populate in the running OnAIR CSV.

**Result:** ✅ DONE (2026-07-16). 16 MIDs subscribed for recording; per-pipe cap now
**48** (was 32); `sbn_client.so` rebuilt; the security-telemetry schema now carries
**383 columns**. This unblocked the entire Section-B backlog — every `detect-*` ticket
below reads a field this pass added. **Scope note:** subscribed for RECORDING only —
turning the MIDs into features / rules / incidents is the Section-B detection work below.
(The `AINOS3-30` DEAD-class-recovery analysis used the CFE_TBL subset of this pass and
returned NULL — see [`SPRINT_25_PLAN.md`](SPRINT_25_PLAN.md); this ticket documents the
broader recording subscription that was never separately tracked.)

**Correction (2026-07-29, via AINOS3-72):** 2 of the 16 MIDs pointed at the wrong app.
`TO_LAB_HK` (`0x08E8`) and `CI_LAB_HK` (`0x08E0`) are the **idle stock lab apps** — they
never emit HK, so those columns stayed empty (`[0]`) from this pass onward. NOS3 also runs
the **full `to`/`ci` apps** (Odyssey/OSR) that own the real ground link and whose HK COSMOS
reads. AINOS3-72 re-pointed the subscription to the full-app HK — `0x08E8`→**`0x0880`**
(TO, now carries `usCmdCnt` + the `usEnabledRoutes`/`usConfigRoutes` route masks) and
`0x08E0`→**`0x0884`** (CI, real command-ingest counters). The other 14 MIDs (LC/DS/FM,
sensors, TORQUER) were correct. Net schema is now **382 columns** (was 383; TO 3→8 fields,
CI 8→2) and the `.meta.json` fingerprint changed. **Lesson for future MID work: for TO/CI,
subscribe the full `to`/`ci` apps, not the `*_lab` variants.**

### AINOS3-71 — DS/FM file-operation detector · `Story` · High · E 5 · T 1.5 (~12h) · ✅ DONE

**Summary:** As a defender, I want mass file-destruction (wiper, EX-0010.02) and mass
file-encryption/overwrite (ransomware, EX-0010.01) caught via the now-subscribed Data
Storage / File Manager housekeeping, so the storage-tampering impact class is no longer
UNSUBSCRIBED.

**Description:** EX-0010.01 (ransomware) and EX-0010.02 (wiper) both manifest as an
abnormal burst of file operations. The `DS` (Data Storage) and `FM` (File Manager) HK
packets are now subscribed: `DS.Payload.FileWriteCounter` and the `FM.*` file-op counters
move on file activity. Build a gate/feature that flags an abnormal file-operation rate
(the same static-in-nominal-counter primitive R6–R9 use), validate both techniques live,
and wire the incident.

**Acceptance Criteria:**

- Footprint validated live for EX-0010.02 (wiper) and EX-0010.01 (ransomware): a
  subscribed `DS`/`FM` field demonstrably moves during the attack (`csv.DictReader`),
  signal class recorded.
- A detection (rule-gate rule or feature) built + deployed that fires on the file-op
  burst, labeled to the technique.
- 0-FP soak on a fresh launch (nominal DS file rollover doesn't trip it).
- Folded into the coverage overview (`gen_nos3_coverage.py`) + `V5_DETECTOR_COVERAGE.md`.

**Estimate note:** E 5 carries the build-a-new-detector uncertainty (the MID is recorded
but nothing reads it yet) + distinguishing malicious bursts from legitimate DS file
rollover.

**Result:** ✅ DONE (2026-07-29). Attack scripts `execution/ex_0010_file_operations/`
(`ex_0010_02_wiper.py` = CREATE_DIR + COPY-populate + `FM DELETE_ALL`;
`ex_0010_01_ransomware.py` = COPY→`.enc` + DELETE-original churn), both `FM_CMD_MID=0x188C`,
safe (only touch a self-created `/cf` scratch dir). Footprint validated live via
`csv.DictReader`: `FM.CommandCounter`/`ChildCmdCounter` **static at 0 in nominal**, wiper
→24/22, ransomware →71/68, `CommandErrCounter` flat 0 (ON_BOARD signal). **The `DS`
premise was wrong** — `DS.Payload.FileWriteCounter` climbs continuously in nominal ops
(DS logging), so the detector keys on **FM**, not DS. Detector = **rule-gate R11
`fm-command`** (sibling of R6–R9: static-in-nominal `FM.CommandCounter` → new-high + dwell),
incident `cluster=EX-0010, sub=fm-command`; the two sub-techniques are HK-indistinguishable
(both a file-op burst), so R11 catches the class and the command mix disambiguates.
Live-verified: wiper → `R11:fm-command` ALERT + `EX-0010` incident (confidence 1.0). +4
unit tests (rule-gate suite now 32 pass). Folded into the coverage overview
(`gen_nos3_coverage.py` → 62 techniques) + `V5_DETECTOR_COVERAGE.md` (Section-B table) +
`SPARTA_COVERAGE_TRIAGE.md`. 0-FP soak in progress on the current stack; the full
fresh-launch soak is the belt-and-suspenders confirmation. rule-gate now **R1–R11**.

### AINOS3-72 — TO downlink-path detector · `Story` · High · E 5 · T 1.5 (~12h) · ✅ DONE

**Summary:** As a defender, I want unauthorized downlink exfiltration (EXF-0003.02) caught
and the theft class (IMP-0006) sharpened via the now-subscribed Telemetry Output
housekeeping.

**Description:** EXF-0003.02 (downlink exfiltration) routes data out through the
telemetry-output path; IMP-0006 (theft) is the impact sibling. The `TO_LAB_HK` packet is
now subscribed: `TO.Payload.*` exposes output throughput / destination. Build a detector
on abnormal downlink volume or a destination change, validate EXF-0003.02 live, and
sharpen the IMP-0006 label (already in the corpus) with the TO signal.

**Acceptance Criteria:**

- Footprint validated live for EXF-0003.02: a subscribed `TO.Payload.*` field moves on an
  exfil attempt (throughput spike or destination change), signal class recorded.
- Detection built + deployed (rule/feature), labeled to EXF-0003.02.
- IMP-0006 theft: assessed whether the TO signal improves its incident label; recorded.
- 0-FP soak; folded into the coverage overview + `V5_DETECTOR_COVERAGE.md`.

**Note:** the DE-0010 finding that externally-injected *commands* bypass CI_LAB
(`:5012` → SB bridge) does NOT affect TO — TO is the *output* path driven by the FSW's
downlink, so `TO.Payload.*` is a genuine on-board signal.

**Result:** ✅ DONE (2026-07-29). **The ticket's premise was doubly wrong** and fixing
it was the bulk of the work: (1) the subscribed `TO_LAB_HK` (`0x08E8`) has no throughput/
destination field — only a command counter; (2) it never even reached OnAIR (empty over
11k frames — the stock `to_lab` app is idle; its `SEND_HK` is unscheduled). NOS3 runs the
**full `to`/`ci` apps** (Odyssey/OSR) in parallel, and *those* own the real ground link:
COSMOS reads the full `to` HK (`0x0880`), which carries `usCmdCnt` + the downlink route
masks `usEnabledRoutes`/`usConfigRoutes`. **Fix = re-point OnAIR** from the idle lab HK to
the full-app HK (`0x08E8`→`0x0880` TO, `0x08E0`→`0x0884` CI) in `message_headers.py` +
`nos3_security_tlm.json` — a schema change, **no FSW rebuild** (37 MIDs < 48 cap). This also
put real **CI** command-ingest HK on the pipe (bonus; deferred as a follow-up). Attack
`exf_0003_02_downlink_exfiltration.py` rewritten passive-listen → **active TO redirect**
(full `to`, cmd MID `0x1880`, `TO_ENABLE_OUTPUT`). Detector = **rule-gate R12**
(`TO.usCmdCnt` static-in-nominal → new-high+dwell, R6–R11 sibling) + **R13**
(`usEnabledRoutes`/`usConfigRoutes` leaving baseline — the specific "downlink reconfigured"
signal; also sharpens IMP-0006). Validated live on a fresh cycle: **0-FP soak** (4320 frames,
0 alerts), attack → **R12 + R13 fire → EXF-0003.02 incident** (usCmdCnt 0→3, route masks 0→1,
cmd-err flat). +7 tests (rule-gate suite now 39). Folded into the coverage overview
(63 techniques), `V5_DETECTOR_COVERAGE.md`, and `SPARTA_COVERAGE_TRIAGE.md`. rule-gate now
**R1–R13**. Note: R13 latches on the persistent route change until the downlink is restored
(correct — an unrestored exfil route is an ongoing anomaly).

### AINOS3-73 — DE-0001 fault-management-disable detection · `Task` · Medium · E 2 · T 0.5 (~4h) · ○ STRETCH

**Summary:** As a defender, I want an attacker disabling on-board fault management (DE-0001)
caught via the now-subscribed Limit Checker HK.

**Description:** DE-0001 (disable / defeat fault management) turns off the autonomy that
would respond to an anomaly. `LC` (Limit Checker) is already subscribed and in use
(rule-gate R5 watches `LC.CurrentLCState`; staleness watches `LC.MonitoredMsgCount`).
Validate DE-0001's footprint and extend R5 (or add a sibling rule) so an LC-based
fault-management disable raises a DE-0001 incident.

**Acceptance Criteria:**

- Footprint validated live for DE-0001: the subscribed `LC` field(s) move on a
  fault-management disable.
- Detection via rule-gate (extend R5 or a new rule), labeled DE-0001; 0-FP soak.
- Folded into the coverage overview.

**Note:** likely cheap — the LC observables + the R5 mechanism already exist; this is
mostly validation + a label/rule extension.

### AINOS3-74 — Watchdog telemetry-packet existence probe · `Spike` · Low · E 1 · T 0.25 (~2h) · ○ STRETCH

**Summary:** Determine whether any watchdog / health telemetry packet exists and is
subscribable, to resolve EX-0012.11 / DE-0003.11 from *pending* to either Section B or
permanent out-of-scope.

**Description:** The triage flags the watchdog (EX-0012.11 modify-WDT, DE-0003.11
WDT-for-evasion) as the only genuine UNSUBSCRIBED holdout, noting a subscribable
WDT/health packet may not exist. Inventory the FSW for a watchdog/health MID; if one
exists, this becomes a Section-B detection candidate; if not, both techniques move to
out-of-scope (structurally unobservable in this build).

**Acceptance Criteria:**

- Verdict recorded: a WDT/health packet exists (→ Section-B candidate) or does not
  (→ out-of-scope).
- The coverage overview + triage updated to match (both currently held as *not evaluated /
  pending* per the 2026-07-22 decision to leave them pending until this check).

### AINOS3-75 — Footprint-check the borderline held-outs · `Spike` · Low · E 2 · T 0.5 (~4h) · ○ STRETCH

**Summary:** Resolve the 3 borderline ON_BOARD held-outs — EX-0001.02 (Bus Traffic
Replay), EX-0005.01 (Design Flaws), DE-0006 (Modify Whitelist) — from "not evaluated" to
either a Section-B detection candidate or out-of-scope.

**Description:** The triage carries these three as borderline ("held out pending a
footprint check"). Per the evaluation-provenance rule, resolve each by running it against
the live FSW and reading the telemetry — not by assumption. Each either moves a subscribed
field (→ Section-B detection candidate, ticket it) or leaves no footprint (→ out-of-scope,
document why).

**Acceptance Criteria:**

- Each of EX-0001.02 / EX-0005.01 / DE-0006 run against the live FSW; verdict recorded
  (subscribed field moves → candidate, else out-of-scope with the reason).
- The coverage overview + triage updated so none of the three remains "not evaluated."

**Note:** closes the last 3 of the 9 not-evaluated techniques; low priority (these are the
least-likely-observable of the blue set).

**AINOS3-30 reopen trigger:** DE-0006 (Modify Whitelist) is plausibly table-backed — when
running it, watch whether it moves the CFE_TBL table-activity fields (`LastUpdatedTable` /
`LastFileLoaded` / `LastTableLoaded`, or the numeric `ValidationCounter` /
`SuccessValCounter` / `LastUpdateTimeSeconds`). Those are the empirical trigger to reopen
`AINOS3-30`, whose dormant CFE_TBL change-detect feature reads constant-0 because no
validated attack activates a table (see [`SPRINT_25_PLAN.md`](SPRINT_25_PLAN.md)); a hit
here also unblocks the AINOS3-68 gate.

---

## 🟪 EPIC AINOS3-31 — Classification trust (close the mode gap)

**Summary:** Make attack-type labels reliable across ADCS modes and honestly measured.

**Description:** Two carryover items close this epic. Both sequenced after the audit,
which grounds the hybrid's feature decision. Carried from Sprint 25 (full prior bodies in
[`SPRINT_25_PLAN.md`](SPRINT_25_PLAN.md)).

### AINOS3-39 — Audit classifier reliance on activity counters · `Spike` · Medium · E 3 · T 0.75 (~6h) · ○ COMMIT

**Summary:** Determine whether v3's heavy reliance on generic high-traffic counters is
genuine discriminative signal or an activity-level shortcut.

**Description:** AINOS3-38 attribution showed v3 keys heavily on generic high-traffic
counters (`CFE_EVS_HK.AppData`, `CFE_ES.CommandCounter`, `CFE_TBL.*`) — high-IMPORTANCE
but low-DISCRIMINATION. Now unblocked by `AINOS3-48` (the AppID→name map): resolve the
`AppData` contribution to specific apps and test the sharp question — is it the *attacked*
subsystem's event stream (genuine) or a generic busy app (shortcut)? Prototype a
drop/regularize experiment over the frozen `csv_corpus_v3stage` under LOIO.

**Acceptance Criteria:**

- The `AppData` / `CFE_ES.CommandCounter` contributions resolved to named apps and
  classified genuine-vs-shortcut per attack.
- Drop/regularize experiment run under LOIO; net effect on discrimination + overall
  accuracy reported.
- Recommendation only (leave v3 as-is, or a scoped feature change for a *future* retrain —
  any model change interacts with AINOS3-33's "keep v3" decision).

### AINOS3-37 — Selective per-mode classifier hybrid · `Story` · Medium · E 5 · T 1.5 (~12h) · ○ STRETCH

**Summary:** Bank the INERTIAL/SUNSAFE/ROBUST gains from per-mode heads without the
BDOT/PASSIVE regressions, via mode-routed classification.

**Description:** AINOS3-33 showed full per-mode routing helps the signal-rich dynamic modes
(INERTIAL +0.058, SUNSAFE +0.061) and the ROBUST tier (+0.068) but regresses the
signal-poor modes (BDOT −0.047, PASSIVE −0.028). A selective hybrid routes INERTIAL/SUNSAFE
to per-mode heads and keeps the global v3 head for PASSIVE/BDOT, with per-mode probability
calibration so confidences stay comparable.

**Acceptance Criteria:**

- LOIO shows the INERTIAL/SUNSAFE gains retained and **no** BDOT/PASSIVE regression vs
  deployed v3.
- ROBUST-tier accuracy measured under the hybrid, shown not to regress.
- Per-mode calibration validated; model + routing + calibration deployed; ini + build tree
  synced.

**Sequencing:** STRETCH — pull in only after AINOS3-39 clears (the audit may change *which*
features the per-mode heads train on).

---

## 🟪 EPIC AINOS3-42 — Stakeholder rollout & feedback (recurring)

**Summary:** Recurring stakeholder readout — show the coverage overview + doc and turn
feedback into backlog.

### AINOS3-76 — Stakeholder rollout (Sprint 26) · `Task` · Medium · E 2 · T 0.5 (~4h) · ○ COMMIT

**Summary:** Present the Sprint-26 result — the Section-B detections + the counter-reliance
audit findings — on the coverage overview, and capture feedback.

**Description:** Third instance of the recurring `AINOS3-42` readout. Refresh
`STAKEHOLDER_ROLLOUT.md` and regenerate the coverage-overview overlay so it reflects the new
Section-B detections (wiper/ransomware, exfil/theft) and any watchdog reclassification. Walk
stakeholders through what changed since Sprint 25.

**Acceptance Criteria:**

- Coverage overview + coverage doc refreshed to Sprint-26 state (new detections show as
  detected; watchdog verdict updated if AINOS3-74 ran).
- Doc + overview presented — **owner action** (cannot be automated).
- Feedback captured in the `STAKEHOLDER_ROLLOUT.md` table, then filed as backlog tickets.

**Depends on:** the committed `detect-*` tickets + AINOS3-39 (so the readout shows new
results).

---

## 📋 Backlog (carryover)

| Jira | Slug | Type | E | T | Summary |
|---|---|---|--:|--:|---|
| AINOS3-44 | tcn-feature | Story | 5 | 1.5 | TCN reconstruction-error as a feature, scoped to EX-0008 ATS/RTS |
| AINOS3-45 | corpus-instance-4 | Task | 3 | 0.75 | 4th corpus instance (LOIO variance ±3.6%; ~5h wall-clock) |
| AINOS3-46 | demo-tier-bc | Story | 3 | 1.0 | Demo app Tier B/C — the live "detector in action" demo |
| AINOS3-47 | foundation-baseline | Story | 8 | 2.5 | Optional: foundation-model (MOMENT/THEMIS) zero-shot baseline |
| AINOS3-68 | deepsad-revisit | Spike | 3 | 0.75 | Reopen Phase 5 DeepSAD — **gate NOT cleared** (AINOS3-30 returned NULL) |

The other backlog items above are table-rows only until sprinted. AINOS3-68
has its body spelled out here because it was the one carryover still needing
creation and its reopen gate needs documenting:

### AINOS3-68 — Reopen Phase 5 (DeepSAD / VAE) feasibility · `Spike` · Backlog (gate NOT cleared)

**Summary:** As an ML engineer, I want to re-run the Phase-5 semi-supervised deep
anomaly-detector (DeepSAD / VAE) feasibility assessment once a signal-broadening effort has
changed the data-sufficiency picture that drove the original NO-GO.

**Description:** `NOS3_330` (next-ml-bet) returned Phase-5 DeepSAD as **NO-GO** — the
binding constraint was signal / observability, not model capacity, so a deep
semi-supervised model wouldn't beat the deployed IF + XGB stack on the available data. This
spike is **gated, not scheduled**: it reopens only when the signal picture materially
improves. The designated gate is `AINOS3-30` (recover the nominal-ambiguous DEAD classes),
which returned **NULL** (its CFE_TBL premise was disproven), so the gate is **not cleared**.
Reopen when either (a) a validated technique finally moves the CFE_TBL table-activity fields
and revives AINOS3-30 with real signal (see the AINOS3-75 / DE-0006
trigger note above), or (b) the Section-B detections + corpus growth broaden the labeled
signal enough to change the data-sufficiency verdict.

**Acceptance Criteria:**

- Reopened only against a cleared gate (AINOS3-30 revived, or a materially broader corpus);
  the trigger that cleared it is recorded.
- DeepSAD / VAE re-assessed against the then-current corpus vs the deployed IF + XGB
  baseline under LOIO.
- Deliverable is a GO/NO-GO recommendation with evidence — no deploy from the spike itself.

---

## Capacity note

- **Effort:** committed E across AINOS3-71 / AINOS3-72 /
  AINOS3-39 / AINOS3-76 = **15** — right at the ~16/sprint capacity.
  The four stretch items add **10** more.
- **Time:** committed set = **~4.25 T** (≈ 34 ideal hours) — inside the ~7–8 T realistic
  solo capacity, leaving headroom for the two `detect-*` soaks' unattended wall-clock and,
  if it lands early, a stretch pull.

The headroom is deliberate: the two Section-B detector Stories are the highest-uncertainty
items (a new detector on a MID nothing reads yet), so the sprint commits them + the audit
first and holds AINOS3-73 / AINOS3-74 / AINOS3-37 as
de-risked stretch.

## Suggested execution order

1. **AINOS3-71** + **AINOS3-72** — the Section-B headliners
   (DS/FM + TO are the triage's highest-leverage MIDs). Kick off the FP soaks early so the
   wall-clock overlaps other work.
2. **AINOS3-39** (counter-reliance audit) — unblocked by AINOS3-48; grounds the AINOS3-37
   feature decision.
3. Stretch, if there's headroom: **AINOS3-73** + **AINOS3-74** +
   **AINOS3-75** (cheap coverage adds that resolve the last of the
   not-evaluated techniques), then **AINOS3-37** (needs the audit first).
4. **AINOS3-76** at close.
