# Step 1: Data Preparation & Evolving Attacks

**Project**: Cyber-Economic Resilience Under Evolving Attacks  
**Phase**: Step 1 (Step 1.1: Preprocessing & Validation; Step 1.2: Evolving Attack Benchmark Generation)  
**Status**: **COMPLETE, VERIFIED, AUDITED, AND FROZEN**

---

## 1. Overview & Research Objectives

In decentralized peer-to-peer (P2P) energy markets, prosumers trade energy through local continuous double auctions (CDA). Malicious actors can launch False Data Injection Attacks (FDIAs) against smart meter telemetry (General Consumption $GC$, Gross Generation $GG$, or Net Power $P_{\text{net}} = GC - GG$) to fraudulently manipulate settlement prices, evade charges, or destabilize grid scheduling.

The objective of **Step 1** is to construct a rigorous, reproducible, and realistic cybersecurity benchmark representing **temporally evolving FDIAs** over a multi-year horizon using real-world half-hourly smart meter telemetry.

---

## 2. Directory Structure

```text
Step 1/
├── README.md                      # Comprehensive guide to Step 1
├── requirements.txt               # Step 1 Python environment dependencies
├── configs/
│   └── attack_config.yaml         # Authoritative attack generation configuration
├── src/
│   ├── data_preprocessing.py      # Cleans, reshapes, and validates Ausgrid raw telemetry
│   ├── attack_generator.py        # Implements the 4-phase evolving FDIA model
│   └── validation.py              # 27 rigorous audit and invariant checks
├── outputs/
│   ├── dataset_inspection_report.md          # Raw Ausgrid data quality analysis
│   ├── preprocessing_report.md               # Preprocessing cohort selection & audit
│   ├── attack_model_specification.md         # Frozen attack formulation specification
│   ├── attack_generation_report.md           # Benchmark generation audit (27/27 PASS)
│   └── parquet_to_csv_conversion_report.md   # Parquet-to-CSV verification report
├── Planning/
│   └── MAJOR PROJECT PLAN.docx               # Overall project charter and milestones
├── Step 2 Handoff/
│   ├── HANDOFF_README.md          # Step 1 → Step 2 handoff specification
│   ├── CONFIG/                    # Frozen attack configuration for downstream tasks
│   ├── DATA/                      # Checksums and specifications for benchmark files
│   └── DOCUMENTATION/             # Authoritative attack specification and reports
└── data/
    ├── raw/                       # Raw Ausgrid yearly CSV files (see data/raw/README.md)
    └── processed/                 # Frozen clean and attacked datasets (see data/processed/README.md)
```

---

## 3. Dataset & Cohort Selection

- **Source**: Ausgrid Solar Home Electricity Dataset (New South Wales, Australia).
- **Time Horizon**: July 1, 2010 through June 30, 2013 (3 calendar years = 1,096 continuous days = 52,608 half-hour intervals).
- **Cohort Selection**:
  - Total raw households: 300.
  - **Customer 2 Excluded**: Excluded due to 81 contiguous missing days (2012-10-12 through 2012-12-31) in both GC and GG. Imputation was rejected to preserve observational integrity.
  - **Retained Cohort**: **299 prosumers** with 100% complete records across all 1,096 days.
- **Benchmark Observation Count**:
  $$\text{Total Observations} = 299 \text{ customers} \times 52,608 \text{ intervals} = 15,729,792 \text{ rows}$$

---

## 4. Evolving Attack Model Architecture

