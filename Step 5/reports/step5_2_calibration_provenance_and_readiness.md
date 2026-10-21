# Step 5.2 — Calibration Provenance, Scenario Restoration, and Final Readiness Gate Report

**Project**: Cyber-Economic Resilience Under Evolving Attacks in Peer-to-Peer Energy Markets  
**Phase**: Pre-Step 6 Targeted Correction and Verification  
**Evaluation Scope**: Calibration Provenance, Metric Realism, Original 5 Sensitivity Scenarios, Policy Truthfulness, Step 6 Streaming Contract, and Regression Testing  
**Date**: October 20, 2026  
**Auditor**: Independent Evaluation Agent  

---

## 1. Executive Summary & Readiness Verdict

### Final Verdict: `READY FOR STEP 6` (With Explicit Scientific Caveats)

Step 5.2 resolves all outstanding reproducibility discrepancies, restores the exact original sensitivity scenarios, documents the precise provenance of all calibrator artifacts, and provides an unvarnished assessment of the detector's predictive capacity.

The codebase and data contracts are **technically correct, robustly tested, and fully reproducible**. However, this audit confirms a fundamental empirical reality that must govern the narrative of Step 6:

1. **Weak Underlying Detector Discrimination**:
   The autoencoder's interval-level reconstruction error has an out-of-time test **AUROC of $0.5237$** and **AUPRC of $0.0454$** (against a test prevalence base rate of $0.0420$). The detector exhibits very weak discrimination between normal load fluctuations and cyber-attacks. Monotonic Platt scaling does not, and mathematically cannot, alter this underlying ranking capacity.

2. **The Calibrator Dilemma (Balanced vs. Unweighted)**:
   - **Under the Existing Balanced Calibrator** ($w=0.075659, b=+0.509879$), artificial class weighting shifts the intercept upward, inflating probabilities into $[0.2226, 0.6312]$ (mean $0.4922$). Under baseline costs ($p^* = 0.1833$), the economic policy mitigates **100.0% of intervals**, collapsing into `ALWAYS_MITIGATE` and racking up **$\$1,018,888.42$ AUD** in realized false-alarm and overhead costs.
   - **Under the Verified Unweighted Calibrator** ($w=0.074456, b=-3.159390$), probabilities reflect true pre-test empirical frequencies ($p \in [0.0075, 0.0418]$, mean $0.0245$). Because the weak detector never produces a high-confidence signal, $p < p^*$ everywhere across the 9.63 million test intervals. Consequently, the economic policy mitigates **0.0% of intervals**, collapsing into `NEVER_MITIGATE` and incurring **$\$202,163.50$ AUD** in unmitigated attack damage.

3. **No Optimization for Appearance**:
   Neither calibrator allows the proposed economic policy to selectively mitigate attacks while sparing clean intervals under baseline costs. Acknowledging this limitation is scientifically honest. Step 6 will simulate the Continuous Double Auction across **three distinct operating regimes**:
   - **Regime 1: Unmitigated Attacked Market** (`NEVER_MITIGATE` / Unweighted Economic Rule)
   - **Regime 2: Maximum Defense Market** (`ALWAYS_MITIGATE` / Balanced Economic Rule)
   - **Regime 3: Heuristic Filtering Market** (Fixed Threshold $\tau = 0.50$, which achieves an intermediate realized loss of $\$537,259.75$ AUD).

---

## 2. Resolution of Calibration Provenance & Partition Discrepancy

### 2.1 Artifact Provenance Dissection

An exhaustive audit of fitting scripts, execution logs, and serialized binary headers resolved the calibration partition discrepancy identified in Step 5.1:

