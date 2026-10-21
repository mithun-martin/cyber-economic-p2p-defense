# Step 5 to Step 6 Interface Specification: Decision Engine to CDA Market Simulator

**Project**: Cyber-Economic Resilience Under Evolving Attacks in Peer-to-Peer Energy Markets  
**Charter Reference**: Major Project Plan — Steps 5 & 6 Handoff Protocol  
**Document Status**: AUTHORITATIVE & FROZEN  
**File Location**: `Step 5/reports/step5_interface_spec.md`  

---

## 1. Overview and Purpose

This specification defines the formal mathematical, data, and programmatic contract between **Step 5 (Economic-Aware Mitigation Decision Engine)** and **Step 6 (Continuous Double Auction [CDA] Market Simulator)**.

Step 5 processes half-hourly smart-meter energy telemetry, evaluates calibrated cyber-attack probabilities $p_{i, t} \in [0.0, 1.0]$, applies the expected-loss economic decision rule:
$$\text{Action}_i(t) = \begin{cases} \text{MITIGATE}, & \text{if } p_{i, t} \cdot C_{\text{FN}} > (1 - p_{i, t}) \cdot C_{\text{FP}} + C_{\text{M}} \\ \text{ALLOW}, & \text{otherwise} \end{cases}$$
and produces order-ready physical energy bids and asks, substituting anomalous bids with strictly causal trailing 7-day historical averages when mitigation is triggered.

---

## 2. Decision Engine Output Schema (Step 6 Input Contract)

Every 30-minute trading interval, Step 5 emits an enriched decision record for each active prosumer $i \in \{1, \dots, 299\}$:

| Field Name | Type | Unit | Description / Constraints |
| :--- | :---: | :---: | :--- |
| `customer_id` | `int64` | ID | Unique prosumer identifier $\{1, \dots, 300\}$. |
| `date` | `string` | YYYY-MM-DD | Calendar date of the market session. |
| `day_index` | `int64` | Days | Relative day index ($0$ to $1095$). Test period starts at day $425$. |
| `time_index` | `int64` | Slot | Global Ausgrid interval index ($0$ to $52,607$). |
| `interval_index` | `int64` | Slot | Half-hour of the day ($0$ to $47$, where $0$ = 00:00, $47$ = 23:30). |
| `raw_GC_kWh` | `float64` | kWh | Observed General Consumption from smart meter. |
| `raw_GG_kWh` | `float64` | kWh | Observed General Generation (solar) from smart meter. |
| `raw_P_net_kWh` | `float64` | kWh | Raw net physical volume: $GC - GG$. $>0$ = Buyer, $<0$ = Seller. |
| `reconstruction_error` | `float64` | MSE | 2-channel interval autoencoder reconstruction error $e_{i, t}$. |
| `p_attack` | `float64` | $[0, 1]$ | Calibrated cyber-attack probability from interval Platt scaler. |
| `C_FN_AUD` | `float64` | AUD ($) | Cost of false negative (unmitigated attack). |
| `C_FP_AUD` | `float64` | AUD ($) | Cost of false positive (unnecessary mitigation). |
| `C_M_AUD` | `float64` | AUD ($) | Administrative/computational mitigation overhead. |
| `expected_loss_allow` | `float64` | AUD ($) | $\mathbb{E}[L(\text{ALLOW})] = p \cdot C_{\text{FN}}$. |
| `expected_loss_mitigate`| `float64` | AUD ($) | $\mathbb{E}[L(\text{MITIGATE})] = (1 - p) \cdot C_{\text{FP}} + C_{\text{M}}$. |
| `decision` | `string` | Action | **`ALLOW`** or **`MITIGATE`**. |
| `decision_reason` | `string` | Text | Human-readable explanation of the loss comparison. |
| `mitigation_strategy` | `string` | Text | `none` if ALLOW; `trailing_7day_slot_average` if MITIGATE. |
| `substituted_GC_kWh` | `float64` | kWh | Causal historical consumption fallback if mitigated, else raw. |
| `substituted_GG_kWh` | `float64` | kWh | Causal historical generation fallback if mitigated, else raw. |
| `substituted_P_net_kWh` | `float64` | kWh | **Order Volume for Step 6 CDA**: $\hat{GC} - \hat{GG}$. |
| `is_attacked_ground_truth` | `int64` | $\{0, 1\}$ | **Evaluation metadata ONLY**. Must never influence CDA matching. |

---

## 3. How Step 6 CDA Simulator Consumes Step 5 Outputs

### 3.1 Order Generation for the CDA Order Book
In Step 6, each prosumer converts their physical net energy into a market order:
1. **Order Volume**:
   $$Q_i(t) = |\text{substituted\_P\_net\_kWh}_i(t)|$$
   - If $\text{substituted\_P\_net\_kWh} > 0$: Prosumer is a **Buyer** (submits a Bid).
   - If $\text{substituted\_P\_net\_kWh} < 0$: Prosumer is a **Seller** (submits an Ask).
   - If $\text{substituted\_P\_net\_kWh} == 0$: Prosumer is in energy balance (submits no order).
2. **Order Price Bounds**:
   Bids and asks must respect Australian residential retail tariff bounds:
   - Feed-in Tariff (Floor): $\text{FiT} = \$0.08/\text{kWh}$.
   - Grid Retail Tariff (Cap): $G_T = \$0.30/\text{kWh}$.
   - Sellers set ask prices $A_j \ge \text{FiT}$.
   - Buyers set bid prices $B_i \le G_T$.
3. **Continuous Double Auction Matching Engine**:
   - Limit order book maintains active bids (sorted descending by price) and asks (sorted ascending by price).
   - Trade clears immediately when highest bid $B^* \ge$ lowest ask $A^*$.
   - Transaction clearing price: $P^* = \frac{B^* + A^*}{2}$ (or k-double auction rule).

---

## 4. Injectable Dynamic Cost Interface (Step 6 Feedback to Step 5)

While Step 5 operates on static baseline cost configurations ($C_{\text{FN}} = \$0.50, C_{\text{FP}} = \$0.10, C_{\text{M}} = \$0.01$), Step 6 can optionally inject real-time market state to dynamically adjust costs:

```python
from Step_5.cost_model import ConfigurableCostModel, MarketState

# Step 6 instantiates dynamic cost provider
market_state = MarketState(
    net_volume_kwh=abs(row["substituted_P_net_kWh"]),
    order_price=bid_price,
    market_clearing_price=cleared_price,
    retail_tariff=0.30,
    feed_in_tariff=0.08,
    imbalance_penalty_rate=0.45,
    mitigation_fee=0.01
)

cost_model = ConfigurableCostModel(c_fn_base=0.50, c_fp_base=0.10, c_m_base=0.01)
dynamic_costs = cost_model.get_costs(market_state=market_state)
# dynamic_costs returns {'C_FN': ..., 'C_FP': ..., 'C_M': ...}
```

---

## 5. Non-Negotiable Contract Guarantees

1. **No Ground Truth Leakage**:
   `is_attacked_ground_truth` is included strictly for post-simulation loss and welfare calculations. Step 6 CDA matching algorithms must **never** read this column when determining bid priority, clearing prices, or execution order.
2. **Strict Causality**:
   All fallback substitutions in `substituted_P_net_kWh` were precomputed using only trailing days $d' < d$. Step 6 requires no lookahead buffers.
3. **Deterministic Repeatability**:
   Running the decision pipeline on identical telemetry and configuration produces bitwise identical decisions and expected losses.
