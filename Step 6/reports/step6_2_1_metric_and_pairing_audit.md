# Step 6.2.1 Audit Report: Pre-Run Metric Semantics and Paired-Randomness Verification

**Project**: Cyber-Economic Resilience Under Evolving Attacks in Peer-to-Peer Energy Markets  
**Phase**: Step 6.2.1 Pre-Run Audit (Prerequisite to Step 6.3 Full Evaluation)  
**Author**: Antigravity Assistant & Independent Major Project Auditor  
**Date**: October 20, 2026  
**Status**: **AUDIT COMPLETE — ALL INVARIANTS VERIFIED — STOPPING RULE ENFORCED (HOLD STEP 6.3)**

---

## Executive Summary

Before launching the full 671-day Continuous Double Auction (CDA) simulation across Regimes A, B, C, and Clean (Step 6.3), a formal pre-run audit was conducted on the Step 6.2 CDA market implementation and initial 5-day smoke-test outputs. 

This audit addressed two fundamental technical risks:
1. **Conflated Attack-Volume Semantics**: Resolving why the initial smoke-test report indicated $253.97\text{ kWh}$ of "cleared attack volume" in Regime B (ALWAYS_MITIGATE) and $257.72\text{ kWh}$ in Regime C, even though Regime B universally substitutes clean historical fallback telemetry for every interval.
2. **Paired-Randomness Invariance**: Verifying that participant arrival queues and ZI-C valuation draws in `LockedPairingEngine` are strictly paired across regimes, reproducible, and invariant to regime composition, active participant counts, or prosumer role flips.

### Key Audit Findings & Corrections
1. **Root Cause of Regime B Volume**: The legacy metric `cleared_attack_volume` was implemented as a post-hoc query on the ground-truth attack label $y_{i,t}=1$. It reported traded volume during intervals that had been *targeted* by attacks in the benchmark, regardless of whether defensive mitigation substituted clean telemetry. In Regime B, all prosumer orders were formed using clean fallback baselines ($M=1$), yet their trades were misattributed as "cleared attack volume".
2. **Orthogonal Metric Separation**: We decoupled post-hoc cyber metrics into four distinct, mathematically defined quantities:
   - `corrupted_raw_energy_cleared_kWh`: Traded energy directly attributable to corrupted raw telemetry entered into the order book ($y=1 \land M=0$). Under Regime B, this is rigorously **$0.0000\text{ kWh}$** ($100\%$ eliminated).
   - `attack_targeted_interval_traded_energy_kWh`: Total energy traded by prosumers during intervals targeted by attacks ($y=1$), regardless of mitigation status ($253.97\text{ kWh}$ in Regime B, $380.98\text{ kWh}$ in Regime A).
   - `fallback_energy_traded_kWh`: Total matched energy derived from fallback-substituted telemetry ($M=1$). In Regime B, this equals $1,249.21\text{ kWh}$ ($100\%$ of cleared energy).
   - `clean_counterfactual_exposure_kWh`: Traded energy during targeted intervals in the unattacked Clean market baseline ($306.35\text{ kWh}$), establishing the non-attack counterfactual exposure.
3. **Paired-Randomness Hardening**: `LockedPairingEngine` was refactored to generate independent two-dimensional valuation draws per customer ID $\left(u_i, v_i\right) \in [0, 1]^2$. Column 0 provides the buyer bid valuation draw, and Column 1 provides the seller ask valuation draw. Even if customer $i$ switches from Buyer in Regime A to Seller in Regime B due to mitigation, their valuation draws remain fixed, independent, and completely insulated from iteration order, active participant counts, or regime composition.
4. **Stopping Rule Enforced**: The full 671-day experiment (Step 6.3) has **NOT** been launched. All unit tests (14/14 pass) and the 5-day smoke test (10/10 invariants pass) have been executed and verified. The code and artifacts are frozen awaiting review.

---

## 1. Audit of Attack-Volume Classification

