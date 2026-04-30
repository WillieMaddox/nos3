# AI Anomaly Detection for NOS3/OnAir — Research Plan

> Comprehensive research synthesis for designing an ML-based anomaly/threat detection
> system on top of the existing NOS3 OnAir telemetry pipeline.
>
> Research date: 2026-04-12. Generated from 5 parallel research agents covering
> SPARTA, OnAir framework, ML architectures, NOS3 reset strategies, and local
> codebase analysis.

---

## TL;DR

**Start simple, iterate fast.** Train an **Isolation Forest** (unsupervised) on
engineered delta-features from nominal telemetry CSV. Working detector in
1-2 weeks. Then layer in **LSTM prediction-error models** (month 2-3) and
**graph-based cross-channel detectors** (month 4+).

**NOS3 is the biggest advantage** — it's a digital twin that generates unlimited
labeled data. For simulation reset, use **cFS ES Power-On Reset**
(`CFE_ES_RESTART` with `RestartType=2`) + NOS Engine **PAUSE/UNPAUSE** — no
Docker teardown needed.

---

## 1. What Kind of Data to Generate

### Nominal Baseline (Train Set)

Run NOS3 through **5-10 operational scenarios**, collecting CSV telemetry for each:

| Scenario | Duration | What It Exercises |
|----------|----------|-------------------|
| Quiescent/safe mode | 2-4 hrs | Minimal commanding baseline |
| Nominal operations | 8-24 hrs | Standard GNC pointing, routine HK |
| Orbit maneuvers | 2-4 hrs | Thruster firings, attitude changes (legitimate transients) |
| Communication passes | 1-2 hrs | COMM subsystem active |
| Mode transitions | 1-2 hrs | Power state changes, app restarts |

**Target: 500K-1M total timesteps of clean nominal data.** At 1 Hz across 273
fields, a 24-hour run produces ~86,400 rows.

**Critical principle** (OPS-SAT benchmark, Komorowski et al. 2024): Train anomaly
detectors on **ONLY nominal data**. One-Class SVM improved AUCPR from 0.659 →
0.762 when trained exclusively on nominal vs. mixed data.

### Attack Data (Evaluation + Supervised Training)

The 289 SPARTA attack scripts in `gsw/attack_scripts/sparta/` are the labeled
data generator. **Fully simulatable** attacks in NOS3:

| Tactic | Key Observable Signatures |
|--------|---------------------------|
| **Execution: Replay** (EX-0001) | Duplicate cmd packets, CMD_COUNT double-increments |
| **Execution: Flooding** (EX-0013) | CMD_COUNT rate 10-100x baseline, SB pipe overflow |
| **Execution: Spoofing** (EX-0014) | GPS position discontinuity, sensor DEVICE_ENABLED → 0 |
| **Execution: Modify Values** (EX-0012) | EPS switch toggling, thruster enable, ADCS mode change |
| **Defense Evasion: Disable FM** (DE-0001) | HS_APPMON → DISABLED, LC_STATE → DISABLED |
| **Defense Evasion: Log Overflow** (DE-0010) | EVS MessageSendCounter 10-50x baseline |
| **Lateral Movement: Bus Exploit** (LM-0002) | 10+ unique MIDs/minute (vs normal 1-3) |
| **Impact: Degradation** (IMP-0004) | 60 rapid cmds to RW/thruster/EPS |
| **Impact: Destruction** (IMP-0005) | Battery discharge, permanent thruster, tumble |
| **Kill Chain Demo** | `demo_gnc_kill_chain.py` chains DE-0001 → EX-0012 → EX-0014 → IMP-0004 |

**Run each attack with parametric variation** — fast/slow injection rate,
small/large perturbation, different target subsystems. Natural data diversity
without SMOTE (which violates physical constraints of counter fields).

### Data Augmentation Strategies

- **Time-warping**: Stretch/compress attack temporal profiles
- **Additive noise**: Gaussian noise at detection boundary thresholds (hard negatives)
- **NOS3-native**: Just re-run attacks with different parameters — the
  simulation IS the augmentation engine

---

## 2. What Data to Feed the Model

### Feature Engineering Hierarchy

**Level 0 — Raw Values** (273 fields from `nos3_security_tlm.json`):
- Counters: `CommandCounter`, `CommandErrorCounter`, `MessageSendCounter`
- State flags: `DeviceEnabled`, `LogFullFlag`, `AppEnableStatus`
- Continuous: GPS position/velocity, IMU accel/gyro, EPS voltage/current
- Checksums: `CFECoreChecksum` (should be constant after boot)