The benchmark introduces four chronological attack phases reflecting adversaries with increasing sophistication and capabilities:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        CHRONOLOGICAL PROGRESSION                       │
├─────────────────┬──────────────────┬─────────────────┬─────────────────┤
│ Phase 1: NORMAL │ Phase 2: SCALING │  Phase 3: RAMP  │ Phase 4: EVOLVE │
│  (Days 1 - 365) │ (Days 366 - 601) │(Days 602 - 851) │(Days 852 - 1096)│
│  5,238,480 rows │ 3,387,072 rows   │ 3,588,000 rows  │ 3,516,240 rows  │
│  0% attacked    │ Multiplicative   │ Additive drift  │ 4A: Replay      │
│                 │ α ∈ [0.1, 3.0]   │ δ parameter     │ 4B: Coordinated │
└─────────────────┴──────────────────┴─────────────────┴─────────────────┘
```

1. **Phase 1: Normal (Clean Baseline)**:
   - Days 1 to 365 (2010-07-01 to 2011-06-30).
   - 0 attacks. Establishes the uncorrupted baseline for training anomaly detectors.
2. **Phase 2: Scaling Attacks**:
   - Days 366 to 601 (2011-07-01 to 2012-02-21).
   - Multiplicative distortion: $x'_t = \alpha \cdot x_t$, with scaling factor $\alpha \in [0.1, 0.5] \cup [1.5, 3.0]$.
   - Targets: GC, GG, or BOTH independently.
3. **Phase 3: Ramp (Drift) Attacks**:
   - Days 602 to 851 (2012-02-22 to 2012-10-28).
   - Slowly increasing additive bias: $x'_t = x_t + \delta \cdot \frac{t - t_{\text{start}}}{L}$.
   - Designed to bypass simple threshold-based detection filters.
4. **Phase 4A: Replay Attacks**:
   - Days 852 to 973 (2012-10-29 to 2013-02-27).
   - Telemetry substitution from genuine historical records: $x'_t = x_{t - \tau \cdot 48}$, preserving diurnal profiles.
5. **Phase 4B: Coordinated Attacks**:
   - Days 974 to 1096 (2013-02-28 to 2013-06-30).
   - Synchronized manipulation across multiple compromised prosumers.

---

## 5. Authoritative Datasets & Cryptographic Checksums

All datasets are frozen and deterministically reproducible with master seed `42`.

| Dataset Role | File Path | Format | Rows | Cols | SHA-256 Checksum |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Clean Baseline** | `data/processed/ausgrid_solar_processed.parquet` | Parquet | 15,729,792 | 13 | `dc6bac0ea84a30b84af343ebd1ad7abd6905f9188989fc533a3a53a1d5c878b7` |
| **Attacked Benchmark** | `data/processed/ausgrid_solar_attacked.parquet` | Parquet | 15,729,792 | 19 | `176fa03152359472b544f2197427bca92f51127e4c2becad84e31ec72f6ca1b4` |
| **Attacked Benchmark** | `data/processed/ausgrid_solar_attacked.csv` | CSV | 15,729,792 | 19 | `819ce00d29b5de917bdf2ff86e76da8befa092f59ca7c15ca32b233ad2747682` |

### Attack Distribution Breakdown:
- **Clean Observations (`is_attacked == False`)**: 15,283,221 (97.1610%)
- **Attacked Observations (`is_attacked == True`)**: 446,571 (2.8390%)
  - RAMP: 179,360
  - SCALING: 163,784
  - REPLAY: 86,907
  - COORDINATED: 16,520
- **Physical Boundedness**: 100% of telemetry satisfies non-negativity ($GC \ge 0, GG \ge 0$) and generator capacity limits ($GG \le C_{\text{gen}}$).

---

## 6. How to Reproduce

### 1. Environment Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Preprocessing Pipeline
Place raw Ausgrid files into `data/raw/` and execute:
```bash
python src/data_preprocessing.py
```
This produces the clean baseline `data/processed/ausgrid_solar_processed.parquet`.

### 3. Generate Attacked Benchmark
```bash
python src/attack_generator.py
```
This applies the 4-phase evolving attack model configured in `configs/attack_config.yaml` using seed 42.

### 4. Run Audits & Validation Suite
```bash
python src/validation.py
```
Executes all 27 mathematical and invariant validation checks.

---

## 7. Step 2 Transition

The output of Step 1 is frozen and documented for **Step 2: Local AI Defense (1D-CNN Autoencoders, Sliding Window Construction, and Probability Calibration)**.

Refer to [`Step 2 Handoff/HANDOFF_README.md`](Step%202%20Handoff/HANDOFF_README.md) for full interface specifications.