### 1.1 Root Cause Analysis

In the Step 6.2 initial implementation, trade records recorded prosumer IDs and checked ground-truth attack labels:
$$\text{Legacy Attack Volume} = \sum_{\tau \in \mathcal{T}} q_\tau \cdot \mathbf{1}_{\{y_{B(\tau)} = 1 \lor y_{S(\tau)} = 1\}}$$
where $\mathcal{T}$ is the set of cleared trades, $q_\tau$ is the cleared trade volume, and $y_{i}$ is the benchmark attack label for customer $i$ in slot $t$.

This formulation conflated three mutually distinct phenomena:
1. **Corrupted Telemetry Entry**: Orders formed from altered, fraudulent meter telemetry ($y=1, M=0$).
2. **Ground-Truth Attack Targeting**: Customer-intervals chosen by the benchmark attacker ($y=1$), independent of whether the market operator detected and mitigated the event.
3. **Fallback-Substituted Operations**: Normal energy traded by a mitigated customer using historical median fallback substitution ($M=1$).

Because Regime B mitigates all intervals ($M_{i,t}=1 \ \forall i,t$), no corrupted telemetry ever entered the order book. Labeling its $253.97\text{ kWh}$ of cleared trades as "attack volume" gave the false impression that defense failed to stop cyberattacks, when in reality it stopped $100\%$ of raw corrupted telemetry and traded legitimate energy under fallback baselines. Similarly, in the Clean counterfactual, evaluating $y=1$ would erroneously claim $306.35\text{ kWh}$ of attacks occurred in a dataset with zero attacks.

### 1.2 Mathematical Formulation of Orthogonal Post-Hoc Metrics

Let $i \in \{1, \dots, N\}$ denote customer index, $t$ denote time interval, $y_{i,t} \in \{0, 1\}$ denote the benchmark attack indicator, and $M_{i,t} \in \{0, 1\}$ denote the mitigation decision. For each prosumer order submitted to the CDA, the telemetry source state is:
- **Corrupted Raw Telemetry**: $y_{i,t} = 1 \land M_{i,t} = 0$ (Attacked, Unmitigated — False Negative or Regime A)
- **Fallback-Substituted Telemetry**: $M_{i,t} = 1$ (Mitigated — True Positive or False Alarm, Regimes B and C)
- **Clean Raw Telemetry**: $y_{i,t} = 0 \land M_{i,t} = 0$ (Unattacked, Unmitigated — True Negative or Clean Counterfactual)

When trade $\tau = (B, S, q_\tau, p_\tau)$ clears between buyer $B$ and seller $S$, trade volume attribution is defined as follows:

#### Metric 1: Corrupted Raw Energy Cleared ($E_{\text{corrupt}}$)
Matched energy directly attributable to unmitigated corrupted raw telemetry:
$$E_{\text{corrupt}} = \sum_{\tau \in \mathcal{T}} q_\tau \cdot \frac{1}{2} \left[ \mathbf{1}_{\{y_{B,t}=1 \land M_{B,t}=0\}} + \mathbf{1}_{\{y_{S,t}=1 \land M_{S,t}=0\}} \right]$$
*Properties*:
- In Clean: $y \equiv 0 \implies E_{\text{corrupt}} = 0$.
- In Regime B: $M \equiv 1 \implies E_{\text{corrupt}} = 0$.
- In Regime A: $M \equiv 0 \implies E_{\text{corrupt}} = \sum_\tau q_\tau \frac{1}{2} [\mathbf{1}_{\{y_B=1\}} + \mathbf{1}_{\{y_S=1\}}]$.
- In Regime C: Non-zero strictly when the detector produces a false negative ($y=1, M=0$).