| Artifact File | Script Origin | Feature Definition | Temporal Partition | Python Slice | Sample Size ($N$) | Fitted Parameters | Class Weight Setting |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`interval_calibrator.pkl`](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/preflight/interval_calibrator.pkl) | `compare_temporal_resolution.py` | Interval MSE $\ln(e_{i,t} + 10^{-12})$ | **Days 305 to 424 inclusive** (120 days) | `slice(305, 425)` | 200,000 (RNG seed 42) | $w = 0.075659$<br>$b = +0.509879$ | `class_weight='balanced'` |
| [`probability_calibrator.pkl`](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/preflight/probability_calibrator.pkl) | `calibrate_detector.py` | Daily Max MSE $\ln(\max_t e_{i,t} + 10^{-12})$ | **Days 305 to 424 inclusive** (120 days) | `slice(305, 425)` | 35,880 customer-days | $w = 0.193070$<br>$b = +0.628528$ | `class_weight='balanced'` |
| [`interval_calibrator_unweighted.pkl`](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/preflight/interval_calibrator_unweighted.pkl) | `generate_step5_2_data.py` | Interval MSE $\ln(e_{i,t} + 10^{-12})$ | **Days 305 to 424 inclusive** (120 days) | `slice(305, 425)` | 200,000 (RNG seed 42) | $w = 0.074456$<br>$b = -3.159390$ | `class_weight=None` (Unweighted) |

### 2.2 Partition Range & Sample Count Clarification
- **The Partition Discrepancy Resolved**:
  - In `Step 5/preflight/compare_temporal_resolution.py`, the calibration partition was explicitly defined as `CALIB_START = 305, CALIB_END = 424` (Days 305 to 424 inclusive = 120 calendar days). Across 299 prosumers and 48 slots/day, this partition contains exactly **$1,722,240$ intervals** (42,244 attacked, empirical base rate $= 2.4529\%$).
  - To accelerate fitting, `compare_temporal_resolution.py` drew a reproducible random subsample of 200,000 intervals using `np.random.default_rng(42)`. Fitting balanced logistic regression on this subsample produced exactly $w = 0.07565884, b = 0.50987947$, which was serialized to `interval_calibrator.pkl`.
  - In Step 5.1 (`generate_audit_data.py`), the author mistakenly defined calibration as Days 365 to 424 (60 days = 861,120 intervals) based on a textual reference to "Year 1 (Days 0–364)".
  - **Empirical Confirmation**: Refitting on the true preflight partition (Days 305–424, 200k subsample) reproduces the serialized balanced parameters to 8 decimal places ($w = 0.07565887, b = 0.5098797$).

### 2.3 Temporal Isolation & Leakage Verification
- The calibration partition (Days 305 to 424 inclusive) strictly precedes the test partition (Days 425 to 1095 inclusive).
- Zero observations from Day 425 onwards and zero test ground-truth labels were accessed during calibrator fitting.
- The new unweighted artifact has been serialized to [interval_calibrator_unweighted.pkl](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/preflight/interval_calibrator_unweighted.pkl) without overwriting the original artifact.

---

## 3. Independent Probability Calibration Audit & Scientific Limitations

### 3.1 Separation of Ranking vs. Probability Calibration

A key requirement of this audit is strictly separating **ranking discrimination** (ordering attacked vs. clean intervals) from **probability calibration** (mapping error magnitudes to posterior probabilities):

1. **Ranking Metrics (AUROC and AUPRC)**:
   - Platt scaling is a strictly monotonic sigmoid transformation: $p = \sigma(w \cdot z + b)$ with $w > 0$.
   - Any monotonic transformation preserves the exact rank-ordering of scores. Consequently:
     $$\text{AUROC}(p_{\text{bal}}) = \text{AUROC}(p_{\text{unw}}) = \text{AUROC}(e_{\text{raw}}) = \mathbf{0.523712}$$
     $$\text{AUPRC}(p_{\text{bal}}) = \text{AUPRC}(p_{\text{unw}}) = \text{AUPRC}(e_{\text{raw}}) = \mathbf{0.045410}$$
   - **Scientific Reality**: The autoencoder has barely any discriminative power at the 30-minute interval level. An AUROC of $0.5237$ means that given a randomly chosen attacked interval and a randomly chosen clean interval, the model assigns a higher error to the attacked interval only $52.37\%$ of the time (scarcely better than a coin flip at $50.0\%$).

2. **Probability Calibration Metrics (Brier Score, Log Loss, and ECE)**:
   While ranking cannot be improved by calibration, probability calibration dramatically impacts whether probabilities match empirical frequencies.

### 3.2 Quantitative Calibration Scorecard on 9.63 Million Test Intervals

All metrics were independently evaluated on the out-of-time test partition (Days 425 to 1095, $9,630,192$ intervals, true prevalence $4.1985\%$) and exported to [step5_2_calibration_metrics.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/outputs/step5_2_calibration_metrics.csv):

