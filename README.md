# Cyber-Economic Resilience Under Evolving Attacks

A research framework investigating data-local continual federated defense and economic resilience in decentralized peer-to-peer (P2P) energy markets subject to evolving False Data Injection Attacks (FDIAs).

---

## Research Vision

> **Core Research Question**: How can a data-local continual federated detector adapt to evolving FDIAs while translating uncertain cyber-threat predictions into economically resilient mitigation decisions in P2P energy markets?

### Multi-Step Architecture & Status:

#### Layer 1 — Cybersecurity & Machine Learning
- **[Step 1: Data Preparation & Evolving Attacks](Step%201/step_1_master_reference.md)** — `[COMPLETED & FROZEN]`  
  Data preprocessing of the Ausgrid solar dataset (299 prosumers, 3 years, 15.7M observations) and generation of a 4-phase temporally evolving FDIA benchmark (Scaling, Ramp, Replay, and Coordinated attacks; 27/27 integrity checks passed).
- **[Step 2: Local AI Defense & Calibration](Step%202/step_2_master_reference.md)** — `[COMPLETED]`  
  24-hour diurnal windowing ($[B, 2, 48]$), 1-D Convolutional Autoencoder ($4,418$ parameters) trained exclusively on Phase 1 clean baseline (loss converged to $0.00129$), Platt scaling probability calibration ($p_t \in [0, 1]$), and local-only baseline evaluation ($13.25\%$ F1).
- **Step 3: Privacy-Aware Collaboration** — `[NEXT PHASE]`  
  Federated learning via the Flower framework (`flwr` / `FedAvg`) enabling cross-prosumer collaborative defense without raw telemetry exposure.
- **Step 4: Continual Learning**  
  Memory-aware continual model adaptation (Episodic Experience Replay) to counteract catastrophic forgetting under non-stationary attack distributions.

#### Layer 2 — Economic Resilience
- **Step 5: Economic-Aware Mitigation Decision**  
  Coupling calibrated threat probabilities ($p_t$) with downstream Continuous Double Auction (CDA) expected cost formulations:
  $$\text{Mitigate if: } p_t \cdot C_{\text{FN}} > (1 - p_t) \cdot C_{\text{FP}} + C_{\text{mit}}$$
- **Step 6: Economic Resilience Evaluation**  
  Continuous double auction (CDA) market clearing simulation, social welfare analysis, and cost-ratio sensitivity evaluations ($C_{\text{FN}} / C_{\text{FP}} \in \{1\times, 5\times, 10\times, 20\times\}$).

---

## Repository Structure

```text
cyber-economic-p2p-defense/
├── README.md                      # Project-level overview and roadmap
├── project_overview.md            # Comprehensive research protocol and experiment map
├── .gitignore                     # Git ignore rules for virtual environments and checkpoints
├── Step 1/                        # Step 1: Data Preparation & Evolving Attacks
│   ├── step_1_master_reference.md # Complete dossier: math, statistics, and 27-point audit
│   ├── HANDOFF_README.md          # Step 1 -> Step 2 transition specification
│   ├── CONFIG/                    # YAML configuration files for attack generation
│   ├── DATA/                      # Frozen benchmark (ausgrid_solar_attacked.parquet)
│   └── DOCUMENTATION/             # Attack models and conversion audit reports
└── Step 2/                        # Step 2: Local AI Defense & Calibration
    ├── step_2_master_reference.md # Step 2 complete dossier: architecture, convergence & metrics
    ├── dataset.py                 # Parquet ingestion, 24h diurnal windowing, Phase 1 scaler
    ├── model.py                   # 1-D Convolutional Autoencoder architecture
    ├── train.py                   # 15-epoch training loop on Phase 1 clean baseline
    ├── evaluate.py                # Reconstruction error, Platt scaling, and scorecard
    ├── checkpoints/               # Serialized model weights (local_autoencoder_c1.pt)
    └── outputs/                   # Evaluation artifacts and performance figures
```

---

## Quickstart (Step 2 Local Model)

To run the verified local anomaly detector:

```bash
# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Verify dataset windowing
python "Step 2\dataset.py"

# 3. Train 1-D Conv-AE on Phase 1 clean baseline
python "Step 2\train.py"

# 4. Evaluate against 3-year evolving attack stream with calibration
python "Step 2\evaluate.py"
```

For full details on dataset specifications and empirical validation, see [`Step 1/step_1_master_reference.md`](Step%201/step_1_master_reference.md) and [`Step 2/step_2_master_reference.md`](Step%202/step_2_master_reference.md).