#### Metric 2: Attack-Targeted Interval Traded Energy ($E_{\text{targeted}}$)
Matched energy cleared by participants whose underlying interval was targeted in the benchmark, regardless of mitigation:
$$E_{\text{targeted}} = \sum_{\tau \in \mathcal{T}} q_\tau \cdot \frac{1}{2} \left[ \mathbf{1}_{\{y_{B,t}=1\}} + \mathbf{1}_{\{y_{S,t}=1\}} \right]$$
*Properties*: Measures the physical market participation volume of targeted prosumers across all regimes.

#### Metric 3: Fallback Energy Traded ($E_{\text{fallback}}$)
Matched energy resulting from orders constructed using fallback-substituted telemetry:
$$E_{\text{fallback}} = \sum_{\tau \in \mathcal{T}} q_\tau \cdot \frac{1}{2} \left[ \mathbf{1}_{\{M_{B,t}=1\}} + \mathbf{1}_{\{M_{S,t}=1\}} \right]$$
*Properties*:
- In Clean and Regime A: $M \equiv 0 \implies E_{\text{fallback}} = 0$.
- In Regime B: $M \equiv 1 \implies E_{\text{fallback}} = \sum_\tau q_\tau = E_{\text{P2P}}$.
- In Regime C: Measures the exact volume of P2P trade executed under fallback baselines.

#### Metric 4: Clean-Counterfactual Baseline Exposure ($E_{\text{clean\_exp}}$)
Matched energy in the unattacked Clean market during intervals that were attacked in the benchmark:
$$E_{\text{clean\_exp}} = \left. \sum_{\tau \in \mathcal{T}_{\text{clean}}} q_\tau \cdot \frac{1}{2} \left[ \mathbf{1}_{\{y_{B,t}=1\}} + \mathbf{1}_{\{y_{S,t}=1\}} \right] \right|_{\text{Clean Market}}$$
*Properties*: Strictly evaluated on the Clean run. Demonstrates that the targeted prosumers normally trade $\approx 306.35\text{ kWh}$ of legitimate energy in the absence of attacks.

### 1.3 Limits of Causal Attribution in Auction Clearing

While order-level attribution is mathematically exact, market clearing in a Continuous Double Auction is non-linear and path-dependent:
1. **Marginal Displacement**: A corrupted bid at price $\$0.28$ might match against an ask that would have otherwise matched against a clean bid at $\$0.26$. The displaced clean buyer is relegated to the retail grid.
2. **Partial Phantom Volume**: If a customer's genuine demand was $1.0\text{ kWh}$ and attack manipulation inflated it to $1.5\text{ kWh}$, attributing all $1.0\text{ kWh}$ of cleared energy as "corrupted" overstates the fraud, while attributing only $0.5\text{ kWh}$ ignores that the priority of the entire order was influenced by the attack.
3. **Attribution Boundary**: Our trade-level attribution credits each side proportionally ($\frac{1}{2}$ per participant). This guarantees that:
   $$\sum \text{attributions} \le E_{\text{P2P}}$$
   and prevents double-counting two-sided trades.

---

## 2. Audit of Paired Randomness

### 2.1 Engine Architecture and Seed Hierarchy

The Continuous Double Auction simulation requires strict variance reduction through common random numbers (CRN). The `LockedPairingEngine` enforces this via a hierarchical seed derivation:

$$\text{Seed}(d, s) = \text{base\_seed} \times 1,000,000 + d \times 100 + s$$
where $d \in [425, 1095]$ is the test day index, $s \in [0, 47]$ is the half-hour slot index, and $\text{base\_seed} = 42$.

Crucially, **the seed depends only on $(d, s)$ and is identical across Regimes A, B, C, and Clean**.

```
Master Seed (42)
   │
   ├── Day d, Slot s Seed: 42*1000000 + d*100 + s
   │      │
   │      ├── Arrival RNG (Seed + 10007)
   │      │      └── Random permutation of customer IDs [1, 3, 4, ..., 300]
   │      │
   │      └── Valuation RNG (Seed + 20011)
   │             └── 2D Uniform Matrix [299, 2]
   │                    ├── Column 0: Buyer Valuation Draw u_i
   │                    └── Column 1: Seller Valuation Draw v_i
```