**Level 1 — Rate-of-Change** (most security-relevant):
```
delta_CommandErrorCounter[t] = CommandErrorCounter[t] - CommandErrorCounter[t-1]
delta_MessageSendCounter[t]    -- event rate acceleration (flooding)
delta_NoSubscribersCounter[t]  -- reconnaissance probe indicator
delta_MsgLimitErrorCounter[t]  -- DoS indicator
delta_SysLogBytesUsed[t]       -- log fill rate
```

**Level 2 — Rolling Window Statistics** (windows: 10s, 60s, 300s):
- `mean`, `std`, `max-min`, `count(state_changes)`, `slope`
- 273 fields × 3 windows × 5 stats = 4,095 derived features
- Prune to top 200-500 via mutual information / permutation importance

**Level 3 — Cross-Channel Correlations**:
- EPS current vs. active subsystem count
- IMU angular rate vs. reaction wheel speed
- GPS velocity vs. IMU integrated acceleration
- CommandCounter vs. CommandErrorCounter ratio

**Level 4 — Temporal/Lag Features**:
- `x[t-1], x[t-5], x[t-30]` for sequence models
- Time-since-last-state-change for discrete fields
- FFT periodicity features (HK at 1 Hz — detect period changes)

### The 5 ML Feature Groups for SPARTA Detection

| Feature Group | Type | Detects |
|---------------|------|---------|
| **Command Rate** | `cmd_count_rate_<subsys>`, `unique_mids_per_window` | Flooding, Replay, Recon, Lateral Movement |
| **State Transitions** | `eps_switch_state`, `thruster_enabled`, `adcs_mode`, `sensor_enabled_*` | Value modification, Spoofing |
| **Anomaly Indicators** | `evs_msg_trunc_rate`, `unregistered_app_counter`, `log_full_flag` | Flooding, Log overflow, Unauthorized code |
| **Cross-Subsystem** | `simultaneous_cmd_spikes`, `sensor_disabled_count`, `fm_disabled_and_state_change` | Kill chains, Multi-technique attacks |
| **Physics Validation** | `attitude_quat_rate`, `battery_v_vs_expected`, `gyro_vs_rw_torque` | Sensor spoofing, Actuator injection |

---

## 3. Training Paradigm: Supervised vs. Unsupervised vs. RL

### Short Answer
**Start unsupervised, layer in supervised, defer RL.**

### Detailed Rationale

**Unsupervised (primary approach):**
- Train on ONLY nominal data — model learns the manifold of normal behavior
- Anything far from that manifold is anomalous
- **Sidesteps class imbalance entirely** — no labeled attacks needed for training
- Evaluation still uses labeled attack data (from SPARTA scripts)
- Best models: Isolation Forest, Autoencoder, One-Class SVM, VAE

**Semi-supervised (intermediate):**
- Train primarily on nominal data but incorporate small set of labeled attacks
  to guide the boundary
- **DeepSAD** (Ruff et al., 2020) is ideal — NN maps normal data to a
  hypersphere; labeled anomalies push the boundary
- Best for attack-type classification ("this is EX-0013 flooding" vs. just "anomaly")

**Supervised (attack classification layer):**
- XGBoost/Random Forest on labeled data from comprehensive attack campaigns
- Feature importance output tells you exactly which fields matter per attack type
- Use as a meta-learner over unsupervised anomaly scores

**Reinforcement Learning (later-stage enhancement):**
- **NOT for detection itself** — RL is not a natural fit for anomaly detection
- Three relevant applications:
  1. **Adaptive thresholding**: RL adjusts detection thresholds by operational
     mode (relax during maneuvers, tighten during quiet ops)
  2. **Automated response**: After detection, RL learns optimal response
     (isolate subsystem, safe mode, alert)
  3. **Active learning**: RL decides which unlabeled windows to present to
     human experts for labeling

**Evaluation metric**: Use **AUCPR** (area under precision-recall curve), NOT
accuracy or AUCROC. AUCROC is misleadingly optimistic under extreme imbalance.

---

## 4. Model Architectures — What to Use

### Tier 1: Simplest Effective (Weeks 1-2)

**Isolation Forest + Delta Features**

