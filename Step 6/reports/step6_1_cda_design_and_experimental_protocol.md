# Step 6.1 — Continuous Double Auction (CDA) Simulation Design and Experimental Protocol

**Project**: Cyber-Economic Resilience Under Evolving Attacks in Peer-to-Peer Energy Markets  
**Component**: Step 6 — Market Simulation and Cyber-Economic Resilience Evaluation  
**Author**: Antigravity Pair Programmer (Agentic Engineering Pass)  
**Date**: October 2026 (Updated in Step 6.1.1 Consistency Pass)  
**Status**: DESIGN RECONCILED & LOCKED — AWAITING USER APPROVAL PRIOR TO IMPLEMENTATION  
**Handoff Baseline**: Step 5.3 Completed (`READY FOR STEP 6 WITH DOCUMENTED LIMITATIONS`)  
**Associated Artifacts**:
- Assumptions Register: [step6_1_assumptions_register.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/outputs/step6_1_assumptions_register.csv)
- Metric Specification: [step6_1_metric_specification.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/outputs/step6_1_metric_specification.csv)
- Consistency Audit Report: [step6_1_1_design_consistency_audit.md](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/reports/step6_1_1_design_consistency_audit.md)

---

## Executive Summary

Step 6 marks the convergence of the cyber-defense layer (Steps 2–5) with the micro-economic transactive energy layer. In this step, peer-to-peer (P2P) trading dynamics are modeled using a **Continuous Double Auction (CDA)** mechanism. The central scientific inquiry of this major project is:

> *How does cyber-attack telemetry distortion propagate into local energy market clearing, and to what extent does probability-calibrated, economic-aware cyber defense restore market efficiency, price stability, and social welfare without penalizing honest prosumers?*

This document provides the complete, mathematically rigorous architectural blueprint and experimental protocol for Step 6 before code execution begins. In strict compliance with project constraints:
1. **Zero Modification to Historical and Upstream Data**: The frozen Ausgrid benchmark (`data/processed/ausgrid_solar_attacked.parquet`, SHA-256 `176fa0315...`), model checkpoints, calibrator artifacts, and Step 5 decision rules are strictly preserved.
2. **Standardized Production Interface**: Step 6 consumes records directly through `Step5MarketStreamer` across the identical test partition (Days 425–1095, 671 calendar days, 299 prosumers, 9,630,192 customer-intervals).
3. **Explicit Methodological Guardrails**: The weak discrimination of the current reconstruction-based anomaly detector ($\text{AUROC} \approx 0.5237$) is incorporated as an explicit project constraint, demonstrating how high false-positive rates under uncalibrated or selective defense mechanically impact market liquidity and participant economic welfare.
4. **Epistemological Integrity**: We clearly distinguish observed physical load measurements from synthetic market bidding rules, avoiding unwarranted causal assertions regarding real-world market equilibria. $W_{\text{P2P}} = (G_T - \text{FiT}) \cdot E_{\text{P2P}}$ is explicitly defined as a **tariff-based gross-surplus proxy under the modeled assumptions**, not a complete real-world social-welfare measure.

---

## 1. Task 1 — Interface Inspection & Telemetry-to-Order Mapping

### 1.1 Source Files Inspected
The following production components and artifacts were audited to verify the data contract:
- [Step 5/streaming.py](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/streaming.py): Contains `Step5MarketStreamer` and `StreamConfig`.
- [Step 5/economic_decision.py](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/economic_decision.py): Contains mitigation rules (`NEVER_MITIGATE`, `ALWAYS_MITIGATE`, `make_fixed_threshold_decision`, `make_economic_decision`).
- [Step 5/cost_model.py](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/cost_model.py): Contains loss accounting ($C_{\text{FN}}, C_{\text{FP}}, C_{\text{M}}$).
- [Step 5/fallback.py](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/fallback.py): Contains trailing 7-day slot median/mean substitution engine.
- [Step 5/reports/step5_report.md](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/reports/step5_report.md): Validates production throughput (5.92 ms/day, 14,352 records/day).

### 1.2 Data Schema Yielded by `Step5MarketStreamer`
For each day $t \in [425, 1095]$, `Step5MarketStreamer.stream_days()` yields a tuple:
$$(t, \text{date\_str}, \mathcal{D}_t)$$
where $\mathcal{D}_t$ is a Pandas DataFrame containing exactly $N \times S = 299 \times 48 = 14,352$ rows with the following 13 schema fields:

| Field Name | Type | Physical Unit | Description & Semantics | Safe for CDA? |
| :--- | :--- | :--- | :--- | :---: |
| `day_index` | `int64` | Day index | Integer day in range $[425, 1095]$. | Yes |
| `slot_index` | `int64` | Slot index | Half-hour index in range $[0, 47]$. | Yes |
| `customer_id` | `int64` | ID | Unique identifier for prosumer $i \in \{1, \dots, 299\}$. | Yes |
| `raw_GC_kWh` | `float64` | kWh / 30 min | General consumption telemetry (attacked or raw). | Informational |
| `raw_GG_kWh` | `float64` | kWh / 30 min | Gross solar generation telemetry (attacked or raw). | Informational |
| `raw_P_net_kWh` | `float64` | kWh / 30 min | Net load before mitigation: $P_{\text{net}} = \text{GC} - \text{GG}$. | Regime A only |
| `calibrated_p` | `float64` | Probability $[0, 1]$ | Posterior probability of attack $P(y=1 \mid \text{loss})$. | Cyber layer |
| `mitigate` | `bool` | Boolean | Step 5 mitigation decision flag ($1 = \text{fallback}, 0 = \text{pass}$). | Safe |
| `substituted_GC_kWh` | `float64` | kWh / 30 min | Effective GC after Step 5 mitigation decision. | Yes |
| `substituted_GG_kWh` | `float64` | kWh / 30 min | Effective GG after Step 5 mitigation decision. | Yes |
| `substituted_P_net_kWh` | `float64` | kWh / 30 min | **Effective Net Load**: $P_{\text{net}}^{\text{eff}} = \text{GC}^{\text{sub}} - \text{GG}^{\text{sub}}$. | **Primary CDA Signal** |
| `is_attacked_ground_truth` | `int64` | Binary $\{0, 1\}$ | **Ground-truth attack label** from Step 1 benchmark. | **QUARANTINED** |
| `cost_scenario` | `str` | Categorical | Active cost regime (default: `baseline`). | Evaluation |

