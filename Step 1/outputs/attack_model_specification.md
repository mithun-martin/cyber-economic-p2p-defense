# Cybersecurity Attack Model Specification: Step 1 (Final Revision)
**Project:** Cyber-Economic Resilience Under Evolving Attacks  
**Phase:** Step 1 — Data Preparation & Evolving Attacks  
**Document Status:** Final Specification & Architecture Design (Frozen Input: `data/processed/ausgrid_solar_processed.parquet`)  
**Target Implementation:** `src/attack_generator.py`  
**Revision Date:** 2026-10-02  

---

## 1. Threat Model

### 1.1 System Architecture Context
The target cyber-physical system is a decentralized local energy community operating a Peer-to-Peer (P2P) transactive energy market. Residential prosumers are equipped with:
1. Rooftop photovoltaic (PV) solar generation ($GG_t \ge 0$, kW/kWh).
2. General household electricity consumption ($GC_t \ge 0$, kW/kWh).
3. Advanced Metering Infrastructure (AMI) smart meters recording half-hourly interval energy data and transmitting bid/ask telemetry to a local market clearing engine (Continuous Double Auction, CDA).

Each prosumer's market exchange is determined by net demand:
$$P_{\text{net}, t} = GC_t - GG_t$$
- When $P_{\text{net}, t} < 0$, the prosumer has surplus solar energy and enters the CDA as a **Seller** offering an ask of volume $|P_{\text{net}, t}|$.
- When $P_{\text{net}, t} > 0$, the prosumer has net energy deficit and enters the CDA as a **Buyer** offering a bid of volume $P_{\text{net}, t}$.

