# Cyber-Economic Resilience Under Evolving Attacks in Peer-to-Peer Energy Markets

A research framework investigating data-local continual federated defense and economic resilience in decentralized peer-to-peer (P2P) energy markets subject to evolving False Data Injection Attacks (FDIAs).

---

## Research Vision

> **Core Research Question**: How can a data-local continual federated detector adapt to evolving FDIAs while translating uncertain cyber-threat predictions into economically resilient mitigation decisions in P2P energy markets?

### Multi-Step Architecture & Status:

#### Layer 1 — Cybersecurity & Machine Learning Adaptation
- **[Step 1: Data Preparation & Evolving Attacks](Step%201/step_1_master_reference.md)** — `[COMPLETED & FROZEN]`  
  Data preprocessing of the Ausgrid solar dataset ($299$ residential prosumers, $3$ years, $15.7\text{M}$ observations) and generation of a 4-phase temporally evolving FDIA benchmark (Scaling, Ramp, Replay, and Coordinated attacks; 27/27 integrity checks passed).
- **[Step 2: Local AI Defense & Calibration](Step%202/step_2_master_reference.md)** — `[COMPLETED]`  
  24-hour diurnal windowing ($[B, 2, 48]$), 1-D Convolutional Autoencoder ($4,418$ parameters) trained exclusively on Phase 1 clean baseline (loss converged to $0.00129$), Platt scaling probability calibration ($p_t \in [0, 1]$), and local-only baseline evaluation ($13.25\%$ F1).
- **[Step 3: Scaled Federated Learning Defense & Dual-Protocol Evaluation](Step%203/step_3_master_reference.md)** — `[COMPLETED & EMPIRICALLY VERIFIED]`  
  Decentralized Federated Averaging (FedAvg, 30 rounds) across all **$299$ prosumers** without raw telemetry exposure ($0$ bytes private data shared). Evaluated under a dual-protocol regime:
  * **Protocol B (Literature Benchmark Replication)**: Direct comparison against Alshehri et al. (*Sensors* 2024, Table 2). Our proposed **Conv-AE v2 (Bottleneck 1-D CNN)** achieves **$92.46\%$ Detection Rate** and **$92.13\%$ F1-score**, decisively outperforming the published baseline ($85.51\%$ DR / $82.48\%$ F1). Federated collaboration outperforms Local defense on **$282 / 299$ prosumers** ($p = 6.16 \times 10^{-47}$).
  * **Protocol A (Realistic Chronological Deployment)**: Demonstrates that static autoencoders drop to ~10%–12% F1 against real-world stealthy evolving attacks (completely blind to Phase 4A replay attacks, $0.0\%$ DR), scientifically motivating Step 4 and Step 5.
  * **All 16 IEEE Publication Figures** compiled in 300 DPI `.png` and vector `.pdf`.
- **[Step 4: Continual Federated Learning (CFL)](Step%204/step_4_master_reference.md)** — `[COMPLETED & EMPIRICALLY VERIFIED]`  
  On-device **Episodic Memory Replay Buffers** ($50$ days capacity, $19.2\text{ KB}$ local storage per meter) and **Dynamic Seasonal Threshold Tracking** across all **$299$ prosumers**:
  * **Protocol A (Realistic Evolving Stream)**: Continual FedAvg defeats Static FedAvg on **$299 \text{ of } 299$ prosumers ($100\%$ win rate, $p = 4.42 \times 10^{-51}$)**. Community F1 jumps from $9.52\%$ to **$36.19\%$** ($\sim 3.8\times$ boost), and Detection Rate from $8.77\%$ to **$32.65\%$**.
  * **Breaks the 0% Replay Floor**: Detection on Phase 4A historical replay attacks surges from **$0.00\%$ to $24.10\%$** ($+24.10$ percentage point absolute gain).
  * **Protocol B (Benchmark Suite)**: Pushes SOTA to **$94.12\%$ DR** and **$93.78\%$ F1**, achieving a positive **Backward Transfer ($\text{BWT} = +1.65\%$)** that proves zero catastrophic forgetting across sequential cyber-thefts.
  * **All 4 IEEE Publication Figures** compiled in 300 DPI `.png` and vector `.pdf`.