```python
from sklearn.ensemble import IsolationForest

# 273 raw fields + delta features for all counters
model = IsolationForest(n_estimators=200, contamination=0.01)
model.fit(nominal_feature_matrix)
scores = model.decision_function(test_data)  # negative = anomalous
```

Schwarz et al. (2023, CEAS Space Journal) explicitly demonstrated that
**Isolation Forest frequently matches or outperforms deep learning** on
spacecraft telemetry when deep models aren't carefully tuned.

### Tier 2: Temporal Awareness (Month 2-3)

**LSTM Prediction-Error with Dynamic Thresholding** (NASA Telemanom, Hundman 2018)

Per-subsystem LSTMs trained to predict next-timestep values. Anomaly = high
prediction error.

```
Input:  (batch, seq_len=60, n_features)  # 60-second lookback
LSTM:   128 units, return_sequences=True
LSTM:   64 units
Dense:  n_features  # predict next timestep
Loss:   MSE between prediction and actual
Anomaly: squared_error > dynamic_threshold
```

NASA achieved **87.5% precision, 80.0% recall** on SMAP/MSL. Code:
https://github.com/khundman/telemanom

**Alternative: Temporal Convolutional Network (TCN)** — 2025 MDPI review
reports TCN achieving **94% precision** with faster training than LSTM.

### Tier 3: Cross-Channel + Ensemble (Month 4-6)

**Multi-Scale Graph-Temporal Ensemble**

| Layer | Model | Purpose | Speed |
|-------|-------|---------|-------|
| Fast | Isolation Forest + CUSUM | Catch obvious attacks | Microseconds |
| Temporal | TCN or Transformer | Subtle temporal pattern violations | Milliseconds |
| Graph | Graph Attention Network | Physically inconsistent telemetry | Milliseconds |
| Meta | XGBoost on all anomaly scores | Final decision + attack classification | Microseconds |

Graph models spacecraft as nodes (20 MID channels) with edges encoding physical
dependencies (POWER → all, GNC sensors → ADCS → actuators, CFE_SB → all apps).

### Comparison Matrix

| Model | Temporal? | Data Needed | Training Time | Interpretable? | NOS3 Fit |
|-------|-----------|-------------|---------------|----------------|----------|
| Isolation Forest | No (engineer features) | Nominal only | Minutes | High | **Start here** |
| One-Class SVM | No | Nominal only | Hours | Medium | Good for per-subsystem |
| Autoencoder | No (or windowed) | Nominal only | Hours | Medium | Good baseline |
| VAE | No (or windowed) | Nominal only | Hours | High (latent space) | Operational mode discovery |
| DeepSAD | No | Nominal + few labels | Hours | Medium | Best semi-supervised |
| XGBoost | No (engineer features) | Labeled both classes | Minutes | **Very high** | Attack classification |
| LSTM | **Yes** | Nominal only | Day+ | Low | NASA-validated |
| TCN | **Yes** | Nominal only | Hours | Low | 94% precision reported |
| Transformer | **Yes** | Nominal (more data) | Day+ | **High** (attention) | Best if enough data |
| GNN/GAT | Cross-channel | Nominal only | Hours | **Very high** (graph) | Root cause isolation |

---

## 5. Novel and State-of-the-Art Ideas

### Foundation Models for Zero-Shot Detection (2024-2025)

- **MOMENT** (Goswami et al., 2024) — 385M parameter T5-based model. Zero-shot
  anomaly detection with no NOS3-specific training.
- **THEMIS** (2025) — Extracts embeddings from Chronos foundation model +
  outlier detection. **Requires NO training on your telemetry.**
- **Foundation Auto-Encoders** (2025) — VAE-based pretrained model. Strong
  zero-shot performance claims.

**Practical value**: Test a foundation model on CSV data as a free baseline. If
it catches 50% of attacks with zero training, that's a floor to beat.

### Graph Neural Networks for Root Cause Isolation

Beyond "anomaly detected" → "here's WHY and WHERE it started":
- Model spacecraft as graph: nodes = subsystems, edges = physical/logical deps
- When anomaly fires, trace causal chain backward through the graph
- **GTAD** and **MST-GAT** architectures designed for exactly this

### Digital Twin + Curriculum Learning

**LATTICE framework** (ACM TOSEM, 2023):
1. Generate unlimited normal data from NOS3 (digital twin)
2. Generate labeled attack data by running SPARTA scripts
3. **Curriculum learning**: Train on easy attacks first (massive counter spikes),
   progressively introduce subtle ones (slow-drift sensor spoofing)