### 2.2 Invariance Verification Properties

We performed explicit audits and unit tests verifying the following five pairing invariants:

| Property | Implementation Mechanism | Audit Result | Unit Test Status |
| :--- | :--- | :--- | :--- |
| **Arrival Permutations** | Permutation is drawn once over the full fixed cohort of 299 customer IDs using `rng_arrival.permutation(299)`. Inactive participants are filtered *after* permutation. | Bitwise identical arrival sequence across all regimes. | `test_arrival_permutations_paired_across_regimes` [PASS] |
| **Customer Valuations** | Matrix $U \in [0, 1]^{299 \times 2}$ drawn in a single vectorized call. Customer $k$ always indexes row $k$. | Valuations for customer $k$ do not shift if other participants change roles or go inactive. | `test_customer_valuations_paired_across_regimes` [PASS] |
| **Role-Flip Independence** | Buyer valuation uses $u_{k} = U[k, 0]$; Seller valuation uses $v_{k} = U[k, 1]$. | If customer $k$ flips from Buyer in Regime A to Seller in Regime B, their seller valuation is drawn from $v_k$, entirely independent of $u_k$ and unaffected by iteration order. | `test_buyer_to_seller_role_flip_valuation_independence` [PASS] |
| **Active Count Invariance** | Matrix row $k$ maps to Customer ID regardless of whether 10 or 250 prosumers are active. | Zero cross-contamination or phase-shift in the pseudo-random stream. | `test_valuations_do_not_shift_with_active_counts_or_roles` [PASS] |
| **Deterministic Isolation** | Deterministic midpoint benchmark evaluates analytic formulas ($B=\$0.20, A=\$0.18$) without invoking the random number generator. | Random streams remain completely unconsumed and independent. | `test_deterministic_strategy` [PASS] |

All 5 pairing unit tests pass with zero variance.

---

## 3. Reconciled 5-Day Smoke-Test Results

The 5-day smoke test (Test Days 425–429, August 30 – September 3, 2011) was re-executed using the corrected orthogonal metrics.

### 3.1 5-Day Aggregate Comparison Table

| Metric | Clean Baseline | Regime A (Unmitigated) | Regime B (ALWAYS_MITIGATE) | Regime C (Selective $\tau=0.50$) |
| :--- | :---: | :---: | :---: | :---: |
| **P2P Matched Volume (kWh)** | $1,783.63$ | $1,807.56$ | $1,249.21$ | $1,267.06$ |
| **Total Number of Trades** | $14,538$ | $14,420$ | $12,814$ | $12,820$ |
| **Volume-Weighted VWAP ($/kWh)** | $\$0.1809$ | $\$0.1795$ | $\$0.1749$ | $\$0.1739$ |
| **P2P Gross Surplus (AUD)** | $\$392.40$ | $\$397.66$ | $\$274.83$ | $\$278.75$ |
| **Welfare Retention Rate (%)** | $100.00\%$ | $101.34\%$ | $70.04\%$ | $71.04\%$ |
| **Corrupted Raw Energy Cleared (kWh)** | **$0.0000$** | **$380.98$** | **$0.0000$** | **$76.24$** |
| **Attack-Targeted Interval Energy (kWh)** | $306.35$ | $380.98$ | $253.97$ | $257.72$ |
| **Fallback-Substituted Energy (kWh)** | $0.0000$ | $0.0000$ | $1,249.21$ | $1,185.20$ |
| **Clean Baseline Exposure (kWh)** | $306.35$ | $0.0000$ | $0.0000$ | $0.0000$ |
| **Grid Import Cost (AUD)** | $\$4,977.00$ | $\$4,903.62$ | $\$4,996.39$ | $\$4,547.75$ |
| **Grid Export Revenue (AUD)** | $\$172.93$ | $\$191.71$ | $\$153.07$ | $\$177.89$ |
| **Net Grid Settlement (AUD)** | $\$4,804.08$ | $\$4,711.91$ | $\$4,843.33$ | $\$4,369.86$ |

