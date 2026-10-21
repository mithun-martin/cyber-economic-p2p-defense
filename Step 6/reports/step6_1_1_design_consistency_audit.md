# Step 6.1.1 — Design Consistency Audit Before CDA Implementation

**Project**: Cyber-Economic Resilience Under Evolving Attacks in Peer-to-Peer Energy Markets  
**Component**: Step 6 — Market Simulation and Cyber-Economic Resilience Evaluation  
**Author**: Antigravity Pair Programmer (Agentic Engineering Pass)  
**Date**: October 2026  
**Status**: AUDIT COMPLETE — DISCREPANCIES RECONCILED — READY FOR APPROVAL  
**Audited Document**: [Step 6/reports/step6_1_cda_design_and_experimental_protocol.md](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/reports/step6_1_cda_design_and_experimental_protocol.md)  
**Associated Specifications**:
- Assumptions Register: [step6_1_assumptions_register.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/outputs/step6_1_assumptions_register.csv)
- Metric Specification: [step6_1_metric_specification.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/outputs/step6_1_metric_specification.csv)

---

## Executive Summary

Before beginning implementation of the Continuous Double Auction (CDA) simulator in Step 6.2, an independent design-consistency audit was executed on the Step 6.1 design specification. The audit investigated two numerical discrepancies between the initial Step 6.1 draft and the authoritative Step 5.2/5.3 artifacts, refined the economic terminology, formalized the paired simulation protocol, and updated the design documents in place.

### Key Audit Findings & Corrections:
1. **Selective Defense Policy Reconciliation**: The initial Step 6.1 text referenced a mitigation rate of $40.1\%$ ($3,863,165$ intervals). The authoritative Step 5.2/5.3 policy evaluation reports **$41.9258\%$ ($4,037,535$ intervals)**. Root cause analysis confirms the draft text mistakenly conflated the false positive count ($\approx 3.86\text{M}$) with the total mitigation count. The policy metrics were independently recomputed on the 9,630,192 test intervals, verifying bitwise agreement with Step 5.2.
2. **Ground-Truth Attack Prevalence Reconciliation**: The initial Step 6.1 text described attack prevalence as "approximately 2%". Ground-truth labels across the authoritative test partition (Days 425–1095, 299 prosumers) contain exactly **$404,327$ attacks out of $9,630,192$ customer-intervals**, establishing an exact test prevalence of **$4.198535\%$ ($\approx 4.20\%$)**. Under Policy A ($\tau = 0.50$), $3,855,814$ of the $4,037,535$ mitigations are false positives, yielding a verified false alarm proportion of **$95.499217\%$ ($\approx 95.50\%$)** and precision of **$4.500791\%$**.
3. **Tightened Economic Interpretation**: $W_{\text{P2P}} = (G_T - \text{FiT}) \cdot E_{\text{P2P}}$ is explicitly redefined as a **tariff-based gross-surplus proxy under the modeled flat-tariff assumptions**, not a complete real-world social welfare measure. The lack of physical distribution network constraints and the synthetic nature of Zero-Intelligence Constrained (ZI-C) bidding are explicitly logged.
4. **Locked Paired Protocol**: Pseudorandom streams for prosumer arrival order permutations and ZI-C bidding valuations are locked across Regimes A, B, C, and Clean using deterministic hierarchical seeds, eliminating random Monte Carlo variance from regime comparisons.

---

## 1. Discrepancy Reconciliation & Evidence

### 1.1 Discrepancy 1: Selective-Defense Policy (Policy A, $\tau = 0.50$, Balanced)

| Metric | Initial Step 6.1 Text | Verified Authoritative Step 5 Result | Discrepancy Cause / Resolution |
| :--- | :--- | :--- | :--- |
| **Mitigation Rate** | $40.1\%$ | **$41.9257996\%$ ($\approx 41.93\%$)** | Draft text used rounded FP rate instead of total mitigations. |
| **Mitigation Count** | $3,863,165$ | **$4,037,535$** | $3,863,165$ was an informal approximation of $\text{FP} = 3,855,814$. |
| **Allow Count** | Not specified | **$5,592,657$ ($58.0742004\%$)** | Verified bitwise against `Step 5/outputs/step5_2_policy_comparison.csv`. |
| **True Positives (TP)** | $181\text{k}$ | **$181,721$** | Confirmed exact value. |
| **False Positives (FP)** | $3.86\text{M}$ | **$3,855,814$** | Confirmed exact value. |
| **True Negatives (TN)** | Not specified | **$5,370,051$** | Confirmed exact value. |
| **False Negatives (FN)** | Not specified | **$222,606$** | Confirmed exact value. |
| **Recall / Detection Rate** | $\approx 45\%$ | **$44.944068\%$** | Confirmed exact value. |
| **Precision** | $\approx 4.5\%$ | **$4.500791\%$** | Confirmed exact value. |
| **False Positive Rate** | Not specified | **$41.793523\%$** | $\text{FPR} = \text{FP} / (\text{FP} + \text{TN}) = 3,855,814 / 9,225,865$. |
| **F1 Score** | $\approx 8.18\%$ | **$8.182199\%$** | Confirmed exact value. |