4. Model learns a difficulty-ordered decision boundary

### Causal Inference for Attack Attribution

- **Granger causality** tests between channels reveal directional dependencies
- When `CommandErrorCounter` and `NoSubscribersCounter` both spike, causal
  analysis determines which caused which
- Maps detected anomalies back to SPARTA kill chain sequences

### SPARTEND (Aerospace Corporation)

Neural network that maps **SPARTA TTPs → DARS detection signatures**. Deployed
on NOAA-20/NOAA-21 satellites. Closest real-world analog. Approach: ensemble of
multiple detectors with a meta-classifier.

---

## 6. Key Papers and References

### Must-Read (directly applicable)

| Paper | Year | Why It Matters |
|-------|------|----------------|
| Hundman et al., "Detecting Spacecraft Anomalies Using LSTMs" | 2018 | NASA JPL foundation paper. SMAP/MSL. Open-source Telemanom. |
| Schwarz et al., "Unmasking overestimation" | 2023 | **Simple models often beat deep ones** on spacecraft data. |
| Komorowski et al., "OPS-SAT benchmark" | 2024 | ESA. 30-algorithm benchmark on real CubeSat telemetry. |
| Martinez-Heras et al., "ESA-ADB" | 2024 | Annotated real telemetry from 3 ESA missions. |
| Pilastre et al., "Synthetic satellite telemetry" | 2024 | Library for generating synthetic telemetry with injected anomalies. |
| "OnAIR: Applications of NASA OnAIR Platform" | 2025 | AAAI. YOLO + cFS integration on embedded hardware. |

### Public Datasets to Benchmark Against

| Dataset | Source | Link |
|---------|--------|------|
| SMAP/MSL | NASA JPL | https://www.kaggle.com/datasets/patrickfleith/nasa-anomaly-detection-dataset-smap-msl |
| OPS-SAT-AD | ESA | https://zenodo.org/records/12588359 |
| ESA-ADB | ESA | https://arxiv.org/abs/2406.17826 |

### Public Code

| Tool | Source | Link |
|------|--------|------|
| Telemanom (LSTM) | NASA JPL | https://github.com/khundman/telemanom |
| NPO-50838-1 | NASA JPL | https://software.nasa.gov/software/NPO-50838-1 |
| OPS-SAT-AD benchmarks | KP Labs | https://github.com/kplabs-pl/OPS-SAT-AD |

---

## 7. OnAir Framework — How to Use It Better

### Current OnAir Usage in the Wild

1. **YOLO Crater Detection** (IEEE Aerospace 2025) — Deep learning model plugged
   into OnAir running on Teledyne LS1046 + Google Coral TPU. Proves arbitrary ML
   works as OnAir plugins.
2. **DASS Workshop 2025** — OnAir as part of standard for distributed multi-asset
   missions.
3. **SPAICE 2024** — Overview with onboard experimental flight payload.
4. **cFS Integration Example** — `github.com/the-other-james/cFS/tree/OnAIR-integration`

### Our Integration Is Already More Advanced Than Upstream

- Upstream SBN adapter has `# note does not work for arrays?` comment. Our
  `_ctypes_to_python()` recursive converter fixes this.
- 20 subscribed MIDs vs. upstream's single-MID example.
- 273 fields with security-annotated metadata.

### OnAir Plugin Pipeline (what plugs in where)

```
[Knowledge Rep]     Currently: generic + csv_output
                    Recommended additions: kalman_filter (built-in)
                    → Receives: low_level_data (raw 273 fields)
                    → Outputs to: high_level_data['vehicle_rep']

[Learner]           Currently: EMPTY
                    Recommended: isolation_forest_plugin (NEW)
                    → Wraps scikit-learn IF on engineered features
                    → Receives: low_level + high_level (KR outputs)
                    → Outputs: per-timestep anomaly scores

[Planner]           Currently: EMPTY
                    Recommended: attack_classifier_plugin (NEW)
                    → XGBoost meta-classifier on anomaly scores
                    → Receives: only high_level_data (no raw)
                    → Outputs: {attack_type, confidence, affected_subsystem}

[Complex Reasoner]  Currently: EMPTY
                    Recommended: response_recommender_plugin (NEW)
                    → Receives all upstream outputs
                    → Recommends operator actions based on attack type
                    → Eventually could become RL-based adaptive responder
```

### Plugin API (minimal)