### 1.3 Physical Units vs. Normalization
- **Strict Finding**: Telemetry yields from `Step5MarketStreamer` are **strictly non-normalized physical energy quantities in kilowatt-hours (kWh) per 30-minute interval**.
- **Transformation Traceability**: The raw Ausgrid 30-minute meter readings were initially converted in Step 1 from raw half-hourly power/energy channels into explicit energy increments. In Step 3, inputs were temporarily z-score normalized to $[0, 1]$ for Autoencoder tensor inference; however, the Step 5 streaming pipeline de-normalizes all predictions and maintains raw and fallback telemetry strictly in physical kilowatt-hours (`kWh`). No scaling factors or unit conversions are required to interpret these values as physical energy.

### 1.4 Fallback Substitution Mechanics
When `mitigate == True`, the prosumer's effective telemetry is substituted by historical baseline values generated by `FallbackEngine`:
$$\text{GC}^{\text{sub}}_{i, t, s} = \widehat{\text{GC}}_{i, s}^{\text{hist}}, \quad \text{GG}^{\text{sub}}_{i, t, s} = \widehat{\text{GG}}_{i, s}^{\text{hist}}$$
where $\widehat{\text{GC}}_{i, s}^{\text{hist}}$ and $\widehat{\text{GG}}_{i, s}^{\text{hist}}$ are derived from the trailing 7-day median for slot $s$.
- **Impact on Net Energy Position**:
  $$P_{\text{net}, i, t, s}^{\text{eff}} = \text{GC}_{i, t, s}^{\text{sub}} - \text{GG}_{i, t, s}^{\text{sub}}$$
  - If a stealth attack injected synthetic solar export ($\text{GG}_{\text{raw}} \gg \text{GC}_{\text{raw}}$), fallback substitution collapses the false export back to seasonal expected generation, preventing the attacker from selling "phantom" energy into the microgrid.
  - Conversely, under a **false alarm** on a high-solar day, substituting the 7-day median suppresses legitimate excess generation, causing the prosumer to offer less green energy than physically available.

### 1.5 Information Quarantine and Anti-Leakage
- **Quarantined Field**: `is_attacked_ground_truth` is strictly isolated from:
  1. The participant role assignment.
  2. The submitted order quantity $Q$.
  3. The bidding/asking price calculation.
  4. The CDA order matching engine.
- **Evaluation Role**: Ground-truth labels are stored in parallel and mapped to order IDs post-clearing. This enables retroactive classification of trades into:
  - *Clean trades* (both buyer and seller telemetry uncorrupted).
  - *Attacked trades* (buyer or seller telemetry corrupted by FDI attack).
  - *Mitigated trades* (cleared based on fallback substituted volumes).

### 1.6 Physical Telemetry vs. Market Orders
> [!IMPORTANT]
> **Defensible Modeling Disturbance**: The Ausgrid dataset contains meter telemetry representing *physical energy import/export measurements*, **not market orders or transaction bids**. 
> 
> No historical P2P market operated across these 299 homes in 2011–2014. Therefore, any mapping from $P_{\text{net}}$ to bid/ask price and quantity is an **experimental simulation construct**. In Section 2, we establish an axiomatic, non-speculative economic formulation based on rational tariff bounds and Zero-Intelligence Constrained (ZI-C) behavior.

---

## 2. Task 2 — Continuous Double Auction (CDA) Specification

### 2.1 Participant Roles
In each 30-minute market interval $s \in [0, 47]$ of test day $t$, each prosumer $i \in \{1, \dots, 299\}$ is deterministically assigned a market role based on their effective physical net position:

$$\text{Role}_{i, t, s} = \begin{cases}
\text{BUYER} & \text{if } P_{\text{net}, i, t, s}^{\text{eff}} > \epsilon \\
\text{SELLER} & \text{if } P_{\text{net}, i, t, s}^{\text{eff}} < -\epsilon \\
\text{INACTIVE} & \text{if } |P_{\text{net}, i, t, s}^{\text{eff}}| \le \epsilon
\end{cases}$$

where $\epsilon = 10^{-4}\text{ kWh}$ ($0.1\text{ Wh}$) eliminates numerical floating-point noise.

### 2.2 Order Quantity Derivation
- **Buyers**: Demand volume $Q_{i, t, s}^B = P_{\text{net}, i, t, s}^{\text{eff}} > 0$.
- **Sellers**: Available surplus generation $Q_{j, t, s}^S = |P_{\text{net}, j, t, s}^{\text{eff}}| > 0$.
- **Inelastic Volume Assumption (ASM-01, ASM-02)**: We assume households submit their full net energy position as an inelastic market order ($Q = |P_{\text{net}}|$) for the half-hour. This reflects standard microgrid operating paradigms where local generation has zero marginal cost (solar PV) and residential appliances have inelastic demand within a 30-minute settlement period.

### 2.3 Rational Price Bounds and Bidding Strategies