### 1.2 Adversary Objectives
The adversary seeks to compromise data integrity by mounting False Data Injection Attacks (FDIAs) against prosumer telemetry. The objectives are two-fold:
1. **Economic Fraud (Theft & Market Manipulation):**
   - **Generation Inflation ($GG' > GG$):** A malicious prosumer reports fabricated solar generation to offer non-existent energy in the CDA, seeking unearned cash settlements from peers while causing physical power delivery shortfalls at grid settlement.
   - **Consumption Deflation ($GC' < GC$):** A prosumer under-reports energy usage to avoid paying for consumed grid electricity (classic energy theft).
   - **Strategic Demand Shifting:** Artificial inflation/deflation to influence local clearing conditions during peak tariff windows.
2. **Operational & Resilience Degradation:**
   - Inducing aggregate market imbalances with the downstream objective of impacting utility reserve dispatch and peer settlement.
   - Forcing defensive detectors into high False Positive Rates (FPR), resulting in unnecessary and costly trade mitigations.

### 1.3 Adversary Capabilities & Constraints
- **Access Level:** The adversary has gained unauthorized access to the firmware, communication interface, or local data logger of a subset $\mathcal{C}_{\text{att}} \subset \mathcal{C}$ of smart meters (e.g., through compromised home energy management gateways, insecure API endpoints, or physical optical-port tampering).
- **Stealthiness & Physical Plausibility:** An attack qualifies as an **FDIA** (rather than a simple anomalous fault) if and only if it preserves physical plausibility and avoids trivial tripwire boundary alarms:
  1. **Strict Non-Negativity:** Preserves non-negative real energy readings ($GC' \ge 0$, $GG' \ge 0$).
  2. **Inverter Nameplate Capacity Bound:** Generation cannot physically exceed the prosumer's installed solar inverter rating ($GG'_{i,t} \le \text{Capacity}_i \times 0.5\text{ h}$).
  3. **No Artificial Consumption Ceilings:** General consumption ($GC$) does **not** have an artificial distribution-dependent upper bound (e.g., no $\mu + 4\sigma$ or percentile clamp), as household loads lack an inverter-like physical cap.
  4. **Preservation of Authentic Sensor Characteristics:** The Ausgrid raw dataset exhibits small non-zero nighttime solar generation readings (up to $0.013$ kWh / $13$ Wh, reflecting inverter standby or calibration offsets). The attack generator respects the original measurement behavior and does not enforce a forced-zero rule at night.
  5. **Semantic Coherence:** Alters energy accounting while maintaining plausible intra-day and cross-channel dynamics.
- **Evolving Behavioral Profile:** The adversary does not deploy static attacks indefinitely. Aware that machine learning defenders adapt, the adversary evolves from simple multiplicative shifts to gradual ramping, historical replays, and coordinated multi-agent collusion.

---

## 2. Attack Definitions & Target-Signal Analysis

### 2.1 Attack vs. Sensor Anomaly
A benign sensor fault (e.g., communication dropout, flat-lining, spike noise) typically exhibits uncorrelated, non-contextual artifacts that violate physical bounds or temporal continuity. In contrast, an **FDIA**:
- Is mathematically structured and goal-oriented.
- Maintains plausible correlation with underlying physical conditions.
- Specifically targets the quantity ($GC, GG,$ or $P_{\text{net}}$) that dictates economic settlement and clearing prices in the CDA market.

### 2.2 Target Signal Evaluation (GC vs. GG vs. Both)

| Target Signal | Physical Properties | P2P Market Impact | Attacker Strategy | Feasibility & Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Gross Generation ($GG$)** | Diurnally bounded; active during sunlight; physical upper bound: inverter kWp rating ($\text{Cap}_i$). Preserves raw nocturnal sensor offsets. | Directly dictates prosumer surplus ($P_{\text{net}} < 0$). Inflating $GG$ injects "phantom" energy asks into the CDA. | Attacker inflates solar output during midday to profit from feed-in credits or high peer asks. | **Primary Target for Generation Fraud.** Constrained strictly by PV inverter capacity. Nocturnal sensor baseline is preserved. |
| **General Consumption ($GC$)** | Active 24/7; high stochasticity; driven by human occupancy and appliance cycles. No inverter-like physical ceiling. | Directly dictates prosumer deficit ($P_{\text{net}} > 0$). Deflating $GC$ reduces buyer settlement obligation. | Attacker deflates load during high-price hours to steal power, or inflates load to cause grid distress. | **Primary Target for Consumption Theft.** Non-negativity enforced; no artificial statistical clamp imposed. |
| **Joint ($GC$ and $GG$)** | Multi-channel interaction; preserves joint dependency $P_{\text{net}} = GC - GG$. | Maximizes economic swing by simultaneously inflating generation and deflating consumption. | Correlated multi-channel attack; shifts prosumer from net consumer to net supplier. | **Advanced Attack Mode.** Fully supported in specification to test multi-variate detector capability. |

**Approved Baseline Allocation:** In Phases 2 and 3, target channels are allocated according to: **40% Gross Generation ($GG$)**, **40% General Consumption ($GC$)**, and **20% Joint ($GC$ and $GG$)**.

---

## 3. Mathematical Formulations of Attack Types

Let $x_t \in \mathbb{R}_{\ge 0}$ denote the clean ground-truth measurement of customer $i$ at half-hour interval $t$, where $x_t$ represents $GC_{i,t}$, $GG_{i,t}$, or both. Let $\tilde{x}_t$ denote the compromised measurement transmitted to the market.

### 3.1 Fundamental Rule: At Most One Primary Attack per Observation
To ensure methodological rigor, clear ground-truth attribution, and unambiguous evaluation of continual learning:
$$\text{Clean Observation } x_t \longrightarrow \text{At Most One Attack Transformation } f_{\text{attack}}(x_t) \longrightarrow \text{Attacked Observation } \tilde{x}_t$$

**Prohibited Behaviors:**
- Sequentially chaining multiple attack types on the same observation (e.g., applying Scaling and then Replay).
- Overlapping attack episodes on the same customer/time interval.
- Transforming an already-attacked value with another attack operator.

Every attacked observation in the dataset originates from a single, deterministic transformation applied directly to the pristine clean measurement.

---

### 3.2 Scaling FDIA (Multiplicative Attack)
The scaling attack applies a multiplicative distortion factor $\beta$ to the true measurement:

$$\tilde{x}_t = f_{\text{scale}}(x_t; \beta)$$

- **For General Consumption ($GC$):**
  $$\tilde{GC}_{i,t} = \max\left(0.0, \beta \cdot GC_{i,t}\right)$$
  - *Distinction:* Non-negativity is preserved. **No artificial upper bound ceiling** (such as $\mu + 4\sigma$ or historical percentiles) is imposed as household consumption does not possess a physical nameplate capacity. Plausibility is evaluated post-hoc rather than by hard-coded truncation.
- **For Gross Generation ($GG$):**
  $$\tilde{GG}_{i,t} = \max\left(0.0, \min\left(\text{Capacity}_i \times 0.5\text{ h}, \beta \cdot GG_{i,t}\right)\right)$$
  - *Distinction:* Clamped at physical inverter nameplate capacity ($\text{Capacity}_i \times 0.5\text{ h}$ kWh per half-hour). Authentic small nocturnal sensor readings are transformed multiplicatively or preserved untouched; **no artificial forced-zero rule** is enforced.
- **Scaling Factor $\beta$ Ranges:**
  - *Down-scaling (Theft / Deflation):* $\beta \in [0.30, 0.80]$ (Experimental Assumption informed by theft literature).
  - *Up-scaling (Inflation / Fraud):* $\beta \in [1.25, 2.00]$ (Experimental Assumption informed by solar fraud literature).

*Rationale:* Scaling preserves relative peak/trough intra-day dynamics (shape of the load/solar curve) while shifting the integrated energy volume, making it deceptive to simple threshold detectors.

---

### 3.3 Ramp FDIA (Gradual Temporal Drift Attack)
The ramp attack gradually transitions the telemetry from legitimate values to an altered state over a defined duration $T_{\text{ramp}}$, evading step-change and CUSUM change-point detectors:

$$\tilde{x}_t = \beta(t) \cdot x_t$$

The time-varying scaling factor $\beta(t)$ evolves linearly from unity:

$$\beta(t) = 1.0 + \left(\beta_{\text{target}} - 1.0\right) \cdot \frac{t - t_{\text{start}}}{T_{\text{ramp}}}, \quad \forall t \in [t_{\text{start}}, t_{\text{start}} + T_{\text{ramp}}]$$

After reaching $t_{\text{start}} + T_{\text{ramp}}$, the attack enters a **sustain phase** where $\beta(t) = \beta_{\text{target}}$, or a **decay phase** ramping back down to $1.0$.
- For $GG$, inverter capacity clamping is enforced at all time steps.
- For $GC$, non-negativity is enforced without artificial upper clamps.

*Evolutionary Character:* The ramp attack explicitly embeds temporal non-stationarity. In initial intervals, $|\tilde{x}_t - x_t| < \sigma_{\text{noise}}$, making early detection impossible without cumulative temporal tracking.

---

### 3.4 Replay FDIA (Historical Playback Attack)
The replay attack intercepts legitimate historical meter observations recorded during a past window and plays them back during the current window, masking abnormal physical behavior behind authentic historic telemetry:

$$\tilde{x}_t = f_{\text{replay}}(t; \Delta) = x_{t - \Delta}$$

where $\Delta = k \times 48$ intervals ($k \in \{7, 14, 21\}$ days) represents a **lagged temporal offset**.

**Plausibility & Contextual Rules for Replay:**
1. **Same-Customer Replay:** The replayed sequence must belong to the **same customer** ($i$) to maintain customer-specific load scale and panel capacity invariants.
2. **Day-of-Week Matching:** $\Delta$ must be an integer multiple of 7 days ($k \in \{7, 14, 21\}$) so that weekday/weekend occupancy and appliance habits are preserved.
3. **Temporal Bounds Validity:** The historical reference interval $t - \Delta$ must exist within the valid experimental dataset ($t - \Delta \ge 0$).
4. **Authenticity Without Synthetic Noise:** Replay is executed using raw historical records. **The attack generator does NOT inject synthetic additive noise** merely to inflate the deviation.

**Replay Magnitude Validation Procedure:**
A replay attack is not guaranteed to produce a large numerical deviation (e.g., two consecutive mild Tuesdays may naturally have very similar consumption). Therefore, the attack generator records empirical deviation metrics for every replay episode:
- Absolute deviation: $\delta_t = |\tilde{x}_t - x_t|$.
- Relative deviation (where $x_t > 0.05$ kWh): $\delta_{\text{rel}, t} = |\tilde{x}_t - x_t| / x_t$.
- Episode Mean Absolute Error: $\text{MAE}_{\text{replay}} = \frac{1}{T} \sum_{t} |\tilde{x}_t - x_t|$.
- Episode Maximum Absolute Deviation: $\max_t |\tilde{x}_t - x_t|$.
- Proportion of near-identical intervals: fraction of intervals where $|\tilde{x}_t - x_t| < 0.01$ kWh.

*Analytical Role:* Replay tests the autoencoder's ability to detect temporal and seasonal contextual desynchronization rather than distributional shape malformation.

---

### 3.5 Primary Coordinated FDIA: Market Price Manipulation (Economic Collusion)
The primary specification designates **one primary coordinated FDIA** optimized for evaluating cyber-economic resilience in the Continuous Double Auction (CDA) market.

**Designation: Market Price Manipulation / Economic Collusion Attack**
- **Objective:** The coordinated attack creates an artificial community-wide supply surplus and suppresses reported demand, with the downstream objective of influencing CDA clearing prices and market welfare.
- **Cyber vs. Economic Layer Separation Principle:** The cyber layer (attack generator) strictly generates the coordinated false telemetry. It does not simulate market clearing or assert that clearing prices will necessarily decrease. The economic layer (Step 6 CDA simulation) will later consume the manipulated telemetry and empirically measure the actual effect on clearing prices, energy imbalance, social welfare, and economic loss.
- **Participant Coalition:** A colluding coalition $\mathcal{C}_{\text{coord}} \subset \mathcal{C}$ comprising the default penetration fraction (20% of cohort, $\approx 60$ prosumers) active during the attack window.
- **Coordinated Roles:**
  1. **Compromised Net Sellers (Generation Inflation):** Prosumers with active solar generation ($GG_t > 0$) simultaneously inflate reported Gross Generation:
     $$\tilde{GG}_{i,t} = \min\left(\text{Capacity}_i \times 0.5\text{ h}, \beta_{\text{up}, i} \cdot GG_{i,t}\right)$$
     where $\beta_{\text{up}, i} \sim \mathcal{U}(1.30, 1.80)$ provides heterogeneous, non-uniform scaling across prosumers to prevent trivial multi-meter identical-multiplier detection.
  2. **Compromised Net Buyers (Consumption Deflation):** Prosumers in net deficit simultaneously deflate reported General Consumption:
     $$\tilde{GC}_{i,t} = \max\left(0.0, \beta_{\text{down}, i} \cdot GC_{i,t}\right)$$
     where $\beta_{\text{down}, i} \sim \mathcal{U}(0.40, 0.70)$.
- **Synchronization:** Executed synchronously during peak daylight trading intervals (e.g., 10:00 to 14:00, intervals 20 to 28), generating peak market-facing distortion.
- **Physical Plausibility:** Clamped at PV inverter capacity for $GG$, non-negative for $GC$.
- **Secondary Coordinated Variants:** Uniform Multi-Meter Scaling and Net-Neutral Feeder Cancellation are designated as **secondary ablation extensions** for future sensitivity analyses, not active in the primary benchmark.

---

## 4. Chronological Attack Progression (Four-Phase Architecture)

To evaluate continual learning and adaptive detection across the frozen 3-year Ausgrid timeline (1,096 days, $T = 52,608$ intervals), the timeline is partitioned into four distinct chronological phases. Phase 4 is cleanly sub-divided internally to test sequential concept drift without an uncontrolled mixture.

```
Timeline: 1,096 Days (2010-07-01 to 2013-06-30 | 52,608 Half-Hour Time Points)
├───────────────────────────────────────────────────────────────────────────────────────────┤
│   Phase 1: Normal    │   Phase 2: Scaling   │  Phase 3: Ramp   │    Phase 4: Advanced     │
│                      │                      │                  │   4A: Replay │ 4B: Coord │
│   (Days 0 – 364)     │   (Days 365 – 600)   │ (Days 601 – 850) │ (Days 851–972) (973–1095)│
│   Year 1 (Clean)     │   Year 2 (Early)     │ Year 2-3 (Mid)   │       Year 3 (Late)      │
├───────────────────────────────────────────────────────────────────────────────────────────┤
```

| Phase | Days Range | Date Range | Duration | Dominant Attack Distribution | Adversarial Challenge & Concept Drift Character |
| :---: | :---: | :---: | :---: | :--- | :--- |
| **Phase 1: Normal** | 0 – 364 | 2010-07-01 to 2011-06-30 | 365 days (17,520 pts) | **Zero Attack ($a_t = 0$)** | Pristine baseline; seasonal and diurnal patterns. Used for initial autoencoder pre-training. |
| **Phase 2: Scaling** | 365 – 600 | 2011-07-01 to 2012-02-21 | 236 days (11,328 pts) | **Scaling FDIA** | Abrupt magnitude shift. Stationary gain distortion. Tests sudden variance/scale adaptation. |
| **Phase 3: Ramp** | 601 – 850 | 2012-02-22 to 2012-10-27 | 250 days (12,000 pts) | **Ramp FDIA** | Gradual temporal drift. Non-stationary progression. Tests tracking of incipient slow drift. |
| **Phase 4A: Replay** | 851 – 972 | 2012-10-28 to 2013-02-26 | 122 days (5,856 pts) | **Replay FDIA** | Historical playback ($k \in \{7, 14, 21\}$ days). Contextual desynchronization with authentic marginals. |
| **Phase 4B: Coordinated** | 973 – 1,095| 2013-02-27 to 2013-06-30 | 123 days (5,904 pts) | **Primary Coordinated FDIA** | Multi-agent economic collusion (Market Price Manipulation). Correlated multi-meter telemetry distortion. |

### 4.1 Progression of Adversarial Difficulty (Fairness Principle)
The progression reflects **increasing structural sophistication**, not brute-force magnitude escalation:
$$\text{Clean Baseline} \longrightarrow \text{Abrupt Scale} \longrightarrow \text{Gradual Drift} \longrightarrow \text{Contextual Replay} \longrightarrow \text{Multi-Agent Collusion}$$
- Attack magnitudes remain comparable and physically bounded across all phases.
- The model's challenge evolves from detecting simple out-of-scale values to detecting slow temporal divergence, historical desynchronization, and coordinated spatial collusion.

### 4.2 Deterministic Target Selection & Episode Non-Overlap Mechanism
- **Episode Penetration ($f_{\text{episode}}$):** In any active attack episode, the approved default penetration is **20% of the cohort** ($M = \lfloor 0.20 \times 299 \rfloor = 59$ prosumers).
- **Episodic Sub-Cohort Rotation:** Subsets $\mathcal{C}_{\text{att}}^{(e)}$ are selected deterministically per episode using an independent pseudo-random stream seeded by `SEED = 42`. Over the multi-year timeline, different customers experience attacks, exposing data-local detectors across diverse customer profiles.
- **Episode Non-Overlap Scheduling Rule:**
  - An attack episode is defined by customer set $\mathcal{C}_{\text{att}}^{(e)}$ and interval window $[t_{\text{start}}^{(e)}, t_{\text{end}}^{(e)}]$.
  - **Temporal Occupancy Check:** The episode scheduler maintains a binary customer-time occupancy bitmask $\mathbf{O} \in \{0, 1\}^{N \times T}$.
  - Before committing an episode, the scheduler verifies:
    $$\sum_{t=t_{\text{start}}^{(e)}}^{t_{\text{end}}^{(e)}} \mathbf{O}_{i, t} == 0, \quad \forall i \in \mathcal{C}_{\text{att}}^{(e)}$$
  - If a candidate customer $i$ is already engaged in an active attack episode during any overlapping interval, candidate $i$ is deterministically rejected and replaced with the next available candidate from the seeded permutation sequence.
  - **Result:** No customer ever experiences overlapping attack episodes. Observations receive at most one primary attack transformation. Different customers may be attacked simultaneously during the same time interval.
- **Attack Duty Cycle:** Within Phases 2, 3, 4A, and 4B, attacks occur in discrete burst episodes (typically lasting 8 to 48 intervals = 4 to 24 hours), accounting for an active attack duty cycle of **15% to 30%** of time intervals in attack phases.

---

## 5. Parameter Ranges & Grounding Classification

Every parameter is categorized strictly into:
- **Physically Motivated (P):** Derived directly from grid physics, sensor engineering, or device nameplate specifications.
- **Literature-Supported Principles (L):** Conceptually motivated by established academic literature (citations provided for principles, not fabricated exact numbers).
- **Experimental Assumptions (A):** Explicit engineering decisions formulated for this experimental setup.

| Parameter | Symbol | Range / Value | Category | Grounding Justification |
| :--- | :---: | :---: | :---: | :--- |
| **PV Inverter Capacity Clamp** | $GG_{\max, i}$ | $\text{Capacity}_i \times 0.5\text{ h}$ (kWh) | **P** | Physical nameplate limit from Ausgrid connection metadata. An inverter cannot physically inject power above its rated peak capacity. |
| **Non-Negativity Constraint** | $\tilde{x}_{\min}$ | $\ge 0.0$ kWh | **P** | Energy meters measure real non-negative energy volumes. |
| **Preservation of Nocturnal GG** | $\text{GG}_{\text{nocturnal}}$ | Preserve raw sensor baseline | **P** | Ausgrid dataset contains small legitimate sensor/standby offsets ($\le 0.013$ kWh). Artificially zeroing them destroys ground-truth measurement realism. |
| **Scaling Down Range (Theft)** | $\beta_{\text{down}}$ | $[0.30, 0.80]$ | **L / A** | **Principle (L):** Jokar et al. (2016), Liang et al. (2017) establish multiplicative deflation for energy theft. **Assumption (A):** Exact range $[0.30, 0.80]$ is an experimental assumption to balance economic incentive with anomaly evasion. |
| **Scaling Up Range (Fraud)** | $\beta_{\text{up}}$ | $[1.25, 2.00]$ | **L / A** | **Principle (L):** Habibi et al. (2020) model solar generation fraud in P2P markets. **Assumption (A):** Exact range $[1.25, 2.00]$ is an experimental assumption bounded by physical solar variability. |
| **Ramp Duration** | $T_{\text{ramp}}$ | $12 \text{ to } 96$ intervals (6h to 48h) | **L / A** | **Principle (L):** Kurt et al. (2018) formalize linear ramp attacks against change-point detectors. **Assumption (A):** Exact range $[12, 96]$ intervals chosen to test multi-hour diurnal transitions. |
| **Ramp Target Strength** | $\beta_{\text{target}}$ | $0.4 \text{ to } 0.6$ (down) / $1.4 \text{ to } 1.8$ (up) | **A** | Matches terminal scaling strength while evolving continuously. |
| **Replay Lag Offsets** | $\Delta$ | $k \times 48, \quad k \in \{7, 14, 21\}$ days | **P / A** | **Physical Motivation (P):** Preserves 7-day human behavioral/occupancy cycles and seasonal solar envelopes. **Assumption (A):** Specific candidate offsets $\{7, 14, 21\}$ days. |
| **Default Episode Penetration** | $f_{\text{episode}}$ | $20\%$ of cohort ($59$ prosumers) | **L / A** | **Principle (L):** Almasabi et al. (2022) analyze multi-prosumer compromise thresholds ($10\% - 25\%$). **Assumption (A):** 20% selected as approved primary benchmark default. |
| **Coordinated Scaling Heterogeneity** | $\beta_i$ | $\mathcal{U}(1.30, 1.80)$ (sellers), $\mathcal{U}(0.40, 0.70)$ (buyers) | **A** | Prevents identical multi-meter multiplier artifacts. |

---

## 6. Experimental Fairness Across Experiments A–D

To ensure the research questions remain methodologically unassailable, **attack generation occurs strictly ONCE**:

$$\mathcal{D}_{\text{attacked}} = \text{DeterministicAttackGenerator}(\mathcal{D}_{\text{processed}}, \text{Config}_{\text{attack}}, \text{Seed})$$

- The generated attacked dataset is persisted as an immutable benchmark dataset.
- **Experiment A (Federated vs. Local vs. Centralized):** Evaluates detection performance across architectures on the identical attack stream.
- **Experiment B (Continual Learning vs. Static FedAvg):** Evaluates memory retention and adaptation against the identical sequence of evolving concept drift.
- **Experiment C (Economic Decision vs. Fixed Threshold):** Compares downstream market welfare under identical detector uncertainty and identical attack realities.
- **Experiment D (Economic Sensitivity Analysis):** Evaluates cost-ratio sensitivity ($C_{\text{FN}} / C_{\text{FP}} = 1\times, 5\times, 10\times, 20\times$) against the identical ground truth.
- **Zero Experiment-Specific Randomness:** Downstream experimental scripts consume the benchmark in read-only mode.

---

## 7. Deterministic Reproducibility Strategy

1. **Master PRNG Architecture:**
   - Seed: Fixed master seed (`SEED = 42` by default).
   - Independent Sub-Streams: A dedicated `numpy.random.Generator` initialized via `np.random.SeedSequence(SEED)` to prevent cross-phase RNG coupling.
2. **Configuration Architecture (`configs/attack_config.yaml`):**
   - All phase boundaries, rotation schedules, scaling parameters, ramp slopes, and replay lags are fully externalized in a version-controlled YAML configuration file.
3. **Data Immutability & Traceability:**
   - Input Parquet (`data/processed/ausgrid_solar_processed.parquet`) is strictly read-only.
   - Attack generation creates `data/processed/ausgrid_solar_attacked.parquet`.
   - A cryptographic SHA-256 hash of the generated attack dataset is logged in the run report.

---

## 8. Ground-Truth Metadata Specification

Every observation in the output dataset contains comprehensive ground-truth tracking metadata to permit granular ablation and evaluation across attack classes:

| Field Name | Type | Description |
| :--- | :---: | :--- |
| `customer_id` | `int32` | Retained customer ID ($1..300$, excluding 2). |
| `time_index` | `int32` | Sequential chronological index ($0..52607$). |
| `date` | `string` | Calendar date (`YYYY-MM-DD`). |
| `interval_index`| `int8` | Half-hour interval ($0..47$). |
| `interval_label`| `string` | Original column label (`0:30`..`0:00`). |
| `GC_clean` | `float64` | Pristine, unmanipulated General Consumption (kWh). |
| `GG_clean` | `float64` | Pristine, unmanipulated Gross Generation (kWh). |
| `GC_attacked` | `float64` | Injected / observed General Consumption (kWh). |
| `GG_attacked` | `float64` | Injected / observed Gross Generation (kWh). |
| `P_net_clean` | `float64` | Clean net demand: $GC_{\text{clean}} - GG_{\text{clean}}$. |
| `P_net_attacked`| `float64` | Attacked net demand: $GC_{\text{attacked}} - GG_{\text{attacked}}$. |
| `is_attacked` | `bool` | Binary ground-truth label (`True` if $GC$ or $GG$ was manipulated). |
| `attack_type` | `category`| Single primary attack applied: `{'NONE', 'SCALING', 'RAMP', 'REPLAY', 'COORDINATED'}`. |
| `attack_phase` | `string` | Active chronological phase: `{'1_NORMAL', '2_SCALING', '3_RAMP', '4A_REPLAY', '4B_COORDINATED'}`. |
| `attack_target`| `category`| Target channel: `{'NONE', 'GC', 'GG', 'BOTH'}`. |
| `attack_param` | `float32` | Injected parameter value (e.g., scaling $\beta$, ramp $\beta(t)$, replay lag $\Delta$ in days, or coordinated multiplier $\beta_i$). |
| `is_actual` | `bool` | Preserved Ausgrid meter quality flag. |

**Label Disambiguation Guarantees:**
- When `is_attacked == False`: $GC_{\text{attacked}} \equiv GC_{\text{clean}}$, $GG_{\text{attacked}} \equiv GG_{\text{clean}}$, `attack_type == 'NONE'`, `attack_target == 'NONE'`, and `attack_param == 0.0`.
- When `is_attacked == True`: Exactly one primary attack type is assigned (`attack_type \ne 'NONE'`). Ambiguous, overlapping, or compound multi-type assignments are strictly prohibited.

---

## 9. Attack Generator Validation Suite (Plan for `attack_generator.py`)

Prior to releasing the attacked dataset for model training, a dedicated validation suite will programmatically enforce:

1. **Dimensionality Invariance:** Output row count strictly equals $15,729,792$ ($299 \text{ customers} \times 52,608 \text{ time points}$).
2. **Phase 1 Purity:** Exactly 0 attacks (`is_attacked == False`) across all 299 customers during Days 0–364.
3. **Clean Data Fidelity:** For all unattacked rows (`is_attacked == False`), $GC_{\text{attacked}} \equiv GC_{\text{clean}}$ and $GG_{\text{attacked}} \equiv GG_{\text{clean}}$ bit-for-bit (0.000 absolute tolerance).
4. **No Overlapping Primary Attacks (Single-Transformation Invariance):**
   - For every customer-interval observation, at most one primary attack transformation is applied.
   - Verify that no observation has conflicting or sequential attack labels.
   - Verify that all attack transformations originate strictly from the clean baseline value ($x_{\text{clean}}$).
5. **Customer Episode Non-Overlap:**
   - Verify that attack episodes assigned to the same customer never overlap temporally.
   - Verify that simultaneous attacks in the same time interval occur exclusively across disjoint customer subsets.
6. **Strict Temporal Ordering & Phase Segregation:**
   - Scaling attacks occur exclusively in Phase 2 (Days 365–600).
   - Ramp attacks occur exclusively in Phase 3 (Days 601–850).
   - Replay attacks occur exclusively in Phase 4A (Days 851–972).
   - Coordinated attacks occur exclusively in Phase 4B (Days 973–1,095).
7. **Physical Range & Sensor Compliance:**
   - $GC_{\text{attacked}} \ge 0.0$ and $GG_{\text{attacked}} \ge 0.0$ globally.
   - For all prosumers, $GG_{\text{attacked}} \le \text{Capacity}_i \times 0.5\text{ h}$.
   - **No artificial GC clamp:** Verification ensures $GC$ was not artificially truncated by an arbitrary statistical ceiling.
   - **Nighttime Sensor Integrity:** Verification ensures authentic nighttime sensor readings were not artificially zeroed outside of explicit attack transformations.
8. **Ramp Continuity Verification:** Verify that ramp attacks initialize smoothly ($\beta(t_{\text{start}}) \approx 1.0$) and transition continuously without jump discontinuities.
9. **Replay Integrity & Metric Audit:**
   - Verify that replayed values correspond strictly to authentic past values of the same customer ($x_{t - \Delta}$) with $\Delta \pmod{48 \times 7} = 0$.
   - Verify that no synthetic noise was added to replayed values.
   - Audit and report replay deviation distributions (MAE, maximum deviation, and fraction of near-identical intervals).
10. **Coordinated Collusion Verification:** Verify that prosumers targeted during Phase 4B belong to the designated coordinated coalition $\mathcal{C}_{\text{coord}}$ and execute synchronized injections during peak trading intervals.
11. **Cyber/Economic Layer Separation:** Verify that the attack generator validates only telemetry attributes; economic impact on clearing prices and welfare is strictly deferred to the downstream CDA market simulator.
12. **Deterministic Hash Traceability:** Verify that the SHA-256 hash of the generated dataset matches the configuration execution log.

---

## 10. Literature References & Academic Grounding

1. **Liu, Y., Ning, P., & Reiter, M. K. (2011).** *False data injection attacks against state estimation in electric power grids.* ACM Transactions on Information and System Security (TISSEC), 14(1), 1–33.
   - *Supported Principle:* Foundational mathematical formulation of stealthy FDIAs that exploit measurement residuals to bypass detection.
2. **Liang, G., Zhao, J., Luo, F., Thakur, S. R., & Liu, Y. (2017).** *A review of false data injection attacks against modern power systems.* IEEE Transactions on Smart Grid, 8(4), 1630–1638.
   - *Supported Principle:* Conceptual taxonomy of cyber-attack waveforms against energy telemetry, including scaling, ramp, additive, and coordinated classes.
3. **Kurt, M. N., Ogundipe, O., Yilmaz, Y., & Wang, X. (2018).** *Online cyber-attack detection in smart grid: A reinforcement learning approach.* IEEE Transactions on Smart Grid, 10(5), 5174–5185.
   - *Supported Principle:* Mathematical modeling of gradual ramp/drift attacks designed to evade change-point algorithms.
4. **Jokar, P., Leung, N., & Eyisi, P. (2016).** *Electricity theft detection in AMI using high-order statistics and pattern recognition.* IEEE Transactions on Smart Grid, 7(2), 932–945.
   - *Supported Principle:* Multiplicative consumption reduction models for smart meter energy theft.
5. **Mo, Y., & Sinopoli, B. (2012).** *Secure state estimation in the presence of replay attacks.* IEEE Transactions on Automatic Control, 57(1), 161–172.
   - *Supported Principle:* Control-theoretic formulation of replay attacks and proof of stealthiness against linear estimators when replaying authentic historical sequences.
6. **Habibi, D., Sajjadi, M., & Modarres, M. (2020).** *Cybersecurity in transactive energy systems and peer-to-peer markets.* IEEE Access, 8, 124312–124328.
   - *Supported Principle:* Prosumer telemetry vulnerabilities in P2P transactive energy markets, demonstrating economic consequences of false solar generation claims.
7. **Almasabi, S., Al-Sumaiti, A., & Guerrero, J. M. (2022).** *Data-driven cyber-attack detection in peer-to-peer energy trading.* IEEE Transactions on Industrial Informatics, 18(9), 6120–6131.
   - *Supported Principle:* Analysis of multi-prosumer coordinated attack feasibility and penetration bounds in local energy trading networks.

---

## 11. Explicit Experimental Assumptions

1. **Compromise Boundary:** The adversary compromises meter telemetry at the local smart meter / gateway firmware level, but cannot alter regional solar irradiance or external grid utility substations.
2. **Penetration Level Selection:** The default episode penetration rate of 20% ($\approx 60$ prosumers per episode) is an approved experimental design choice balancing statistical detection power with plausible attack surface.
3. **Episodic Sub-Cohort Rotation:** Rotating customer subsets between episodes is an approved experimental assumption designed to expose data-local models across diverse customer load distributions.
4. **Discrete Half-Hourly Intervals:** Attacks are injected at the native half-hour meter interval resolution matching the Ausgrid source recording rate.
5. **No Synthetic Noise in Replay:** Replay fidelity is maintained without artificial additive noise, ensuring that replay detection evaluates purely temporal/contextual desynchronization.

---

## 12. Approved Baseline Architecture & Implementation Finalization

### 12.1 Approved Architectural Foundations (Frozen Decisions)
The following architectural choices have been reviewed and approved:
1. **Dataset Storage Format:** Single combined Parquet file (`data/processed/ausgrid_solar_attacked.parquet`, ~160 MB) containing pristine clean columns alongside attacked columns for zero-lookup training.
2. **Target Customer Rotation:** Deterministic episodic rotation sampling 20% of prosumers ($M=59$) per burst episode via seeded PRNG, with temporal non-overlap enforcement per customer.
3. **Channel Allocation:** Default split of 40% Gross Generation ($GG$), 40% General Consumption ($GC$), and 20% Joint ($GC$ and $GG$) during active scaling and ramp episodes.
4. **Primary Coordinated Attack:** Market Price Manipulation / Economic Collusion (coordinated seller generation inflation and buyer consumption deflation during peak daylight CDA trading windows).
5. **Phase Chronological Boundaries:**
   - Phase 1 (Normal): Days 0–364 (2010-07-01 to 2011-06-30, 365 days)
   - Phase 2 (Scaling): Days 365–600 (2011-07-01 to 2012-02-21, 236 days)
   - Phase 3 (Ramp): Days 601–850 (2012-02-22 to 2012-10-27, 250 days)
   - Phase 4A (Replay): Days 851–972 (2012-10-28 to 2013-02-26, 122 days)
   - Phase 4B (Coordinated): Days 973–1,095 (2013-02-27 to 2013-06-30, 123 days)
6. **Non-Overlapping Primary Attack Invariance:** Each customer-interval observation receives at most one primary attack transformation, computed strictly from the clean baseline value.

### 12.2 Implementation Details to Be Finalized in `src/attack_generator.py`
The following operational details will be codified directly in the configuration and implementation scripts:
- Configuration file location: `configs/attack_config.yaml`.
- Default master PRNG seed: `SEED = 42`.
- Exact numerical logging schema for replay episode audit metrics (MAE, max deviation, negligible fraction).
- SHA-256 integrity hash generation and logging upon script completion.
