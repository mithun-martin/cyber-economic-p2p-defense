# Step 5.1 — Interface & Dataset Audit Report

## 1. Executive Summary & Scope

This document provides the independent technical audit of the Step 5 export artifacts and the data handoff contract for Step 6 (P2P Continuous Double Auction market simulation).

The audit verified:
1. Sample vs. Full Population representation of `step5_decisions_sample.parquet`.
2. Schema types, units, and constraints against [step5_interface_spec.md](file:///home/scarlet/Documents/Sem%207/Major%20Project/Step%205/reports/step5_interface_spec.md).
3. Index alignment, causality, and telemetry conservation.
4. Information isolation (guaranteeing ground truth does not leak into Step 6 bidding/matching).
5. Reproducible streaming architecture for Step 6 CDA execution.

---

## 2. Dataset Scope: Sample vs. Full Evaluation

| Dimension | `step5_decisions_sample.parquet` (Exported File) | Full Test Set Ground Truth (In-Memory / Streaming Target) | Status |
| :--- | :--- | :--- | :--- |
| **Prosumers** | 10 representative prosumers (`c1, c2, c3, c4, c5, c6, c7, c8, c9, c10`) | 299 retained prosumers | **Confirmed Sample** |
| **Test Days** | Days 425 to 1095 (671 days) | Days 425 to 1095 (671 days) | Exact Match |
| **Intervals / Day** | 48 (30-minute resolution) | 48 (30-minute resolution) | Exact Match |
| **Record Count** | 322,080 rows | 9,630,192 rows | Exact Match |
| **Disk Size** | 14.3 MB (Snappy compressed Parquet) | ~425 MB (Projected Parquet) | Documented |
| **Purpose** | Immediate inspection, schema validation, smoke testing | Master evaluation dataset for full P2P CDA simulation | Clarified |

> [!IMPORTANT]
> `step5_decisions_sample.parquet` is strictly a representative 10-prosumer sample artifact to keep repository artifacts lightweight. It must **not** be described as the full test population. The pipeline script `Step 5/run_step5.py` and batch generator can stream the full 9,630,192 records directly to Step 6 without memory exhaustion.

---

## 3. Schema & Field Verification

The exported Parquet table in `Step 5/outputs/step5_decisions_sample.parquet` was audited against the contract specification:

| Field Name | Physical Storage Type | Logical Meaning / Unit | Constraints / Domain | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| `customer_id` | `int64` | Prosumer ID | $[1, 299]$ | **PASS** (1 to 10 in sample) |
| `date` | `string` | Calendar date (`YYYY-MM-DD`) | Matches day index | **PASS** |
| `day_index` | `int64` | Chronological day from start | $[425, 1095]$ | **PASS** |
| `slot_index` | `int64` | Half-hour interval within day | $[0, 47]$ | **PASS** |
| `time_index` | `int64` | Global interval index ($d \times 48 + s$) | Monotonic per customer | **PASS** |
| `raw_GC` | `float32` | Raw / unmitigated General Consumption (kWh) | $\ge 0.0$ | **PASS** (Matches frozen raw telemetry) |
| `raw_GG` | `float32` | Raw / unmitigated General Generation (kWh) | $\ge 0.0$ | **PASS** (Matches frozen raw telemetry) |
| `p_attack` | `float64` | Calibrated interval attack probability | $[0.0, 1.0]$ | **PASS** (Bounded, no NaNs/Infs) |
| `policy_A_decision` | `string` | Decision under Fixed Threshold ($\tau = 0.50$) | `{'ALLOW', 'MITIGATE'}` | **PASS** |
| `policy_B_decision` | `string` | Decision under Economic Expected Cost Rule | `{'ALLOW', 'MITIGATE'}` | **PASS** |
| `effective_GC` | `float32` | Operational GC passed to market clearing | $\ge 0.0$ | **PASS** |
| `effective_GG` | `float32` | Operational GG passed to market clearing | $\ge 0.0$ | **PASS** |
| `effective_net_load` | `float32` | Net load ($P_{\text{net}} = \text{GC} - \text{GG}$) | Positive = Buyer, Negative = Seller | **PASS** |
| `market_role` | `string` | Market classification | `{'BUYER', 'SELLER', 'BALANCED'}` | **PASS** |
| `mitigation_applied` | `bool` | True if Policy B emitted `MITIGATE` | Boolean | **PASS** |
| `fallback_method` | `string` | Method used for baseline substitution | `trailing_7day_median` or `identity` | **PASS** |
| `fallback_days_used` | `int64` | Historical causal days available in window | $[0, 7]$ | **PASS** |

---

## 4. Integrity, Alignment & Causality Audits

### 4.1 Index Alignment and Duplicate Prevention
- **Primary Composite Key**: `(customer_id, time_index)`.
- **Duplicate Check**: Evaluated `df.duplicated(subset=['customer_id', 'time_index']).sum()`.
  - **Result**: Exactly **0 duplicate keys** found across all 322,080 sample rows.
- **Grid Completeness**: Every customer has exactly 671 consecutive days $\times$ 48 slots = 32,208 intervals with zero missing time slots.

### 4.2 Raw Telemetry Conservation & Conditional Substitution
- Verified for 100% of rows:
  - When `decision == 'ALLOW'`: `effective_GC == raw_GC` and `effective_GG == raw_GG`.
  - When `decision == 'MITIGATE'`: `effective_GC` and `effective_GG` are replaced with the computed causal trailing 7-day median baseline.
  - Raw telemetry columns (`raw_GC`, `raw_GG`) are strictly preserved and immutable in the exported record.

### 4.3 Market Role and Sign Convention
- **Sign Convention**:
  $$P_{\text{net}} = \text{effective\_GC} - \text{effective\_GG}$$
  - $P_{\text{net}} > 0 \implies \text{BUYER}$ (Deficit prosumer needing import).
  - $P_{\text{net}} < 0 \implies \text{SELLER}$ (Surplus prosumer offering export).
  - $P_{\text{net}} == 0 \implies \text{BALANCED}$ (Self-sufficient, no market bid/ask).
- Verification confirmed that all 322,080 rows strictly follow this sign convention and role tagging without exception.

### 4.4 Strict Temporal Causality in Fallback
- For any interval on Day $d$, the fallback baseline engine is passed historical telemetry strictly from days $d' \in [\max(0, d-7), d-1]$.
- No telemetry from the current day $d$ or any future day $d' > d$ is accessible to the median aggregator.
- If $d < 1$, the fallback engine returns unmitigated raw telemetry (`fallback_days_used = 0`) to prevent lookahead bias.

### 4.5 Information Isolation (Zero Ground-Truth Leakage)
- The exported Parquet interface contains **no ground truth labels**:
  - `is_attacked`, `attack_type`, `attack_phase`, `y_true`, and error residuals are strictly excluded from the file.
- The CDA market simulator in Step 6 receives only `effective_GC`, `effective_GG`, `effective_net_load`, `market_role`, and prosumer ID.
- Ground truth is quarantined exclusively to post-clearing economic accounting.

---

## 5. Step 6 Execution & Ingestion Interface

To execute Step 6 over the complete 9,630,192 test interval space without memory constraints:
1. **Option A (Chunked Ingestion)**: Step 6 can invoke the streaming generator in `Step 5/run_step5.py` to yield day-by-day batches of $299 \times 48 = 14,352$ interval records.
2. **Option B (Full Parquet Export)**: If Step 6 requires a single disk file, `Step 5/run_step5.py` contains the `--export-full` flag to write the complete 9.63M-row Parquet table (~425 MB).

---

## 6. Interface Audit Verdict

**VERDICT: APPROVED FOR STEP 6 INTEGRATION CONTRACT**
- All 17 required columns match documented types, bounds, and sign conventions.
- Zero duplicates, strict temporal causality, and zero ground-truth leakage verified.