#### 2.3.1 Grid Tariff Constraints (Rationality Boundary)
In a dual-settlement grid-connected microgrid, rational prosumers will only participate in P2P trade if it improves upon their default retail grid alternative:
- **Default Grid Import Tariff ($G_T$)**: The cost to buy from the main grid. We set $G_T = \$0.3000/\text{kWh}$ (reflective of standard Ausgrid flat domestic retail tariffs).
- **Default Feed-in Tariff ($\text{FiT}$)**: The compensation for exporting solar to the main grid. We set $\text{FiT} = \$0.0800/\text{kWh}$ (historical Australian solar feed-in tariff baseline).

Rationality dictates that:
$$\text{FiT} \le \text{Ask Price } A_j \le \text{Bid Price } B_i \le G_T$$
- A buyer will never bid $B_i > G_T$, because purchasing from the utility grid costs only $G_T$.
- A seller will never ask $A_j < \text{FiT}$, because selling to the utility grid yields $\text{FiT}$ with zero counterparty risk.

#### 2.3.2 Primary Bidding Behavior: Zero-Intelligence Constrained (ZI-C)
To evaluate the market mechanism and cybersecurity effects without assuming complex, uncalibrated behavioral psychology, the primary simulation protocol employs **Zero-Intelligence Constrained (ZI-C)** agents (Gode & Sunder, 1993):
$$B_i = \text{FiT} + u_{i, t, s} \cdot (G_T - \text{FiT}) = 0.08 + 0.22 \cdot u_{i, t, s} \quad [\$/\text{kWh}]$$
$$A_j = \text{FiT} + v_{j, t, s} \cdot (G_T - \text{FiT}) = 0.08 + 0.22 \cdot v_{j, t, s} \quad [\$/\text{kWh}]$$
where $u_{i, t, s}, v_{j, t, s} \sim \mathcal{U}(0, 1)$ are drawn from the locked pseudorandom stream.
*Justification*: ZI-C agents generate random bids subject strictly to budget constraints. In experimental economics, ZI-C demonstrates that allocative efficiency in double auctions is an inherent structural property of the auction institution itself, rather than strategic optimization.

#### 2.3.3 Sensitivity Benchmark: Deterministic Midpoint Bidding
To isolate price volatility caused by random order sampling from price shifts caused by cyber attacks, we specify a secondary deterministic benchmark:
$$B_i^{\text{det}} = G_T - \delta = \$0.20/\text{kWh}, \quad A_j^{\text{det}} = \text{FiT} + \delta = \$0.18/\text{kWh}$$
yielding a steady nominal midpoint of $\$0.19/\text{kWh}$.

### 2.4 Order Arrival and Matching Mechanism

#### 2.4.1 Discrete Event Simulation of Continuous Trading
Although telemetry is captured in discrete 30-minute intervals, trading within the interval is executed via a **Continuous Double Auction (CDA)**:
1. At the opening of interval $(t, s)$, all active prosumers generate an initial order $O = (\text{prosumer\_id}, \text{role}, Q, P, \tau_{\text{arr}})$.
2. Order arrival timestamps $\tau_{\text{arr}}$ are generated via a homogeneous Poisson process or pseudo-random permutation over the interval duration $[0, 1800\text{ seconds}]$.
3. Orders arrive sequentially at the centralized microgrid matching engine.

#### 2.4.2 Order Book Structure & Price-Time Priority
The matching engine maintains two priority queues:
- **Bids (Buyer Queue)**: Sorted descending by bid price $B$; ties broken by earliest arrival time $\tau_{\text{arr}}$ (Price-Time Priority).
- **Asks (Seller Queue)**: Sorted ascending by ask price $A$; ties broken by earliest arrival time $\tau_{\text{arr}}$ (Price-Time Priority).

#### 2.4.3 Matching and Execution Invariants
Upon arrival of an incoming order $O_{\text{in}}$:
- If $O_{\text{in}}$ is a **Bid** with price $B_{\text{in}}$:
  - Check the standing sell book. If the best standing ask $A^* \le B_{\text{in}}$, a trade is triggered.
  - The match proceeds against $A^*$ up to $\min(Q_{\text{in}}, Q_{A^*})$.
- If $O_{\text{in}}$ is an **Ask** with price $A_{\text{in}}$:
  - Check the standing buy book. If the best standing bid $B^* \ge A_{\text{in}}$, a trade is triggered.
  - The match proceeds against $B^*$ up to $\min(Q_{\text{in}}, Q_{B^*})$.

#### 2.4.4 Partial Fills
- If the matched quantity $Q_{\text{trade}} < Q_{\text{standing}}$, the standing order's remaining quantity is updated to $Q_{\text{standing}} - Q_{\text{trade}}$ and retains its price-time priority in the book.
- If $Q_{\text{trade}} < Q_{\text{in}}$, the trade executes, and the incoming order searches for further compatible counter-orders. Any residual quantity is placed into the book as a standing order.

### 2.5 Market Clearing and Settlement Price Rule

#### 2.5.1 Primary Rule: $k$-Double Auction Midpoint Rule ($k=0.5$)
When an incoming order crosses with a standing order, the transaction clearing price $P^*$ is determined by the $k$-double auction pricing rule with $k = 0.5$ (midpoint):
$$P^* = \frac{B^* + A^*}{2}$$
where $B^*$ is the bid price and $A^*$ is the ask price of the matched pair.
- **Fairness Property**: The midpoint rule divides the immediate bilateral gains from trade equally between buyer and seller ($B^* - P^* = P^* - A^* = \frac{B^* - A^*}{2}$).

#### 2.5.2 Sensitivity Rule: Standing-Order Price Rule
As an algorithmic robustness check, setting $P^* = P_{\text{standing}}$ (the price of the resting order in the book, equivalent to maker pricing) will be evaluated as a secondary sensitivity experiment.