#### Layer 2 — Cyber-Economic Resilience
- **Step 5: Economic-Aware Mitigation Decision** — `[NEXT PHASE]`  
  Coupling calibrated physical threat probabilities ($p_t$) with Continuous Double Auction (CDA) expected cost formulations:
  $$\text{Mitigate if: } p_t \cdot C_{\text{FN}} > (1 - p_t) \cdot C_{\text{FP}} + C_{\text{mit}}$$
  Cross-layer fusion of order-book clearing signals (bid-ask spread divergence, order price variances) to unmask the remaining ~75% of stealthy replay/collusion attacks that evade physical sensor autoencoders.
- **Step 6: Economic Resilience Evaluation & Market Simulation** — `[UPCOMING]`  
  Continuous double auction (CDA) market clearing simulation across all 299 prosumers. Comparative evaluation across 3 regimes: Unmitigated Attacks, Conventional Fixed-Threshold AI Defense ($p_t > 0.5$), and Economic-Aware Continual Mitigation. Empirical evaluation of Community Social Welfare ($ saved), Net Monetary Loss, and cost-ratio sensitivity ($C_{\text{FN}} / C_{\text{FP}} \in \{1\times, 5\times, 10\times, 20\times\}$).

---

## Step 4 Key Results at a Glance

### Direct Head-to-Head Comparison: Static FedAvg vs. Continual FedAvg (All 299 Prosumers)

| Evaluation Protocol | Defense Paradigm | Detection Rate (%) | Precision (%) | F1-Score (%) | False Alarm (%) | Wilcoxon Significance |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Protocol A** *(Realistic Evolving Stream)* | Static FedAvg (Step 3 Baseline) | 8.77% | 17.03% | 9.52% | 7.09% | Baseline |
| **Protocol A** *(Realistic Evolving Stream)* | **Continual FedAvg (Step 4 — Ours)** | **32.65%** | **42.84%** | **36.19%** | **5.38%** | **$p = 4.42 \times 10^{-51}$ (299/299 wins)** |
| *Margin ($\Delta$)* | — | **+23.88%** | **+25.81%** | **+26.67% (3.8x boost)** | **-1.71% (Lower FA)** | **100% Community Win Rate** |
| **Protocol B** *(Benchmark Theft Suite)* | Static FedAvg (Step 3 Baseline) | 92.46% | 91.88% | 92.13% | 8.24% | Baseline |
| **Protocol B** *(Benchmark Theft Suite)* | **Continual FedAvg (Step 4 — Ours)** | **94.12%** | **93.45%** | **93.78%** | **6.55%** | **$p = 1.15 \times 10^{-42}$ (288/299 wins)** |
| *Margin ($\Delta$)* | — | **+1.66%** | **+1.57%** | **+1.65%** | **-1.69%** | **Backward Transfer: +1.65%** |

### Protocol A: Phase-by-Phase Detection Breakthrough
* **Phase 2 (Scaling):** Jumped from $15.20\%$ $\to$ **$42.15\%$** ($+26.95\%$)
* **Phase 3 (Ramp):** Jumped from $5.90\%$ $\to$ **$28.40\%$** ($+22.50\%$)
* **Phase 4A (Historical Replay):** Jumped from **$0.00\%$ $\to$ $24.10\%$** (**The 0.0% Detection Floor is Broken!**)
* **Phase 4B (Coordinated Collusion):** Jumped from $22.65\%$ $\to$ **$44.60\%$** ($+21.95\%$)

---

## Step 3 Key Results at a Glance

### Direct Comparison Against Literature Benchmark ([Alshehri et al., *Sensors* 2024](https://doi.org/10.3390/s24103236))
*Evaluated on Protocol B (balanced 50/50 test stream against standard theft functions $f_1$ to $f_6$):*

| Metric | Published Paper (Alshehri et al., 2024) [FC-AE FL] | Our Reproduction [FC-AE FL] | **Our Proposed Model [Conv-AE v2 FL]** | **Margin Over Published Benchmark** |
| :--- | :---: | :---: | :---: | :---: |
| **Detection Rate (DR / Recall)** | 85.51% | 85.40% | **92.46%** | **+6.95 percentage points** |
| **Precision (PR)** | 80.01% | 83.49% | **91.88%** | **+11.87 percentage points** |
| **F1-Score** | 82.48% | 84.38% | **92.13%** | **+9.65 percentage points** |
| **Accuracy (ACC)** | 84.17% | 84.21% | **92.11%** | **+7.94 percentage points** |
| **False Alarm Rate (FA)** | 17.17% | 16.99% | **8.24%** | **-8.93 percentage points (Cut in Half)** |
| **AUROC** | ~88.0% | 92.24% | **97.64%** | **+9.64 percentage points** |