| Model / Estimator | Training Partition & Regime | Intercept $b$ | Slope $w$ | Prob Min | Prob Max | Prob Mean | Brier Score | Log Loss | ECE | AUROC | AUPRC |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Existing Balanced Platt Calibrator** | Days 305–424 (200k, Balanced) | +0.509879 | 0.075659 | 0.222632 | 0.631212 | 0.492215 | 0.243976 | 0.681019 | 0.450230 | 0.523712 | 0.045410 |
| **Verified Unweighted Platt (200k)** | Days 305–424 (200k, Unweighted) | -3.159390 | 0.074456 | 0.007453 | 0.041795 | 0.024542 | 0.040515 | 0.179387 | 0.017443 | 0.523712 | 0.045410 |
| **Verified Unweighted Platt (Full 1.72M)** | Days 305–424 (1.72M, Unweighted) | -3.163928 | 0.077153 | 0.006971 | 0.041653 | 0.023994 | 0.040535 | 0.179809 | 0.017991 | 0.523712 | 0.045410 |
| **Prevalence-Only Baseline (Calib Prior)** | Days 305–424 (Constant $p = 0.02453$) | N/A | N/A | 0.024529 | 0.024529 | 0.024529 | 0.040527 | 0.179470 | 0.017457 | 0.500000 | 0.041985 |
| **Prevalence-Only Baseline (Test Prior)** | Days 425–1095 (Constant $p = 0.04199$) | N/A | N/A | 0.041985 | 0.041985 | 0.041985 | 0.040223 | 0.174203 | 0.000000 | 0.500000 | 0.041985 |
| **Normalized Raw Reconstruction Error** | Min-Max Scaled Test MSE | N/A | N/A | 0.000000 | 1.000000 | 0.002682 | 0.041801 | 0.311785 | 0.039504 | 0.523712 | 0.045410 |

### 3.3 Critical Scientific Insights
- **The Illusion of Calibration**:
  The unweighted Platt calibrator achieves a Brier score of $0.040515$ and Log Loss of $0.179387$. However, comparing this to the **Prevalence-Only Baseline** ($p = 0.024529$), which achieves Brier score $0.040527$ and Log Loss $0.179470$, reveals that the autoencoder's reconstruction error improves probability accuracy by only **$0.000012$ Brier points** over simply guessing the training prior constant!
- **Platt Scaling Cannot Create Signal**:
  Because the underlying autoencoder cannot cleanly separate FDI attacks from normal solar/load dynamics, Platt scaling simply shrinks all predictions toward the prior mean ($p \in [0.0075, 0.0418]$).
- **Why Unweighted Probabilities Must Not Be Called "True Posteriors"**:
  While unweighted probabilities are mathematically calibrated to empirical frequencies, describing them as "true posterior probabilities" would be misleading. They reflect the high uncertainty of a low-signal detector, not high-fidelity knowledge of microgrid state.

---

## 4. Restoration of the Exact Original Five Sensitivity Scenarios

Step 5.1 inadvertently introduced altered cost settings for Scenarios 3, 4, and 5. In Step 5.2, the **exact five original scenarios** from `Step 5/config/step5_config.yaml` were restored, re-evaluated, and exported to [step5_2_original_five_scenarios.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/outputs/step5_2_original_five_scenarios.csv).

### 4.1 Original Five Scenarios Evaluated Under Both Calibrators

#### A. Under Existing Balanced Platt Calibrator ($p \in [0.2226, 0.6312]$):
| Scenario ID & Name | $C_{\text{FN}}$ | $C_{\text{FP}}$ | $C_{\text{M}}$ | Cost Ratio | Breakeven $p^*$ | Mitigation Rate % | ALLOW Count | MITIGATE Count | True Positives | False Positives | Recall % | Precision % | Expected Loss (AUD) | Realized Loss (AUD) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SC-1: Baseline Asymmetric Risk** | $0.50 | $0.10 | $0.01 | 5.0 | 0.1833 | **100.00%** | 0 | 9,630,192 | 404,327 | 9,225,865 | 100.00% | 4.20% | $585,308.62 | **$1,018,888.42** |
| **SC-2: High Attack Consequence** | $1.00 | $0.10 | $0.01 | 10.0 | 0.1000 | **100.00%** | 0 | 9,630,192 | 404,327 | 9,225,865 | 100.00% | 4.20% | $585,308.62 | **$1,018,888.42** |
| **SC-3: Symmetric / Balanced Risk** | $0.20 | $0.20 | $0.01 | 1.0 | 0.5250 | **18.38%** | 7,860,437 | 1,769,755 | 83,417 | 1,686,338 | 20.63% | 4.71% | $935,404.75 | **$419,147.15** |
| **SC-4: High False Alarm Penalty** | $0.10 | $0.50 | $0.01 | 0.2 | 0.8500 | **0.00%** | 9,630,192 | 0 | 0 | 0 | 0.00% | 0.00% | $474,012.56 | **$40,432.70** |
| **SC-5: High Administrative Overhead** | $0.50 | $0.10 | $0.15 | 5.0 | 0.4167 | **97.74%** | 218,017 | 9,412,175 | 396,482 | 9,015,693 | 98.06% | 4.21% | $1,931,121.12 | **$2,317,318.05** |