### 2.6 Dual-Settlement Balancing and Residual Grid Settlement
Microgrids cannot permit physical deficits or unabsorbed surplus. Unmatched volume at the close of each 30-minute CDA window is automatically cleared with the central distribution grid:
1. **Unmet Buyer Demand ($E_{\text{unmet}, B}$)**:
   $$E_{\text{unmet}, B, i} = Q_i^B - \sum_{k \in \text{Trades}_i} Q_k$$
   Settled via standard grid import at retail tariff $G_T = \$0.3000/\text{kWh}$.
2. **Unmatched Seller Supply ($E_{\text{unmatched}, S}$)**:
   $$E_{\text{unmatched}, S, j} = Q_j^S - \sum_{k \in \text{Trades}_j} Q_k$$
   Settled via standard grid export at feed-in tariff $\text{FiT} = \$0.0800/\text{kWh}$.

### 2.7 Trading Boundaries and Interval Independence
- **Strict Half-Hour Independence (ASM-09)**: All orders submitted in interval $s$ expire at the end of interval $s$. No orders, bids, or energy carry over to interval $s+1$.
- **Zero Storage Assumption**: In accordance with the Ausgrid dataset profile, prosumers do not possess physical batteries. Energy must be produced, traded, or absorbed instantaneously.

### 2.8 Energy Conservation Invariants
To guarantee physical validity, the simulation engine must strictly enforce the following mathematical conservation laws at every interval $s$:

$$\sum_{k \in \text{Trades}} Q_k \le \min\left(\sum_{i \in \text{Buyers}} Q_i^B, \sum_{j \in \text{Sellers}} Q_j^S\right)$$

$$\sum_{k \in \text{Trades}} Q_{k, i} \le Q_i^B \quad \forall i \in \text{Buyers}$$

$$\sum_{k \in \text{Trades}} Q_{k, j} \le Q_j^S \quad \forall j \in \text{Sellers}$$

$$E_{\text{P2P}} + E_{\text{unmet}, B} = \sum_{i \in \text{Buyers}} Q_i^B$$

$$E_{\text{P2P}} + E_{\text{unmatched}, S} = \sum_{j \in \text{Sellers}} Q_j^S$$

Violation of any of these invariants triggers an immediate assertion failure in the test suite.

### 2.9 Locked Paired Simulation Protocol (Repeatability & Anti-Confounding)
To ensure that differences in market outcomes across Regimes A, B, C, and Clean are **strictly attributable to telemetry and mitigation** rather than random Monte Carlo variations:
1. **Order Arrival Sequence Locking**:
   For interval $(t, s)$, the arrival timestamps $\tau_{\text{arr}, i}$ or arrival permutation $\pi(t, s)$ of prosumers $i \in \{1, \dots, 299\}$ are generated using:
   $$\text{Seed}_{\text{arrival}}(t, s) = \text{BaseSeed} + t \times 10^5 + s \times 10^3$$
   Prosumer $i$'s arrival rank in the queue is bitwise identical across all regimes.
2. **Bidding Price Valuation Locking**:
   For prosumer $i$ in interval $(t, s)$, the random uniform offsets $u_{i, t, s}$ and $v_{i, t, s}$ used for ZI-C pricing are generated using:
   $$\text{Seed}_{\text{price}}(t, s, i) = \text{BaseSeed} + t \times 10^5 + s \times 10^3 + i$$
   If prosumer $i$ is a buyer in both Regime A and Regime C, they submit the exact same bid price $B_i$. Any divergence in execution or clearing price is caused solely by differences in order volume $Q$ or market composition induced by cyber attacks or fallback mitigation!

---

## 3. Task 3 — Evaluation Metrics Specification

The evaluation protocol defines 20 formal metrics across 6 operational categories, fully enumerated in [step6_1_metric_specification.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/outputs/step6_1_metric_specification.csv).

```
+-----------------------------------------------------------------------------------------------------------------------+
|                                              STEP 6 EVALUATION TAXONOMY                                               |
+-----------------------------------------------------------------------------------------------------------------------+
| 1. Market Volume        | Matched P2P Volume (E_p2p), Unmet Demand, Unmatched Supply, Match Rate, Participation Rate  |
| 2. Market Pricing       | Volume-Weighted Average Price (VWAP), Price Spread Divergence (Delta_P)                     |
| 3. Economic Welfare     | Buyer Surplus (S_B), Seller Surplus (S_S), Gross Tariff Surplus Proxy, Welfare Retention    |
| 4. Equity & Dist.       | Gini Coefficient of Savings, Participant-Level Delta-Bill Distributions                     |
| 5. Grid Interaction     | Net Grid Import, Grid Energy Divergence (Delta_E_grid), Grid Balancing Cost                 |
| 6. Cyber-Resilience     | Cleared Attack Volume, Mitigation Rate, Realized Cyber Cost, Net Resilience Composite       |
+-----------------------------------------------------------------------------------------------------------------------+
```

### 3.1 Market Volume Metrics
1. **Matched P2P Energy Volume ($E_{\text{P2P}}$)**:
   $$E_{\text{P2P}} = \sum_{k \in \text{Trades}} Q_k \quad [\text{kWh}]$$
   *Edge Case*: $E_{\text{P2P}} = 0$ if no compatible bids/asks exist.
2. **Unmet Buyer Demand ($E_{\text{unmet}, B}$)**:
   $$E_{\text{unmet}, B} = \sum_{i \in \text{Buyers}} Q_i^B - E_{\text{P2P}} \quad [\text{kWh}]$$