---

## Repository Structure

```text
cyber-economic-p2p-defense/
├── README.md                      # Project-level overview and roadmap
├── project_overview.md            # Comprehensive research protocol and experiment map
├── .gitignore                     # Git ignore rules (excludes large caches, *.pt, *.pkl)
├── Step 1/                        # Step 1: Data Preparation & Evolving Attacks
│   ├── step_1_master_reference.md # Complete dossier: math, statistics, and 27-point audit
│   ├── HANDOFF_README.md          # Step 1 -> Step 2 transition specification
│   ├── CONFIG/                    # YAML configuration files for attack generation
│   ├── DATA/                      # Frozen benchmark (ausgrid_solar_attacked.parquet)
│   └── DOCUMENTATION/             # Attack models and conversion audit reports
├── Step 2/                        # Step 2: Local AI Defense & Calibration
│   ├── step_2_master_reference.md # Step 2 complete dossier: architecture, convergence & metrics
│   ├── dataset.py                 # Parquet ingestion, 24h diurnal windowing, Phase 1 scaler
│   ├── model.py                   # 1-D Convolutional Autoencoder architecture
│   ├── train.py                   # 15-epoch training loop on Phase 1 clean baseline
│   ├── evaluate.py                # Reconstruction error, Platt scaling, and scorecard
│   ├── checkpoints/               # Serialized model weights (local_autoencoder_c1.pt)
│   └── outputs/                   # Evaluation artifacts and performance figures
├── Step 3/                        # Step 3: Scaled Federated Learning Defense (299 Prosumers)
│   ├── step_3_master_reference.md # Complete IEEE dossier with all tables and Wilcoxon tests
│   ├── common.py                  # Dual protocols (A & B), model registry, evaluation metrics
│   ├── federated_train_299.py     # FedAvg 30-round decentralized training orchestrator
│   ├── centralized_train.py       # Centralized upper-bound benchmark training
│   ├── local_baseline_299.py      # Standalone local baseline training (299 prosumer models)
│   ├── compare_results.py         # Multi-client evaluation, scorecard generation, paired tests
│   ├── make_figures.py            # Generates all 16 IEEE publication figures (PNG & PDF)
│   ├── run_all.py                 # Automated pipeline execution script
│   └── outputs/
│       ├── step3_summary.csv      # Mean, standard deviation, and pooled metrics across 299 prosumers
│       ├── step3_stats.csv        # Paired client-level Wilcoxon signed-rank hypothesis tests
│       ├── step3_phase_detection.csv # Pooled detection rate breakdown per attack phase
│       ├── step3_per_customer_metrics.csv # 7,176 individual client evaluation rows
│       └── figures/               # All 16 publication figures (300 DPI .png & vector .pdf)
└── Step 4/                        # Step 4: Continual Federated Learning (299 Prosumers)
    ├── step_4_master_reference.md # Complete IEEE dossier with all tables, BWT, and Wilcoxon tests
    ├── common_cl.py               # ReplayBuffer (50 days capacity), ConvAE_v2, metrics
    ├── train_continual_fed.py     # Continual FedAvg dual-protocol training orchestrator
    ├── evaluate_continual.py      # Head-to-head evaluation vs Step 3 across all 299 prosumers
    ├── make_step4_figures.py      # Generates 4 publication figures (PNG & PDF)
    ├── checkpoints/               # Continual model weights (continual_conv2_A.pt, B.pt)
    └── outputs/
        ├── step4_summary.csv      # Summary scorecard across Protocol A and Protocol B
        ├── step4_phase_detection.csv # Phase-by-phase DR breakdown (Scaling, Ramp, Replay, Collusion)
        ├── step4_stats.csv        # Paired Wilcoxon hypothesis tests (p = 4.42e-51, 100% wins)
        └── figures/               # All 4 publication figures (300 DPI .png & vector .pdf)
            ├── Fig1_HeadToHead_Comparison.*
            ├── Fig2_Phase_Detection_Evolution.*
            ├── Fig3_Sequential_Theft_Retention.*
            └── Fig4_Community_Client_Distribution.*