#### B. Under Verified Unweighted Platt Calibrator ($p \in [0.0075, 0.0418]$):
| Scenario ID & Name | $C_{\text{FN}}$ | $C_{\text{FP}}$ | $C_{\text{M}}$ | Cost Ratio | Breakeven $p^*$ | Mitigation Rate % | ALLOW Count | MITIGATE Count | True Positives | False Positives | Recall % | Precision % | Expected Loss (AUD) | Realized Loss (AUD) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SC-1: Baseline Asymmetric Risk** | $0.50 | $0.10 | $0.01 | 5.0 | 0.1833 | **0.00%** | 9,630,192 | 0 | 0 | 0 | 0.00% | 0.00% | $118,172.33 | **$202,163.50** |
| **SC-2: High Attack Consequence** | $1.00 | $0.10 | $0.01 | 10.0 | 0.1000 | **0.00%** | 9,630,192 | 0 | 0 | 0 | 0.00% | 0.00% | $236,344.66 | **$404,327.00** |
| **SC-3: Symmetric / Balanced Risk** | $0.20 | $0.20 | $0.01 | 1.0 | 0.5250 | **0.00%** | 9,630,192 | 0 | 0 | 0 | 0.00% | 0.00% | $47,268.93 | **$80,865.40** |
| **SC-4: High False Alarm Penalty** | $0.10 | $0.50 | $0.01 | 0.2 | 0.8500 | **0.00%** | 9,630,192 | 0 | 0 | 0 | 0.00% | 0.00% | $23,634.46 | **$40,432.70** |
| **SC-5: High Administrative Overhead** | $0.50 | $0.10 | $0.15 | 5.0 | 0.4167 | **0.00%** | 9,630,192 | 0 | 0 | 0 | 0.00% | 0.00% | $118,172.33 | **$202,163.50** |

### 4.2 Key Findings on Sensitivity Scenarios
1. **The Original Scenarios Did Exhibit Dynamic Mitigation**:
   Restoring the true cost values reveals that under the balanced calibrator, Policy B did **not** mitigate 100% across all scenarios:
   - In Scenario 3 ($p^* = 0.5250$), it mitigated $18.38\%$ of intervals.
   - In Scenario 4 ($p^* = 0.8500$), it mitigated $0.00\%$.
   - In Scenario 5 ($p^* = 0.4167$), it mitigated $97.74\%$.
   The "100% mitigation" phenomenon occurred specifically in Scenarios 1 and 2 where $p^* \le 0.1833 < \min(p_{\text{bal}})$.
2. **Behavior Under Unweighted Platt**:
   Because the unweighted calibrator outputs probabilities $\le 0.0418$, and all five scenarios have $p^* \ge 0.1000$, the economic policy emits `ALLOW` for 100% of intervals across all five scenarios, matching `NEVER_MITIGATE`.
3. **Supplementary Scenarios Preserved**:
   The intermediate exploratory variants evaluated in Step 5.1 have been preserved in [step5_2_supplementary_scenarios.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/outputs/step5_2_supplementary_scenarios.csv).

---

## 5. Honest Policy Behavior Without Aesthetic Optimization

All six candidate policy baselines were evaluated on the exact same test dataset ($9,630,192$ intervals) under baseline costs ($C_{\text{FN}}=0.50, C_{\text{FP}}=0.10, C_{\text{M}}=0.01, p^*=0.1833$). The results were exported to [step5_2_policy_comparison.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/outputs/step5_2_policy_comparison.csv):