```python
class Plugin(AIPlugin):
    def __init__(self, name, headers):
        super().__init__(name, headers)
        # init any model here

    def update(self, low_level_data=None, high_level_data=None):
        # receive new data each step
        pass

    def render_reasoning(self):
        # return any Python object
        return {...}
```

Any Python library (PyTorch, scikit-learn, XGBoost) works inside.

---

## 8. Simulation Reset Without Docker Recycling

### Tiered Reset Model

| Tier | What to Reset | Time | When to Use |
|------|---------------|------|-------------|
| **0** | Single cFS app via `CFE_ES_RESTART_APP` | ~2s | Attack modified one app's state |
| **1** | Kill `core-cpu1`, `fsw_respawn.sh` auto-relaunches with `-R PO` | ~10s | Tables, SB routing, multiple apps corrupted |
| **2** | Reset FSW + 42 dynamics + truth42sim containers | ~20s | Attitude/orbit corrupted by actuator commands |
| **3** | Stop/restart all sim containers (keep OpenC3) | ~40s | NOS Engine state corrupted |
| **4** | `make stop && make launch` | ~90s | Ground system or network corrupted |

### The Key Commands

**FSW-only reset** (Tier 1 — sufficient for most SPARTA attacks):
```bash
# Via OpenC3:
cmd("CFS_DEBUG CFE_ES_RESTART with RESTARTTYPE 2")  # Power-On Reset

# Or via Docker:
docker exec sc01_nos_fsw kill -TERM $(pidof core-cpu1)
# fsw_respawn.sh relaunches with -R PO in ~6 seconds
```

**NOS Engine time control** (freeze sim during reset, via `nos-terminal` container):
```
PAUSE      # freeze all simulators
UNPAUSE    # resume after reset complete
RUN <N>    # run N more seconds then pause
UNTIL <T>  # run until absolute time T then pause
```

### ES Reset Command Reference

| FC | Name | Purpose |
|----|------|---------|
| 2 | `CFE_ES_RESTART_CC` | Processor (1) or Power-On (2) reset |
| 4 | `START_APP_CC` | Dynamically load and start a new app |
| 5 | `STOP_APP_CC` | Halt and remove an app |
| 6 | `RESTART_APP_CC` | Restart single app without full reset |
| 7 | `RELOAD_APP_CC` | Stop, reload from file, restart an app |
| 10 | `CLEAR_SYSLOG_CC` | Clear system log |
| 12 | `CLEAR_ER_LOG_CC` | Clear exception/reset log |
| 19 | `RESET_PR_COUNT_CC` | Reset processor reset counter |

### Automated Test Harness Flow

```python
for attack in attack_scenarios:
    # 1. Collect baseline
    time_controller.unpause()
    wait_for_stabilization(30)          # poll CFE_ES_HK.CMDCOUNTER
    time_controller.run(seconds=60)     # 60s nominal
    label_data("nominal", attack.id)

    # 2. Execute attack
    time_controller.unpause()
    attack.execute()                    # run SPARTA script
    time_controller.run(seconds=120)    # let effects propagate
    label_data("attack", attack.id)

    # 3. Reset (tier depends on attack)
    time_controller.pause()
    if attack.corrupts_dynamics:
        restart_42_and_fsw()            # Tier 2, ~20s
    else:
        restart_fsw_only()              # Tier 1, ~10s
    time_controller.unpause()
    wait_for_stabilization(30)
```

### Data Labeling Strategy

- **Marker-based**: Send `CFE_ES_NOOP` at each phase boundary — shows up as a
  command counter step in telemetry
- **Companion label file**: JSON with `{attack_id, phase, start_time, end_time}`
  per segment

---

## 9. Recommended Progression

| Phase | Timeline | What to Build | What You Learn |
|-------|----------|---------------|----------------|
| **1** | Weeks 1-2 | Isolation Forest + delta features as OnAir Learner plugin | Which fields discriminate; baseline false positive rate |
| **2** | Weeks 3-4 | Automated test harness (attack → collect → reset → repeat) | Labeled dataset across all SPARTA attack types |
| **3** | Weeks 5-6 | XGBoost attack classifier on labeled data | Attack-type classification accuracy; feature importance |
| **4** | Weeks 7-10 | LSTM/TCN prediction-error model | Whether temporal modeling catches slow-drift attacks |
| **5** | Weeks 11-14 | VAE or DeepSAD for semi-supervised detection | Latent space structure; operational mode discovery |
| **6** | Weeks 15-18 | Graph model for cross-channel dependencies | Root cause isolation capability |
| **7** | Weeks 19-22 | Ensemble meta-learner + SHAP explainability | Production-grade system |
| **Optional** | Anytime | Foundation model (MOMENT/THEMIS) zero-shot experiment | Free baseline to compare against |