3. **Unmatched Seller Supply ($E_{\text{unmatched}, S}$)**:
   $$E_{\text{unmatched}, S} = \sum_{j \in \text{Sellers}} Q_j^S - E_{\text{P2P}} \quad [\text{kWh}]$$
4. **Market Match Rate ($\text{MR}$)**:
   $$\text{MR} = \frac{E_{\text{P2P}}}{\min\left(\sum Q_i^B, \sum Q_j^S\right)} \times 100\%$$
   *Edge Case*: If $\min\left(\sum Q_i^B, \sum Q_j^S\right) = 0$, $\text{MR} = 0.0\%$.

### 3.2 Pricing & Allocative Efficiency Metrics
5. **Volume-Weighted Average Price ($\text{VWAP}$)**:
   $$\text{VWAP} = \frac{\sum_{k \in \text{Trades}} (P_k^* \cdot Q_k)}{E_{\text{P2P}}} \quad [\$/\text{kWh}]$$
   *Edge Case*: If $E_{\text{P2P}} = 0$, $\text{VWAP}$ is undefined; reported as nominal midpoint $\frac{G_T + \text{FiT}}{2} = \$0.1900/\text{kWh}$.
6. **Price Spread Divergence ($\Delta P$)**:
   $$\Delta P_{\text{regime}} = \text{VWAP}_{\text{regime}} - \text{VWAP}_{\text{clean}} \quad [\$/\text{kWh}]$$
   Measures market price distortion induced by unmitigated FDI attacks or excessive mitigation fallback.

### 3.3 Economic Surplus & Gross Tariff-Surplus Proxy
7. **Buyer Surplus ($S_B$)**:
   $$S_B = \sum_{k \in \text{Trades}} (G_T - P_k^*) \cdot Q_k \quad [\$]$$
   Measures total monetary savings of buyers purchasing via P2P rather than utility grid.
8. **Seller Surplus ($S_S$)**:
   $$S_S = \sum_{k \in \text{Trades}} (P_k^* - \text{FiT}) \cdot Q_k \quad [\$]$$
   Measures total additional revenue of sellers exporting via P2P rather than utility grid.
9. **Gross Tariff-Surplus Proxy ($W_{\text{P2P}}$)**:
   $$W_{\text{P2P}} = S_B + S_S = \sum_{k \in \text{Trades}} (G_T - \text{FiT}) \cdot Q_k = (G_T - \text{FiT}) \cdot E_{\text{P2P}} \quad [\$]$$
   > [!NOTE]
   > **Methodological Interpretation**: Under flat grid tariffs ($G_T = \$0.30, \text{FiT} = \$0.08$), $W_{\text{P2P}} = \$0.22 \cdot E_{\text{P2P}}$ represents a **tariff-based gross-surplus proxy under the modeled assumptions**, not a complete real-world social-welfare measure. It quantifies the gross bilateral economic arbitrage captured by microgrid participants relative to the utility default tariff. It does not account for grid infrastructure costs, line losses, or network service charges.
10. **Welfare Retention Rate ($\text{WRR}$)**:
    $$\text{WRR}_{\text{regime}} = \frac{W_{\text{P2P, regime}}}{W_{\text{P2P, clean}}} \times 100\%$$
    Measures percentage of optimal clean-market gross tariff surplus preserved under attack and defense.

### 3.4 Equity & Distributional Metrics
11. **Individual Bill Savings ($\Delta \text{Bill}_i$)**:
    $$\Delta \text{Bill}_i = \text{Bill}_{i}^{\text{grid-only}} - \text{Bill}_{i}^{\text{P2P}}$$
    where:
    $$\text{Bill}_i^{\text{grid-only}} = Q_i^B \cdot G_T - Q_i^S \cdot \text{FiT}$$
    $$\text{Bill}_i^{\text{P2P}} = \left(E_{\text{unmet}, B, i} \cdot G_T + \sum_{k \in \text{Trades}_i^B} P_k^* Q_k\right) - \left(E_{\text{unmatched}, S, i} \cdot \text{FiT} + \sum_{k \in \text{Trades}_i^S} P_k^* Q_k\right)$$
12. **Gini Coefficient of Savings ($G_{\text{savings}}$)**:
    $$G_{\text{savings}} = \frac{\sum_{i=1}^N \sum_{j=1}^N |\Delta \text{Bill}_i - \Delta \text{Bill}_j|}{2 N \sum_{i=1}^N \Delta \text{Bill}_i}$$
    Measures whether economic benefits of P2P trading accrue equitably or are concentrated among high-generation prosumers.

### 3.5 Grid Interaction & Physical Divergence Metrics
13. **Net Grid Energy Divergence ($\Delta E_{\text{grid}}$)**:
    $$\Delta E_{\text{grid}}(t) = \sum_{s=0}^{47} \left| E_{\text{grid}, \text{regime}}(t, s) - E_{\text{grid}, \text{clean}}(t, s) \right| \quad [\text{kWh}]$$
    Measures physical imbalance forced onto the main utility grid due to cyber-telemetry corruption or false mitigation.

### 3.6 Cybersecurity & Composite Resilience Metrics
14. **Cleared Attack Volume ($Q_{\text{attack\_cleared}}$)**:
    $$Q_{\text{attack\_cleared}} = \sum_{k \in \text{Trades} \mid \text{corrupted}(k)} Q_k \quad [\text{kWh}]$$
    Directly quantifies false energy traded due to unmitigated cyber attacks.
15. **Realized Cyber Defense Cost ($\text{Cost}_{\text{cyber}}$)**:
    $$\text{Cost}_{\text{cyber}} = \text{FN} \cdot C_{\text{FN}} + \text{FP} \cdot C_{\text{FP}} + N_{\text{mit}} \cdot C_{\text{M}} \quad [\$]$$
    Evaluated using Step 5 baseline unit costs ($C_{\text{FN}} = \$0.50, C_{\text{FP}} = \$0.10, C_{\text{M}} = \$0.01$).