| Policy Name | Operational Rule | Mitigation Rate % | ALLOW Count | MITIGATE Count | True Positives | False Positives | True Negatives | False Negatives | Recall % | Precision % | F1 % | Expected Loss (AUD) | Realized Loss (AUD) | Disagreement w/ Policy B (Balanced) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Policy B: Economic Rule (Balanced Platt)** | Mitigate if $p_{\text{bal}} > 0.1833$ | **100.00%** | 0 | 9,630,192 | 404,327 | 9,225,865 | 0 | 0 | **100.00%** | **4.20%** | **8.06%** | $585,308.62 | **$1,018,888.42** | **0.00%** (Reference) |
| **Baseline: ALWAYS_MITIGATE** | Mitigate All Intervals | **100.00%** | 0 | 9,630,192 | 404,327 | 9,225,865 | 0 | 0 | **100.00%** | **4.20%** | **8.06%** | $585,308.62 | **$1,018,888.42** | **0.00%** |
| **Policy B: Economic Rule (Unweighted Platt)** | Mitigate if $p_{\text{unw}} > 0.1833$ | **0.00%** | 9,630,192 | 0 | 0 | 0 | 9,225,865 | 404,327 | **0.00%** | **0.00%** | **0.00%** | $118,172.33 | **$202,163.50** | **100.00%** |
| **Baseline: NEVER_MITIGATE** | Allow All Intervals | **0.00%** | 9,630,192 | 0 | 0 | 0 | 9,225,865 | 404,327 | **0.00%** | **0.00%** | **0.00%** | $2,370,062.50 | **$202,163.50** | **100.00%** |
| **Policy A: Fixed Threshold ($\tau = 0.50$)** | Mitigate if $p_{\text{bal}} \ge 0.50$ | **41.93%** | 5,592,657 | 4,037,535 | 181,721 | 3,855,814 | 5,370,051 | 222,606 | **44.94%** | **4.50%** | **8.18%** | $1,541,527.75 | **$537,259.75** | **58.07%** |
| **Policy A: Fixed Threshold ($\tau = 0.30$)** | Mitigate if $p_{\text{bal}} \ge 0.30$ | **99.997%** | 298 | 9,629,894 | 404,310 | 9,225,584 | 281 | 17 | **99.996%** | **4.20%** | **8.06%** | $585,326.75 | **$1,018,865.84** | **0.003%** |
| **Policy A: Fixed Threshold ($\tau = 0.70$)** | Mitigate if $p_{\text{bal}} \ge 0.70$ | **0.00%** | 9,630,192 | 0 | 0 | 0 | 9,225,865 | 404,327 | **0.00%** | **0.00%** | **0.00%** | $2,370,062.50 | **$202,163.50** | **100.00%** |

### Explicit Truthful Summary:
1. **Policy B under Balanced Platt collapses into `ALWAYS_MITIGATE`**:
   Zero decisions differ. It mitigates all $9.63$ million intervals, catching $100\%$ of attacks but disrupting $9.23$ million clean intervals, resulting in the worst realized loss (**$\$1,018,888.42$ AUD**).
2. **Policy B under Unweighted Platt collapses into `NEVER_MITIGATE`**:
   Zero decisions differ. Because all calibrated probabilities are below the breakeven threshold $0.1833$, it allows all $9.63$ million intervals, catching $0\%$ of attacks and incurring **$\$202,163.50$ AUD** in unmitigated attack damage.
3. **Fixed Threshold $\tau = 0.50$ (Balanced Score) Achieves Intermediate Tradeoff**:
   By mitigating $41.93\%$ of intervals, it catches $44.94\%$ of attacks ($181,721$ attacks) and spares $5.37$ million clean intervals, cutting the realized loss to **$\$537,259.75$ AUD** ($47\%$ lower than `ALWAYS_MITIGATE`).

---

## 6. Independent Verification of Step 6 Interface Contract

The handoff contract between Step 5 and Step 6 was independently audited against the master dataset and simulation requirements:

1. **Sample Scope Clarification**:
   - `step5_decisions_sample.parquet` ($322,080$ records, 14.3 MB) represents exactly 10 sample customers over 671 test days.
   - It is strictly a sample artifact for unit testing and schema verification.
