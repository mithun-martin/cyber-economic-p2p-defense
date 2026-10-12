# Cyber-Economic Resilience Under Evolving Attacks in Peer-to-Peer Energy Markets

A research framework investigating data-local continual federated defense and economic resilience in decentralized peer-to-peer (P2P) energy markets subject to evolving False Data Injection Attacks (FDIAs).

---

## Research Vision

> **Core Research Question**: How can a data-local continual federated detector adapt to evolving FDIAs while translating uncertain cyber-threat predictions into economically resilient mitigation decisions in P2P energy markets?

### Multi-Step Architecture & Status:

#### Layer 1 — Cybersecurity & Machine Learning
- **[Step 1: Data Preparation & Evolving Attacks](Step%201/step_1_master_reference.md)** — `[COMPLETED & FROZEN]`  
  Data preprocessing of the Ausgrid solar dataset ($299$ residential prosumers, $3$ years, $15.7\text{M}$ observations) and generation of a 4-phase temporally evolving FDIA benchmark (Scaling, Ramp, Replay, and Coordinated attacks; 27/27 integrity checks passed).
- **[Step 2: Local AI Defense & Calibration](Step%202/step_2_master_reference.md)** — `[COMPLETED]`  
  24-hour diurnal windowing ($[B, 2, 48]$), 1-D Convolutional Autoencoder ($4,418$ parameters) trained exclusively on Phase 1 clean baseline (loss converged to $0.00129$), Platt scaling probability calibration ($p_t \in [0, 1]$), and local-only baseline evaluation ($13.25\%$ F1).
- **[Step 3: Scaled Federated Learning Defense & Dual-Protocol Evaluation](Step%203/step_3_master_reference.md)** — `[COMPLETED & VERIFIED]`  
  Decentralized Federated Averaging (FedAvg, 30 rounds) across all **$299$ prosumers** without raw telemetry exposure ($0$ bytes private data shared). Evaluated under a dual-protocol regime:
  * **Protocol B (Literature Benchmark Replication)**: Direct comparison against Alshehri et al. (*Sensors* 2024, Table 2). Our proposed **Conv-AE v2 (Bottleneck 1-D CNN)** achieves **$92.46\%$ Detection Rate** and **$92.13\%$ F1-score**, decisively outperforming the published baseline ($85.51\%$ DR / $82.48\%$ F1). Federated collaboration outperforms Local defense on **$282 / 299$ prosumers** ($p = 6.16 \times 10^{-47}$).
  * **Protocol A (Realistic Chronological Deployment)**: Demonstrates that static autoencoders drop to ~10%–12% F1 against real-world stealthy evolving attacks (completely blind to Phase 4A replay attacks, $0.0\%$ DR), scientifically motivating Step 4 and Step 5.
  * **All 16 IEEE Publication Figures** compiled in 300 DPI `.png` and vector `.pdf`.
- **Step 4: Continual Federated Learning** — `[NEXT PHASE]`  
  Memory-aware continual model adaptation (Experience Replay Buffers via Reservoir Sampling & Elastic Weight Consolidation) to counteract catastrophic forgetting under non-stationary attack distributions.

#### Layer 2 — Economic Resilience
- **Step 5: Economic-Aware Mitigation Decision**  
  Coupling calibrated threat probabilities ($p_t$) with downstream Continuous Double Auction (CDA) expected cost formulations:
  $$\text{Mitigate if: } p_t \cdot C_{\text{FN}} > (1 - p_t) \cdot C_{\text{FP}} + C_{\text{mit}}$$
- **Step 6: Economic Resilience Evaluation**  
  Continuous double auction (CDA) market clearing simulation, social welfare analysis, and cost-ratio sensitivity evaluations ($C_{\text{FN}} / C_{\text{FP}} \in \{1\times, 5\times, 10\times, 20\times\}$).

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
└── Step 3/                        # Step 3: Scaled Federated Learning Defense (299 Prosumers)
    ├── step_3_master_reference.md # Complete IEEE dossier with all tables and Wilcoxon tests
    ├── common.py                  # Dual protocols (A & B), model registry, evaluation metrics
    ├── federated_train_299.py     # FedAvg 30-round decentralized training orchestrator
    ├── centralized_train.py       # Centralized upper-bound benchmark training
    ├── local_baseline_299.py      # Standalone local baseline training (299 prosumer models)
    ├── compare_results.py         # Multi-client evaluation, scorecard generation, paired tests
    ├── make_figures.py            # Generates all 16 IEEE publication figures (PNG & PDF)
    ├── run_all.py                 # Automated pipeline execution script
    └── outputs/
        ├── step3_summary.csv      # Mean, standard deviation, and pooled metrics across 299 prosumers
        ├── step3_stats.csv        # Paired client-level Wilcoxon signed-rank hypothesis tests
        ├── step3_phase_detection.csv # Pooled detection rate breakdown per attack phase
        ├── step3_per_customer_metrics.csv # 7,176 individual client evaluation rows
        └── figures/               # All 16 publication figures (300 DPI .png & vector .pdf)
            ├── F01_system_architecture.*
            ├── F02_evaluation_protocols.*
            ├── F03_conv_ae_v2_architecture.*
            ├── F04_fedavg_workflow.*
            ├── F05_fl_convergence.*
            ├── F06_roc_curves.*
            ├── F07_pr_curves.*
            ├── F08_metric_bars.*
            ├── F09_f1_violins.*
            ├── F10_local_vs_federated_scatter.*
            ├── F11_phase_detection_heatmap.*
            ├── F12_score_distributions.*
            ├── F13_example_reconstruction.*
            ├── F14_protocol_A_vs_B.*
            ├── F15_confusion_matrices.*
            └── F16_model_ablation.*
```

---

## Quickstart

### Environment Setup
```bash
# 1. Clone repository
git clone https://github.com/mithun-martin/cyber-economic-p2p-defense.git
cd cyber-economic-p2p-defense

# 2. Activate Python virtual environment
.\.venv\Scripts\Activate.ps1
```

### Reproduce Step 3 Experiments
```bash
# Evaluate all trained models and generate CSV scorecards across 299 prosumers:
python "Step 3\compare_results.py"

# Generate all 16 IEEE publication figures (PNG 300 DPI + vector PDF):
python "Step 3\make_figures.py"
```

For full details on dataset specifications and empirical validation, consult:
- [`Step 1 Reference Dossier`](Step%201/step_1_master_reference.md)
- [`Step 2 Reference Dossier`](Step%202/step_2_master_reference.md)
- [`Step 3 Reference Dossier`](Step%203/step_3_master_reference.md)