16. **Net Cyber-Economic Resilience Index ($\mathcal{R}_{\text{net}}$)**:
    $$\mathcal{R}_{\text{net}} = W_{\text{P2P}} - \text{Cost}_{\text{cyber}} \quad [\$]$$
    *Exploratory Composite Metric*: Integrates micro-economic market creation against cybersecurity operational loss. Reported strictly alongside its additive components to avoid conflating IT costs with market gains.

---

## 4. Task 4 — Experimental Comparison Protocol

### 4.1 Paired Three-Regime Design
All evaluations are conducted as a **strictly paired cohort experiment** across the 671 test days (Days 425–1095) for all 299 prosumers:

```
                                      +---------------------------------------------+
                                      |           FROZEN TEST BENCHMARK             |
                                      |   Days 425-1095 (671 Days, 299 Prosumers)   |
                                      |      9,630,192 Customer-Intervals           |
                                      +---------------------------------------------+
                                                             |
                     +---------------------------------------+---------------------------------------+
                     |                                       |                                       |
                     v                                       v                                       v
         +-----------------------+               +-----------------------+               +-----------------------+
         |       REGIME A        |               |       REGIME B        |               |       REGIME C        |
         |      Unmitigated      |               |    Maximum Defense    |               |   Selective Defense   |
         |    (NEVER_MITIGATE)   |               |   (ALWAYS_MITIGATE)   |               |     (Fixed tau=0.5)   |
         |  Mitigation Rate: 0%  |               | Mitigation Rate: 100% |               | Mitigation: 41.9258%  |
         +-----------------------+               +-----------------------+               +-----------------------+
                     |                                       |                                       |
                     +---------------------------------------+---------------------------------------+
                                                             |
                                                             v
                                             +-------------------------------+
                                             |       P2P CDA SIMULATOR       |
                                             |   Locked Deterministic Seeds  |
                                             |   Identical Tariff Bounds     |
                                             |   Midpoint k-Double Auction   |
                                             +-------------------------------+
                                                             |
                                                             v
                                             +-------------------------------+
                                             |     EVALUATION & METRICS      |
                                             |   Welfare, Prices, Volume,    |
                                             |  Cyber Cost, Net Resilience   |
                                             +-------------------------------+
```

1. **Regime A — Unmitigated (`NEVER_MITIGATE`)**:
   - Telemetry fed to CDA is raw attacked load ($P_{\text{net}}^{\text{raw}}$).
   - Mitigation rate: $0.0\%$. Simulates complete cybersecurity absence or detector failure.
2. **Regime B — Maximum Defense (`ALWAYS_MITIGATE`)**:
   - Telemetry fed to CDA is 100% fallback substituted ($\widehat{P}_{\text{net}}^{\text{hist}}$).
   - Mitigation rate: $100.0\%$. Eliminates all cyber attacks, but incurs maximum false suppression of genuine solar surpluses.
3. **Regime C — Selective Defense (`FIXED_TAU`, $\tau = 0.50$)**:
   - Telemetry fed to CDA is mitigated whenever calibrated attack probability $P(y=1) \ge 0.50$ from the Step 5 balanced calibrator.
   - **Verified Policy Metrics**:
     - Calibrator Artifact: `Step 5/preflight/interval_calibrator.pkl` (SHA-256: `52ec0950bf0faf94c931bce74cdd450cbdd0aa88e78ce88b0439daef3f886821`)
     - Comparison Operator: `>=` (`p_attack >= 0.50`)
     - Mitigate Count: $4,037,535$ ($41.9257996\% \approx 41.93\%$)
     - Allow Count: $5,592,657$ ($58.0742004\% \approx 58.07\%$)
     - True Positives (TP): $181,721$
     - False Positives (FP): $3,855,814$
     - True Negatives (TN): $5,370,051$
     - False Negatives (FN): $222,606$
     - Recall: $44.944068\%$
     - Precision: $4.500791\%$
     - False Positive Rate (FPR): $41.793523\%$
     - F1 Score: $8.182199\%$
4. **Counterfactual Reference — Clean Baseline (`CLEAN_GROUND_TRUTH`)**:
   - Executed strictly in parallel using clean, unmanipulated Ausgrid telemetry.
   - Provides the 100% benchmark for Welfare Retention Rate and Grid Energy Divergence.

### 4.2 Aggregation and Statistical Uncertainty
Outcomes will be generated at three distinct hierarchical granularities:
1. **Interval-Level (30-minute)**: $N = 32,208$ intervals. Yields empirical distributions of clearing prices, match rates, and instantaneous surplus.
2. **Daily-Level**: $N = 671$ test days. Tracks seasonal solar progression (winter vs summer) and multi-day attack burst impacts.
3. **Period-Level Summary**: Entire 671-day test horizon. Reports aggregate social welfare, total cyber costs, and net resilience index.
- **Uncertainty Quantification**: For each metric, report mean, standard deviation, median, 5th percentile, and 95th percentile across the 671 days. Paired differences ($\Delta = M_{\text{Regime C}} - M_{\text{Regime A}}$) will be evaluated using two-sided Wilcoxon signed-rank tests ($\alpha = 0.01$).

### 4.3 Mandatory Sensitivity Analyses
To prevent over-claiming based on arbitrary parameter choices, the following sensitivity experiments are formally incorporated:
- **Pricing Parameter Sensitivity**:
  - Sweep Retail Tariff $G_T \in [\$0.25, \$0.30, \$0.35]/\text{kWh}$.
  - Sweep Feed-in Tariff $\text{FiT} \in [\$0.05, \$0.08, \$0.12]/\text{kWh}$.