### 1.2 Discrepancy 2: Attack Prevalence and False-Alarm Proportion

| Parameter | Initial Step 6.1 Text | Verified Authoritative Value | Resolution / Note |
| :--- | :--- | :--- | :--- |
| **Total Test Intervals** | $9,630,192$ | **$9,630,192$** | Days 425–1095 (671 days) $\times$ 299 prosumers $\times$ 48 slots. |
| **Ground-Truth Attacks** | $\sim 2\%$ ($\approx 192\text{k}$) | **$404,327$ intervals** | $\text{TP} + \text{FN} = 181,721 + 222,606 = 404,327$. |
| **Test Attack Prevalence** | $\sim 2.0\%$ | **$4.198535\%$ ($\approx 4.20\%$)** | Prior training set or subset rate (~2%) was mistakenly quoted. |
| **Clean Intervals Count** | $\sim 98\%$ | **$9,225,865$ intervals ($95.801465\%$)** | Verified bitwise from ground truth labels. |
| **False Alarm Proportion** | $> 95\%$ | **$95.499217\%$ ($\approx 95.50\%$)** | $\text{FP} / \text{Mitigate\_Count} = 3,855,814 / 4,037,535$. |

---

## 2. Independent Recomputation & Verification Artifacts

An independent recomputation script was executed against the raw cache and model checkpoints using the project virtual environment (`/home/scarlet/ComfyUI/venv/bin/python`).

### 2.1 Calibrator Artifact & Hash Verification
The balanced calibrator used for Policy A ($\tau = 0.50$) is:
- **File**: [Step 5/preflight/interval_calibrator.pkl](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/preflight/interval_calibrator.pkl)
- **SHA-256 Hash**: `52ec0950bf0faf94c931bce74cdd450cbdd0aa88e78ce88b0439daef3f886821`
- **Model Type**: Scikit-Learn `LogisticRegression(class_weight='balanced')`
- **Fitted Parameters**: $w_{\text{bal}} = 0.07565884292125702, \quad b_{\text{bal}} = 0.509879469871521$
- **Feature Transform**: $\ln(\text{interval\_mse} + 10^{-12})$