### 3.2 Daily Breakdown of Orthogonal Cyber Metrics

The table below confirms the behavior across non-attacked days (Days 426, 428) versus attacked days (Days 425, 427, 429):

```
+-----+------------+-------------------+-------------------+-------------------+-------------------+
| Day | Date       | Clean Exposure    | Regime A Corrupt  | Regime B Corrupt  | Regime C Corrupt  |
+-----+------------+-------------------+-------------------+-------------------+-------------------+
| 425 | 2011-08-30 | 80.391 kWh        | 116.028 kWh       | 0.000 kWh         | 13.442 kWh        |
| 426 | 2011-08-31 | 0.000 kWh         | 0.000 kWh         | 0.000 kWh         | 0.000 kWh         |
| 427 | 2011-09-01 | 118.701 kWh       | 136.587 kWh       | 0.000 kWh         | 40.468 kWh        |
| 428 | 2011-09-02 | 0.000 kWh         | 0.000 kWh         | 0.000 kWh         | 0.000 kWh         |
| 429 | 2011-09-03 | 107.259 kWh       | 128.364 kWh       | 0.000 kWh         | 22.333 kWh        |
+-----+------------+-------------------+-------------------+-------------------+-------------------+
| SUM | 5 Days     | 306.351 kWh       | 380.978 kWh       | 0.000 kWh         | 76.243 kWh        |
+-----+------------+-------------------+-------------------+-------------------+-------------------+
```

### 3.3 Semantic Interpretation & Defensibility

1. **Regime A (Zero Mitigation)**: $380.98\text{ kWh}$ of corrupted energy cleared in the CDA. This is $74.63\text{ kWh}$ greater than the clean baseline exposure ($306.35\text{ kWh}$), directly reflecting phantom demand/supply injected by the adversary to inflate trading volume.
2. **Regime B (Always Mitigate)**: Corrupted raw energy cleared is **identically $0.0000\text{ kWh}$**. Defensive substitution with historical medians successfully eliminated all raw attack corruption from entering the matching engine. However, because fallback profiles underestimate solar peaks, total market volume dropped by $30\%$, reducing gross surplus from $\$392.40$ to $\$274.83$.
3. **Regime C (Selective Defense, $\tau=0.50$)**: Corrupted raw energy cleared is **$76.24\text{ kWh}$**, representing an **$80.0\%$ reduction** in cleared corrupted energy compared to Regime A. The remaining $76.24\text{ kWh}$ represents false negatives due to detector limits (AUROC $\approx 0.5237$). Regime C achieved $\$278.75$ in gross surplus while lowering net grid settlement costs to $\$4,369.86$.
4. **Prevention of Double Counting**: Economic market surplus ($W_{\text{P2P}} = S_B + S_S$), retail grid energy expenditures, and cyber penalty losses are reported as separate columns. Market surplus is not artificially penalized; cyber impacts are reflected directly through physical telemetry distortions, clearing volume reductions, and grid settlements.

---

## 4. Verification of Smoke-Test Invariants

All 10 mandated checks from `step6_2_smoke_test_verification_audit.csv` passed:

