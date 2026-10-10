# Cyber-Economic Resilience Under Evolving Attacks

A research framework investigating data-local continual federated defense and economic resilience in decentralized peer-to-peer (P2P) energy markets subject to evolving False Data Injection Attacks (FDIAs).

---

## Research Vision

> **Core Research Question**: How can a data-local continual federated detector adapt to evolving FDIAs while translating uncertain cyber-threat predictions into economically resilient mitigation decisions in P2P energy markets?

### Multi-Step Architecture:

#### Layer 1 — Cybersecurity & Machine Learning
- **[Step 1: Data Preparation & Evolving Attacks](Step%201/README.md)**  
  Data preprocessing of the Ausgrid solar dataset (299 prosumers, 3 years, 15.7M observations) and generation of a 4-phase temporally evolving FDIA benchmark (Scaling, Ramp, Replay, and Coordinated attacks).
- **Step 2: Local AI Defense** *(Next Phase)*  
  Temporal sliding windows, 1D-Convolutional Autoencoders, reconstruction error probability calibration, and local anomaly detectors.
- **Step 3: Privacy-Aware Collaboration**  
  Federated aggregation and privacy-preserving consensus.
- **Step 4: Continual Learning**  
  Memory-aware continual model adaptation to counteract catastrophic forgetting under non-stationary attack distributions.

#### Layer 2 — Economic Resilience
- **Step 5: Economic-Aware Mitigation Decision**  
  Coupling threat probabilities with risk-adjusted microgrid dispatch and bidding constraints.
- **Step 6: Economic Resilience Evaluation**  
  Continuous double auction (CDA) market clearing simulation and economic surplus loss quantification.

---

## Repository Structure

```text
cyber-economic-p2p-defense/
├── README.md                      # Project-level overview and roadmap
├── .gitignore                     # Git ignore rules for environments and large telemetry
└── Step 1/                        # Step 1: Data Preparation & Evolving Attacks
    ├── README.md                  # Comprehensive documentation for Step 1
    ├── requirements.txt           # Python dependencies for Step 1
    ├── configs/                   # Attack generation configurations
    ├── src/                       # Preprocessing, attack generator, and validation code
    ├── outputs/                   # Audits, model specifications, and verification reports
    ├── Planning/                  # Project planning documentation
    ├── Step 2 Handoff/            # Detailed handoff package for Step 2 modeling
    └── data/                      # Placeholders and instructions for raw and processed datasets
```

For full details on Step 1, data access instructions, and reproduction commands, please see [`Step 1/README.md`](Step%201/README.md).