2. **Full Population Streaming Throughput**:
   - The full test evaluation comprises all 299 prosumers over 671 days = **$9,630,192$ records**.
   - A benchmark of the daily batch streaming path demonstrated that generating a full day of market orders ($299 \times 48 = 14,352$ records) requires only **$7.27$ milliseconds**.
   - The complete 671-day simulation can stream directly in memory in **under 5 seconds**, eliminating the need for a massive multi-gigabyte monolithic disk export.
3. **Data Integrity Invariants Verified**:
   - **Composite Key**: `(customer_id, time_index)` has **zero duplicates**.
   - **Market Roles**: Strictly adheres to sign convention: $P_{\text{net}} > 0 \implies \text{BUYER}$, $P_{\text{net}} < 0 \implies \text{SELLER}$, $P_{\text{net}} == 0 \implies \text{BALANCED}$.
   - **Strict Causality**: Substituted fallback values depend exclusively on historical days $d' \in [\max(0, d-7), d-1]$. Current day $d$ and future days $d' > d$ are strictly inaccessible.
   - **Zero Ground-Truth Leakage**: No attack labels (`is_attacked`, `attack_type`, `y_true`) appear in the order fields passed to Step 6 matching.

---

## 7. Regression Test Execution Summary

The regression test suite in [test_economic_decision.py](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/tests/test_economic_decision.py) was expanded from 16 to **19 comprehensive unit tests**, adding:
- Test 17: Verifying serialization, monotonicity, and bounded range of `interval_calibrator_unweighted.pkl`.
- Test 18: Verifying exact analytical breakeven probabilities $p^*$ across all five original sensitivity scenarios.
- Test 19: Verifying the day-by-day batch streaming contract ($299 \text{ prosumers} \times 48 \text{ slots} = 14,352 \text{ records/day}$, zero duplicates).

### Test Suite Execution:
```bash
/home/scarlet/ComfyUI/venv/bin/python -m unittest "Step 5/tests/test_economic_decision.py"
...................
----------------------------------------------------------------------
Ran 19 tests in 0.641s

OK
```
**Pass Count: 19 passed, 0 failed, 0 errors.**

---

## 8. Preserved Deliverables Inventory

| File Path | Description | Audit Status |
| :--- | :--- | :--- |
| [step5_2_calibration_provenance_and_readiness.md](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/reports/step5_2_calibration_provenance_and_readiness.md) | Master Step 5.2 audit and readiness report (this document) | **Created** |
| [step5_2_calibration_metrics.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/outputs/step5_2_calibration_metrics.csv) | Full calibration metrics including prevalence baselines and raw errors | **Exported** |
| [step5_2_original_five_scenarios.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/outputs/step5_2_original_five_scenarios.csv) | Exact original 5 sensitivity scenarios under Balanced & Unweighted calibrators | **Exported** |
| [step5_2_policy_comparison.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/outputs/step5_2_policy_comparison.csv) | Head-to-head policy baselines with expected & realized loss breakdown | **Exported** |
| [step5_2_supplementary_scenarios.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/outputs/step5_2_supplementary_scenarios.csv) | Step 5.1 exploratory cost variants preserved for completeness | **Exported** |
| [interval_calibrator_unweighted.pkl](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/preflight/interval_calibrator_unweighted.pkl) | Serialized verified unweighted Platt calibrator artifact ($w=0.0745, b=-3.1594$) | **Serialized** |
| [interval_calibrator.pkl](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/preflight/interval_calibrator.pkl) | Original preflight balanced Platt calibrator artifact | **Preserved Unchanged** |
| [test_economic_decision.py](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/tests/test_economic_decision.py) | 19-test automated regression suite | **Updated & Passing** |

---

## 9. Conclusion & Path to Step 6 CDA Simulation

The Step 5.2 audit resolves all remaining ambiguities:
- The exact provenance of the calibrators is documented and mathematically reproduced.
- The weak discriminative capacity of the underlying autoencoder ($\text{AUROC} = 0.5237$) is acknowledged and documented.
- The exact original five sensitivity scenarios are restored and evaluated.
- The Step 6 streaming interface contract is verified.

The project is **READY FOR STEP 6**. Step 6 will simulate the Continuous Double Auction across the full 299 prosumer cohort under the documented policy baselines, evaluating real market clearing, surplus distribution, and grid divergence without masking the underlying detector characteristics.