- **Bidding Strategy Sensitivity**:
  - Compare ZI-C Random Bidding vs. Deterministic Midpoint Bidding ($P^* = \$0.19/\text{kWh}$) vs. Asymmetric Surplus Sharing ($k = 0.25, 0.75$).
- **Matching Rule Sensitivity**:
  - Compare Midpoint Clearing ($k=0.5$) vs Standing-Order Clearing (Maker Pricing).
- **Market Liquidity / Participation Sensitivity**:
  - Test participant participation rates: 25%, 50%, 75%, 100% of the 299 prosumers submitting orders.

---

## 5. Task 5 — Scientific and Implementation Risk Audit

### 5.1 Weak Detector Discrimination and its Economic Consequences
- **The Core Constraint**: Step 4 and Step 5 audits established that the autoencoder reconstruction error yields an $\text{AUROC} \approx 0.5237$ on the test cohort.
- **Authoritative Ground-Truth Prevalence**:
  - Test partition (Days 425–1095, 299 customers) contains exactly $9,630,192$ customer-intervals.
  - Exactly **$404,327$ intervals are ground-truth attacks**, establishing a test attack prevalence of **$4.198535\%$** (~4.20%, not 2%).
  - Clean intervals count: $9,225,865$ ($95.801465\%$).
- **The Market Implication**:
  - In Regime C ($\tau = 0.50$), the detector triggers mitigation on **$4,037,535$ intervals** ($41.93\%$).
  - Of these mitigations, **$3,855,814$ are false alarms** ($\text{FP} / (\text{TP} + \text{FP}) = 95.499217\%$).
  - **Empirical Hypothesis to Test (Not Assume)**: Does selective defense preserve higher market welfare than unmitigated trading? While false mitigation suppresses genuine solar exports on clear days, it also suppresses fraudulent bids on attacked days. Step 6 will empirically quantify which effect dominates across different market regimes.

### 5.2 Decoupling Cyber Costs from Market Welfare (Preventing Double Counting)
- In Step 5, operational loss was evaluated using abstract penalty units:
  $$L = \text{FN} \cdot C_{\text{FN}} + \text{FP} \cdot C_{\text{FP}} + N_{\text{mit}} \cdot C_{\text{M}}$$
  where $C_{\text{FP}} = \$0.10$ was a heuristic penalty for false alarm disruption.
- In Step 6, the CDA simulation directly measures the **actual, realized economic surplus lost by a false alarm**:
  $$\text{Loss}_{\text{realized}}^{\text{FP}} = W_{\text{P2P}}(\text{Clean}) - W_{\text{P2P}}(\text{Mitigated})$$
- **Mandatory Guardrail**: The abstract Step 5 $C_{\text{FP}}$ penalty and the CDA surplus loss must **never be summed together** in the same metric. In [step6_1_metric_specification.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/outputs/step6_1_metric_specification.csv), $\text{Cost}_{\text{cyber}}$ reports the operational IT/security penalty, while $W_{\text{P2P}}$ reports microgrid market gains. The composite metric $\mathcal{R}_{\text{net}}$ accounts for both without overlapping terms.

### 5.3 Physical Limits of Interpreting Net Load as Market Orders
- The simulation assumes that any customer with $P_{\text{net}} < 0$ can export that entire volume to their neighbors via the distribution feeder.
- **Physical Caveat**: In actual low-voltage (LV) distribution networks, high simultaneous solar feed-in causes voltage rise, phase unbalance, and transformer thermal overload. Without power-flow constraints (AC-OPF), the CDA represents an *unconstrained economic dispatch upper bound*. This must be documented in the thesis as a structural scope limitation.

### 5.4 Temporal Alignment and Missing Data Risks
- **Verification**: The Step 5 streaming pipeline enforces strict calendar alignment. All 299 prosumers have exactly 48 records per day. If a customer-interval has missing telemetry, `Step5MarketStreamer` substitutes zeros or historical slot averages before yielding to the CDA.
- **Sign Conventions**:
  $$\text{GC} \ge 0, \quad \text{GG} \ge 0, \quad P_{\text{net}} = \text{GC} - \text{GG}$$
  - $P_{\text{net}} > 0 \implies \text{Net Importer (Buyer)}$
  - $P_{\text{net}} < 0 \implies \text{Net Exporter (Seller)}$
  Any deviation in this sign convention in code will immediately flip buyers into sellers, corrupting the auction. Comprehensive unit tests must assert this invariant.

---

## 6. Assumptions Register Summary

The 12 formal assumptions governing the Step 6 CDA simulation are cataloged in [step6_1_assumptions_register.csv](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%206/outputs/step6_1_assumptions_register.csv). Below is an overview of the most critical structural assumptions:

| ID | Domain | Assumption Name | Engineering Summary | Threat to Validity / Guardrail |
| :--- | :--- | :--- | :--- | :--- |
| **ASM-01** | Order Derivation | Full Net Volume Trading | Prosumers offer 100% of $Q = \|P_{\text{net}}\|$ to P2P market. | Assumes zero home battery storage; tests theoretical maximum liquidity. |
| **ASM-02** | Order Derivation | Inelastic Demand/Supply | Orders do not vary with intra-half-hour price fluctuations. | Reflects non-deferrable residential load and solar physics. |
| **ASM-03** | Price Bounds | Rational Tariff Bounds | Bids/asks bounded within $[\text{FiT}, G_T] = [\$0.08, \$0.30]/\text{kWh}$. | Strict individual rationality constraint vs default grid baseline. |
| **ASM-04** | Bidding | ZI-C Random Bidding | Orders drawn uniformly $B_i, A_j \sim \mathcal{U}(\text{FiT}, G_T)$. | Actual bids are unavailable in Ausgrid; ZI-C is an explicit simulation model. |
| **ASM-05** | CDA Mechanics | Price-Time Priority & Locked Pairing | Orders matched continuously; arrival ranks and valuations locked across regimes. | Eliminates Monte Carlo confounding across Regimes A, B, C, and Clean. |
| **ASM-06** | CDA Mechanics | Midpoint Clearing ($k=0.5$) | Executing trade price set at $P^* = (B^* + A^*)/2$. | Fair bilateral division; maker pricing evaluated in sensitivity analysis. |
| **ASM-07** | CDA Mechanics | Partial Fills Permitted | Orders can partially execute; residuals remain in book. | Mandatory to prevent integer volume mismatches in energy trading. |
| **ASM-08** | Grid Balancing | Dual-Settlement Balancing | Residual imbalances cleared via main grid at $G_T$ or $\text{FiT}$. | Distribution network constraints (AC power flow, voltage) not modeled. |
| **ASM-09** | Session | Strict Interval Independence | Sessions clear every 30 minutes; zero inter-interval order carryover. | Conforms to Australian National Electricity Market (NEM) 30-min settlement. |
| **ASM-10** | Accounting | Cyber Cost / Welfare Decoupling | Step 5 IT penalties reported separately from CDA market surplus. | $W_{\text{P2P}}$ is a tariff gross-surplus proxy; avoids double-counting IT costs. |
| **ASM-11** | Counterfactual | Clean Reference Isolation | Clean data processed strictly post-hoc as an evaluation baseline. | Prevents information leakage into real-time auction matching. |
| **ASM-12** | Mitigation | Historical Fallback Hypothesis | Mitigated orders use trailing 7-day slot median telemetry. | Welfare impact is an empirical hypothesis to be tested across regimes. |

---

## 7. Audit Trail & Step 6.1.1 Revisions

The following revisions were executed during the Step 6.1.1 design consistency audit:
1. **Reconciliation of Policy A (Fixed $\tau = 0.50$) Mitigation Counts**: Corrected mitigation count from $3,863,165$ ($40.1\%$) to verified $4,037,535$ ($41.9258\%$). Root cause identified: initial text approximated false positive count ($3.86\text{M}$) as total mitigations.
2. **Reconciliation of Test Partition Ground-Truth Attack Prevalence**: Corrected from "~2%" to verified $404,327$ attacks out of $9,630,192$ intervals ($4.198535\% \approx 4.20\%$).
3. **Tightening of Economic Interpretation**: Explicitly redefined $W_{\text{P2P}} = (G_T - \text{FiT}) \cdot E_{\text{P2P}}$ as a tariff-based gross-surplus proxy rather than a complete real-world social welfare metric. Added explicit documentation of unmodeled distribution network constraints and synthetic bidding assumptions.
4. **Specification of Locked Paired Protocol**: Formalized deterministic seeding rules ($\text{Seed}_{\text{arrival}}$ and $\text{Seed}_{\text{price}}$) ensuring identical prosumer arrival ranks and price valuations across all regimes.
5. **Decoupled Cyber Accounting**: Reasserted the strict separation of Step 5 IT penalties ($C_{\text{FP}}, C_{\text{FN}}$) from CDA market trade surplus to prevent double-counting.

---

## 8. Unresolved Questions & Decisions for User Approval

Before proceeding to the implementation of the CDA simulator (Step 6.2), the following three design decisions are submitted to the user for formal approval:

1. **Approval of ZI-C as Primary Bidding Benchmark**:
   - *Proposal*: Use Zero-Intelligence Constrained (ZI-C) bidding ($U(\text{FiT}, G_T)$) as the primary auction benchmark, paired with a Deterministic Midpoint check ($B = \$0.20, A = \$0.18$).
   - *Rationale*: Avoids inventing complex, speculative reinforcement learning agents for prosumers whose real preferences cannot be verified from Ausgrid load profiles.
2. **Approval of Flat Retail and Feed-in Tariffs**:
   - *Proposal*: Adopt static flat tariffs of $G_T = \$0.30/\text{kWh}$ and $\text{FiT} = \$0.08/\text{kWh}$.
   - *Alternative*: Implement a 3-tier Time-of-Use (ToU) tariff (Peak $\$0.45$, Shoulder $\$0.28$, Off-Peak $\$0.16$).
   - *Recommendation*: Flat tariffs yield clean, mathematically transparent surplus equations ($W_{\text{P2P}} = \$0.22 \cdot E_{\text{P2P}}$) without obscuring cyber-economic effects.
3. **Approval of 671-Day Streaming Execution Scope**:
   - *Proposal*: Run the full paired simulation across all 671 test days (Days 425–1095) for all three regimes (A, B, C) using a fast, vectorized CDA engine, preceded by a 5-day smoke test to verify execution speed and metric integrity.

---

## 9. Readiness Gate Recommendation

Based on this comprehensive design and consistency audit:
- The streaming data contract is completely verified against `Step5MarketStreamer`.
- The selective defense policy metrics are independently recomputed and bitwise verified against `Step 5/outputs/step5_2_policy_comparison.csv`.
- Ground-truth attack prevalence ($4.1985\%$) and false alarm rates ($95.50\%$) are reconciled.
- The locked paired simulation protocol is mathematically specified.
- No historical data or Step 1–5 artifacts were altered.

**RECOMMENDATION**: **READY FOR APPROVAL.** Upon user confirmation of the design choices in Section 8, Step 6.2 (modular CDA simulator implementation and unit testing) can commence immediately.