```
[PASS] CHK-01: Population_and_Slots_Coverage -> 960 intervals across 4 regimes
[PASS] CHK-02: Sign_Conventions_and_Epsilon -> All non-negative; total participants exactly 299 across all 960 slots
[PASS] CHK-03: Non_Negative_Trades_No_Overfills -> Max matched volume 31.0850 kWh strictly within bounds
[PASS] CHK-04: Energy_Conservation_Equations -> Max demand error: 1.42e-14 kWh, Max supply error: 1.42e-14 kWh
[PASS] CHK-05: Price_Boundaries_and_Crossing -> Min VWAP: $0.1340, Max VWAP: $0.2877
[PASS] CHK-06: Deterministic_Seed_Repeatability -> Bitwise match confirmed across 192 interval comparisons (diff = 0.0)
[PASS] CHK-07: Quarantined_Labels_Anti_Leakage -> Ground-truth labels passed only to post-hoc reporting block
[PASS] CHK-08: Zero_Trade_Edge_Case_Handling -> 524 zero-trade slots; all correctly set VWAP=$0.19 and Surplus=$0.00
[PASS] CHK-09: Exact_Tariff_Surplus_Linearity -> Max sum error: 0.00e+00 AUD, Max linear error: 8.88e-16 AUD
[PASS] CHK-10: Runtime_and_Memory_Feasibility -> 295.57 ms/day, Peak memory: 1740.42 MB
```

---

## 5. Artifact and Benchmark Preservation Confirmation

All Step 1–5 artifacts and frozen data remain intact and uncommitted. Hashes were verified against original benchmarks:

| Artifact | Location | Expected SHA-256 Hash | Verified Status |
| :--- | :--- | :--- | :---: |
| **Frozen Attacked Dataset** | `data/processed/ausgrid_solar_attacked.parquet` | `176fa03152359472b544f2197427bca92f51127e4c2becad84e31ec72f6ca1b4` | **MATCH** |
| **Frozen Attacked Backup** | `Step 1/data/processed/ausgrid_solar_attacked.parquet` | `176fa03152359472b544f2197427bca92f51127e4c2becad84e31ec72f6ca1b4` | **MATCH** |
| **Detector Checkpoint** | `Step 5/preflight/detector_checkpoint.pt` | `85e68a1b1da058cecf56829279e2af42872656e797581e81170f2f712f9fbbf2` | **MATCH** |
| **Calibrator Artifact** | `Step 5/preflight/probability_calibrator.pkl` | `81f70abbe29e775ea064e5fd4c46858bcb158f0fdd93a2b0014627742ac4a158` | **MATCH** |

### Modified Files in Step 6.2.1 Audit
1. `Step 6/cda_market.py`:
   - Updated `simulate_interval` to accept `mitigation_flags`.
   - Separated post-hoc metrics into `corrupted_raw_energy_cleared_kWh`, `attack_targeted_interval_traded_energy_kWh`, `fallback_energy_traded_kWh`, and `clean_counterfactual_exposure_kWh`.
   - Hardened `LockedPairingEngine` to provide independent 2D valuation draws per customer ID for role-flip invariance.
   - Implemented binary bisect key caching in `CDAOrderBook` for $O(\log K)$ order insertion.
2. `Step 6/tests/test_cda_market.py`:
   - Added unit tests for cross-regime arrival pairing, valuation pairing, active-count invariance, role-flip independence, and orthogonal cyber metric classification. Total tests expanded to 14 (all passing).
3. `Step 6/run_smoke_test.py`:
   - Updated summary aggregation to report the 4 orthogonal metrics.
4. `Step 6/outputs/step6_2_smoke_test_daily_summary.csv`:
   - Recomputed 5-day daily records with the new metric columns.
5. `Step 6/outputs/step6_2_smoke_test_verification_audit.csv`:
   - Recomputed 10 invariant check results with latest timings.

---

## 6. Stopping Rule & Recommendation

**STOPPING RULE STRICTLY ENFORCED**:  
The full 671-day experiment (Step 6.3) has **NOT** been launched. 

The CDA engine is now mathematically reconciled, rigorously audited for paired randomness, and verified against all 10 smoke-test invariants. With runtime performance measured at $\approx 295.6\text{ ms/day}$, the full 671-day evaluation across all 4 regimes is projected to execute in approximately $13.5\text{ minutes}$ on the local GPU workstation.

We submit this audit report and await explicit approval before initiating Step 6.3.