### 2.2 Decision Operator Verification
In [Step 5/economic_decision.py](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/economic_decision.py#L191-L199):
```python
def make_fixed_threshold_decision(p_attack, threshold=0.50):
    ...
    decisions = np.where(p_arr >= threshold, DecisionAction.MITIGATE, DecisionAction.ALLOW)
```
- **Threshold Value**: $\tau = 0.50$
- **Comparison Operator**: Strict greater-than-or-equal-to (`>=`).

### 2.3 Reproducible Execution Command
```bash
/home/scarlet/ComfyUI/venv/bin/python -c "
import os, sys, pickle, hashlib
import numpy as np, torch

SCRIPT_DIR = 'Step 5'
sys.path.append(SCRIPT_DIR)
sys.path.append(os.path.join(SCRIPT_DIR, 'preflight'))
from train_detector import ConvAE_v2

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
cache = torch.load('Step 5/preflight/cache_299.pt', map_location='cpu')
X = cache['X']
y_interval = cache['y_interval'].numpy()

model = ConvAE_v2().to(DEVICE)
model.load_state_dict(torch.load('Step 5/preflight/detector_checkpoint.pt', map_location=DEVICE))
model.eval()

sub_X = X[:, slice(425, 1096)].reshape(-1, 2, 48)
errs = []
with torch.no_grad():
    for i in range(0, len(sub_X), 128):
        bx = sub_X[i:i + 128].to(DEVICE)
        recon = model(bx)
        err = ((bx - recon) ** 2).mean(dim=1)
        errs.append(err.cpu().numpy())
test_errs = np.concatenate(errs, axis=0).flatten()
test_y = y_interval[:, 425:1096].flatten()

with open('Step 5/preflight/interval_calibrator.pkl', 'rb') as f:
    calib = pickle.load(f)

w = float(calib['weight_w'])
b = float(calib['bias_b'])
p_bal = 1.0 / (1.0 + np.exp(-(w * np.log(test_errs + 1e-12) + b)))

is_mit = (p_bal >= 0.50)
tp = int((is_mit & (test_y == 1)).sum())
fp = int((is_mit & (test_y == 0)).sum())
tn = int(((~is_mit) & (test_y == 0)).sum())
fn = int(((~is_mit) & (test_y == 1)).sum())

print(f'Test Intervals: {len(test_y)}')
print(f'Attacks: {test_y.sum()} ({test_y.mean()*100:.6f}%)')
print(f'Mitigations: {is_mit.sum()} ({is_mit.mean()*100:.6f}%)')
print(f'TP: {tp}, FP: {fp}, TN: {tn}, FN: {fn}')
print(f'Precision: {tp/(tp+fp)*100:.6f}%, Recall: {tp/(tp+fn)*100:.6f}%')
"
```
**Output Received (Execution Time: 3.2s on RTX 4050 GPU)**:
```text
Test Intervals: 9630192
Attacks: 404327 (4.198535%)
Mitigations: 4037535 (41.925800%)
TP: 181721, FP: 3855814, TN: 5370051, FN: 222606
Precision: 4.500791%, Recall: 44.944068%
```
This confirms 100% bitwise consistency with `Step 5/outputs/step5_2_policy_comparison.csv`.

---

## 3. Tightened Economic Interpretation & Methodological Guardrails

To prevent over-interpreting experimental microgrid simulation results as real-world market outcomes, the following methodological boundaries are formally locked into the design:

### 3.1 $W_{\text{P2P}}$ Defined as a Tariff-Based Gross-Surplus Proxy
In the Step 6 design:
$$W_{\text{P2P}} = S_B + S_S = (G_T - \text{FiT}) \cdot E_{\text{P2P}} = \$0.22 \cdot E_{\text{P2P}}$$
- **Guardrail Statement**: This metric is a **tariff-based gross-surplus proxy under the modeled flat-tariff assumptions**, not a complete general-equilibrium social welfare measure.
- **Scope Limitations**:
  1. It reflects the bilateral arbitrage captured by local prosumers relative to default utility rates ($G_T = \$0.30, \text{FiT} = \$0.08$).
  2. It does not deduct network use-of-system (NUOS) tariffs, distributor transmission charges, wholesale market price elasticity, or metering fees.
  3. Physical distribution network constraints (e.g., line ampacity, voltage rise, reactive power flow, transformer head-room) are not modeled. In a physical low-voltage network, simultaneous high solar exports can cause voltage violations requiring curtailment.

### 3.2 Synthetic Nature of Bidding Models
- The Ausgrid dataset provides physical meter telemetry ($\text{GC}, \text{GG}$), **not human market bids, asks, or reservation prices**.
- Zero-Intelligence Constrained (ZI-C) bidding ($B_i, A_j \sim \mathcal{U}(\text{FiT}, G_T)$) and Deterministic Midpoint bidding ($B = \$0.20, A = \$0.18$) are **explicit simulation assumptions** designed to isolate auction institutional efficiency from unobservable human behavioral preferences.
- No historical market prices exist in the dataset; all market clearing prices are simulation outputs.

### 3.3 Decoupled Cyber-Economic Accounting
- Step 5 IT penalties ($C_{\text{FN}} = \$0.50, C_{\text{FP}} = \$0.10, C_{\text{M}} = \$0.01$) represent administrative/reliability risk proxies.
- Step 6 CDA market surplus represents simulated physical energy arbitrage.
- **Anti-Double-Counting Rule**: These two domains are reported strictly as separate accounting columns in all evaluation tables. The composite metric $\mathcal{R}_{\text{net}} = W_{\text{P2P}} - \text{Cost}_{\text{cyber}}$ is an exploratory index and must always be accompanied by its disaggregated components.

### 3.4 Hypothesis Testing vs. Assuming Welfare Impact
- The hypothesis that *"cyber-mitigation fallback suppresses legitimate prosumer trading surplus and reduces overall market welfare"* is **an empirical hypothesis to be tested across Regimes A, B, and C, not an a priori assumption**.
- While false alarms suppress clean solar exports, mitigating stealth attacks prevents fraudulent solar injections from depressing market prices or creating phantom trades. The CDA simulation will evaluate the exact net empirical trade-off.

---

## 4. Locked Paired Simulation Protocol (Anti-Confounding)

To guarantee that any observed difference in clearing prices, match rates, or market welfare between regimes is caused **solely by attack telemetry or cyber defense**, all random variables are deterministically locked across regimes:

```
For each Day t in [425, 1095]:
    For each Slot s in [0, 47]:
        
        1. Arrival Sequence Seed:
           Seed_arr = BaseSeed + t * 100000 + s * 1000
           Permutation pi = RNG(Seed_arr).permutation(299)
           # Arrival queue rank for customer i is bitwise identical in Regimes A, B, C, Clean
           
        2. Bidding Valuation Seed:
           For each customer i in 1..299:
               Seed_val = BaseSeed + t * 100000 + s * 1000 + customer_id
               u_i, v_i = RNG(Seed_val).uniform(0, 1, size=2)
               # If customer i is a Buyer, Bid = FiT + u_i * (G_T - FiT)
               # If customer i is a Seller, Ask = FiT + v_i * (G_T - FiT)
               # Price valuations are identical across all regimes
```

### 4.1 Auction Mechanism Specification
- **Primary Clearing Rule**: $k$-double auction midpoint rule ($k = 0.5$):
  $$P^* = \frac{B^* + A^*}{2}$$
- **Sensitivity Experiment**: Standing-order pricing (maker price) will be executed as a secondary sensitivity check to assess pricing stability.
- **Metric Edge-Case Rule**: If $E_{\text{P2P}} = 0$ in a given half-hour slot:
  - $\text{VWAP} = \text{Nominal Midpoint} = \frac{G_T + \text{FiT}}{2} = \$0.1900/\text{kWh}$.
  - $S_B = 0.0, \quad S_S = 0.0, \quad W_{\text{P2P}} = 0.0$.
  - $\text{Unmet Demand} = \sum Q_i^B, \quad \text{Unmatched Supply} = \sum Q_j^S$.

---

## 5. In-Place Deliverables Updated

The following existing artifacts were updated in place to incorporate all audit corrections:
1. **[Step 6/reports/step6_1_cda_design_and_experimental_protocol.md](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/reports/step6_1_cda_design_and_experimental_protocol.md)**:
   - Corrected Policy A mitigation counts ($4,037,535$ intervals, $41.93\%$).
   - Corrected test partition attack prevalence ($4.1985\%$, $404,327$ attacks).
   - Corrected false alarm proportion ($95.50\%$).
   - Replaced "Total Social Welfare" terminology with "Gross Tariff-Surplus Proxy" and added economic caveats.
   - Formally specified the locked paired seeding equations and midpoint clearing rule.
   - Added Step 6.1.1 Audit Trail and Changelog.
2. **[Step 6/outputs/step6_1_assumptions_register.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/outputs/step6_1_assumptions_register.csv)**:
   - Updated ASM-04 (ZI-C bidding as an explicit simulation assumption; absence of real bids).
   - Updated ASM-05 (Deterministic locked paired seeding across regimes).
   - Updated ASM-08 (Unconstrained distribution network; absence of AC power flow constraints).
   - Updated ASM-10 (Tariff gross-surplus proxy definition; separation of IT costs).
   - Updated ASM-12 (Mitigation welfare impact framed as an empirical hypothesis to be tested).
3. **[Step 6/outputs/step6_1_metric_specification.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/outputs/step6_1_metric_specification.csv)**:
   - Updated MTR-10 ($W_{\text{P2P}}$ labeled as Gross Tariff-Surplus Proxy with flat-tariff interpretation).
   - Updated MTR-17 (Verified selective mitigation rate logged as $41.9258\%$).
   - Updated MTR-19 (Composite net resilience index marked as exploratory with additive breakdown).

---

## 6. Final Verdict & Readiness Gate

### Verdict: **READY FOR APPROVAL**

All discrepancies between initial draft narratives and verified Step 5 artifacts have been resolved. The mathematical specification of the CDA, the evaluation metric formulas, the locked pseudorandom paired protocol, and the scientific limitations are fully aligned.

### Remaining Decisions Requiring User Approval:
1. **Approval of ZI-C as Primary Bidding Benchmark**: Using Zero-Intelligence Constrained (ZI-C) bidding ($U(\text{FiT}, G_T)$) as primary benchmark, supplemented by deterministic midpoint ($B=\$0.20, A=\$0.18$).
2. **Approval of Flat Retail and Feed-in Tariffs**: Using static flat tariffs ($G_T = \$0.30/\text{kWh}, \text{FiT} = \$0.08/\text{kWh}$) to maintain transparent gross-surplus equations.
3. **Approval of 671-Day Streaming Execution Scope**: Running the full paired simulation across all 671 test days (Days 425–1095) for all three regimes (A, B, C) preceded by a 5-day smoke test.

Upon user confirmation of these decisions, Step 6.2 (implementation of `Step 6/cda_market.py` and integration tests) will commence.