### Concrete First Step

`nos3_security.ini` has empty `LearnersPluginDict`. Write a plugin at
`components/onair/fsw/plugins/isolation_forest/isolation_forest_plugin.py`:

```python
from collections import deque
import numpy as np
from sklearn.ensemble import IsolationForest
from onair.src.ai_components.ai_plugin_abstract.core import AIPlugin

class Plugin(AIPlugin):
    def __init__(self, name, headers):
        super().__init__(name, headers)
        self.model = IsolationForest(n_estimators=200, contamination=0.01)
        self.window = deque(maxlen=60)
        self.trained = False

    def update(self, low_level_data=None, high_level_data=None):
        if low_level_data is None:
            return
        self.window.append(low_level_data)
        if len(self.window) == 60 and not self.trained:
            self.model.fit(np.array(self.window))
            self.trained = True

    def render_reasoning(self):
        if self.trained and len(self.window) == 60:
            score = float(self.model.decision_function([self.window[-1]])[0])
            return {"anomaly_score": score, "is_anomaly": score < -0.5}
        return {"anomaly_score": 0.0, "is_anomaly": False}
```

Slots directly into OnAir's pipeline. CSV output plugin captures anomaly scores
alongside the 273 telemetry fields.

---

## 10. Key Files Reference

| Component | Path |
|-----------|------|
| Telemetry Structs | `components/onair/message_headers.py` (19 ctypes defs, 792 lines) |
| Telemetry Metadata | `components/onair/nos3_security_tlm.json` (21 MIDs, 273 fields, 1676 lines) |
| OnAIR Config | `components/onair/nos3_security.ini` |
| SBN Adapter | `components/onair/fsw/onair/data_handling/sbn_adapter.py` |
| CSV Output | `components/onair/fsw/plugins/csv_output/csv_output_plugin.py` |
| Security Reference | `components/onair/NOS3_SECURITY_LOG_REFERENCE.md` |
| Attack Scripts | `gsw/attack_scripts/sparta/` (289 scripts across 9 tactics) |
| Kill Chain Demo | `gsw/attack_scripts/sparta/execution/demo_gnc_kill_chain.py` |
| FSW Respawn | `scripts/fsw/fsw_respawn.sh` |
| CI Launch | `scripts/ci_launch.sh` |
| Time Driver | `sims/nos_time_driver/src/time_driver.cpp` (PAUSE/UNPAUSE/RUN cmds) |
| ES Reset Impl | `fsw/cfe/modules/es/fsw/src/cfe_es_task.c:602` |
| ES Cmd Defs | `gsw/cosmos/config/targets/CFS/cmd_tlm/ES.txt` |

---

## 11. Key Architectural Insights

1. **NOS3 has ZERO command authentication.** Every well-formed CCSDS packet to
   UDP port 5012 is accepted as legitimate. Detection must be purely
   behavioral/statistical — no crypto layer provides ground truth on command
   legitimacy. ML model must learn operational baseline and flag deviations in
   command rate, state transitions, cross-subsystem correlations, timing.

2. **Our OnAir integration is more advanced than upstream.** The recursive
   `_ctypes_to_python()` in our `sbn_adapter.py` handles nested structs and
   arrays — upstream does not.

3. **We currently only use Knowledge Rep slot.** Learner, Planner, and Complex
   Reasoner slots are empty. That's where the ML models plug in.

4. **The digital twin is the killer feature.** NOS3 + SPARTA scripts generate
   unlimited labeled training data. This is rare in spacecraft ML — most
   researchers fight for scraps of real telemetry. We can generate 1M+
   timesteps with a day of compute.

5. **Start with Tier 1 (FSW-only reset).** Most SPARTA attacks target flight
   software, not dynamics. `docker exec sc01_nos_fsw kill -TERM $(pidof core-cpu1)`
   + `fsw_respawn.sh` = ~10s reset cycle. Reserve Tier 2+ for attacks that
   fire thrusters or corrupt attitude.

6. **Evaluate with AUCPR, not accuracy.** Extreme class imbalance makes AUCROC
   misleadingly optimistic. Precision-recall curve is the right lens.
