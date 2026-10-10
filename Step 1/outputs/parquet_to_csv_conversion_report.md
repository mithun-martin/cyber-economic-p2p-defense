# Parquet to CSV Conversion and Verification Report

**Project**: Cyber-Economic Resilience Under Evolving Attacks  
**Component**: Step 1.2 — Frozen Benchmark Dataset Format Conversion  
**Conversion Date/Time**: 2026-10-03 15:22:12 UTC+05:30  
**Status**: **PASS — CSV verified equivalent to frozen Parquet**

---

## 1. File Metadata & Cryptographic Hashes

| Attribute | Input Parquet File | Output CSV File |
| :--- | :--- | :--- |
| **File Path** | `data/processed/ausgrid_solar_attacked.parquet` | `data/processed/ausgrid_solar_attacked.csv` |
| **File Size** | 173,015,190 bytes (165.00 MB) | 1,705,889,911 bytes (1,626.86 MB) |
| **SHA-256 Hash** | `176fa03152359472b544f2197427bca92f51127e4c2becad84e31ec72f6ca1b4` | `819ce00d29b5de917bdf2ff86e76da8befa092f59ca7c15ca32b233ad2747682` |
| **Immutability Status** | **UNTOUCHED & FROZEN** | **NEWLY GENERATED** |
| **Row Count** | 15,729,792 | 15,729,792 |
| **Column Count** | 19 | 19 |

*Note*: The Parquet SHA-256 hash was verified prior to conversion, immediately after conversion, and again during final audit verification. It remains bit-identical to the authoritative frozen benchmark hash.

---

## 2. Schema and Column Order Comparison

The Parquet schema and CSV header row match with 100% exact column order, name fidelity, and semantic mapping:

| Column Index | Column Name | Parquet Storage Type | CSV Logical Type | Order Match |
| :---: | :--- | :--- | :--- | :---: |
| 1 | `customer_id` | `int32` | Integer ID | **EXACT** |
| 2 | `postcode` | `int32` | Categorical Integer | **EXACT** |
| 3 | `generator_capacity` | `double` | Numeric Float64 | **EXACT** |
| 4 | `date` | `string` | ISO Date String (`YYYY-MM-DD`) | **EXACT** |
| 5 | `time_index` | `int32` | Integer Range `[0, 52607]` | **EXACT** |
| 6 | `interval_index` | `int8` | Integer Range `[0, 47]` | **EXACT** |
| 7 | `interval_label` | `string` | Time Label (`0:30` to `24:00`) | **EXACT** |
| 8 | `GC_clean` | `double` | Numeric Float64 (kWh) | **EXACT** |
| 9 | `GG_clean` | `double` | Numeric Float64 (kWh) | **EXACT** |
| 10 | `GC_attacked` | `double` | Numeric Float64 (kWh) | **EXACT** |
| 11 | `GG_attacked` | `double` | Numeric Float64 (kWh) | **EXACT** |
| 12 | `P_net_clean` | `double` | Numeric Float64 (kWh) | **EXACT** |
| 13 | `P_net_attacked` | `double` | Numeric Float64 (kWh) | **EXACT** |
| 14 | `is_attacked` | `bool` | Boolean (`true` / `false`) | **EXACT** |
| 15 | `attack_type` | `string` | Categorical String | **EXACT** |
| 16 | `attack_phase` | `string` | Categorical String | **EXACT** |
| 17 | `attack_target` | `string` | Categorical String | **EXACT** |
| 18 | `attack_param` | `float` (float32) | Numeric Float32 | **EXACT** |
| 19 | `is_actual` | `bool` | Boolean (`true` / `false`) | **EXACT** |

---

## 3. Numeric Comparison Results & Tolerances

Text-based CSV formats represent floating-point numbers in ASCII decimal form. When parsed back, double-precision numbers roundtrip within standard IEEE 754 precision limits.

### Numerical Tolerance Specification:
- **Telemetry Float64 Columns** (`GC_clean`, `GG_clean`, `GC_attacked`, `GG_attacked`, `P_net_clean`, `P_net_attacked`, `generator_capacity`):
  - Absolute Tolerance ($\text{atol}$): $1.0 \times 10^{-9}$
  - Relative Tolerance ($\text{rtol}$): $1.0 \times 10^{-6}$
  - *Rationale*: Meter energy values are measured in kWh to 3 decimal places in the raw dataset. A tolerance of $10^{-9}$ is several orders of magnitude tighter than physical sensor precision ($10^{-3}$ kWh) while accommodating IEEE 754 decimal conversion roundoff.
- **Metadata Float32 Column** (`attack_param`):
  - Absolute Tolerance ($\text{atol}$): $1.0 \times 10^{-6}$
  - Relative Tolerance ($\text{rtol}$): $1.0 \times 10^{-4}$
  - *Rationale*: Single-precision IEEE 754 has approximately 7 decimal digits of precision.

### Verification Results Across All 15,729,792 Rows:

| Numeric Column | Max Absolute Difference | Max Relative Difference | Values Exceeding Tolerance | Comparison Status |
| :--- | :---: | :---: | :---: | :---: |
| `generator_capacity` | $0.00 \times 10^{0}$ | $0.00 \times 10^{0}$ | 0 | **PASS (Exact)** |
| `GC_clean` | $0.00 \times 10^{0}$ | $0.00 \times 10^{0}$ | 0 | **PASS (Exact)** |
| `GG_clean` | $0.00 \times 10^{0}$ | $0.00 \times 10^{0}$ | 0 | **PASS (Exact)** |
| `GC_attacked` | $8.88 \times 10^{-16}$ | $1.52 \times 10^{-13}$ | 0 | **PASS (Machine Epsilon)** |
| `GG_attacked` | $8.88 \times 10^{-16}$ | $2.80 \times 10^{-13}$ | 0 | **PASS (Machine Epsilon)** |
| `P_net_clean` | $8.88 \times 10^{-16}$ | $9.91 \times 10^{-14}$ | 0 | **PASS (Machine Epsilon)** |
| `P_net_attacked` | $8.88 \times 10^{-16}$ | $1.44 \times 10^{-11}$ | 0 | **PASS (Machine Epsilon)** |
| `attack_param` | $0.00 \times 10^{0}$ | $0.00 \times 10^{0}$ | 0 | **PASS (Exact)** |

**Maximum numeric difference across entire dataset**: $8.88 \times 10^{-16}$ (order of machine epsilon $\approx 2^{-53} \approx 1.11 \times 10^{-16}$).

---

## 4. Exact Value Comparison (Integer, Boolean, Categorical, String)

For discrete, identification, and categorical columns, strict bit-for-bit equivalence was verified across all 15,729,792 rows:

| Column Name | Category Type | Total Rows Evaluated | Total Mismatches | Status |
| :--- | :--- | :---: | :---: | :---: |
| `customer_id` | Integer ID | 15,729,792 | 0 | **PASS (100% Identical)** |
| `postcode` | Integer Postcode | 15,729,792 | 0 | **PASS (100% Identical)** |
| `date` | Date String (`YYYY-MM-DD`) | 15,729,792 | 0 | **PASS (100% Identical)** |
| `time_index` | Time Sequence Index | 15,729,792 | 0 | **PASS (100% Identical)** |
| `interval_index` | Daily Interval `[0, 47]` | 15,729,792 | 0 | **PASS (100% Identical)** |
| `interval_label` | Half-Hour Label | 15,729,792 | 0 | **PASS (100% Identical)** |
| `is_attacked` | Boolean Attack Indicator | 15,729,792 | 0 | **PASS (100% Identical)** |
| `attack_type` | Categorical Attack Label | 15,729,792 | 0 | **PASS (100% Identical)** |
| `attack_phase` | Categorical Phase Label | 15,729,792 | 0 | **PASS (100% Identical)** |
| `attack_target` | Categorical Target Label | 15,729,792 | 0 | **PASS (100% Identical)** |
| `is_actual` | Boolean Meter Quality | 15,729,792 | 0 | **PASS (100% Identical)** |

---

## 5. Missing-Value Comparison

| Column Name | Parquet Null Count | CSV Null Count | Match Status |
| :--- | :---: | :---: | :---: |
| `customer_id` | 0 | 0 | **PASS** |
| `postcode` | 0 | 0 | **PASS** |
| `generator_capacity` | 0 | 0 | **PASS** |
| `date` | 0 | 0 | **PASS** |
| `time_index` | 0 | 0 | **PASS** |
| `interval_index` | 0 | 0 | **PASS** |
| `interval_label` | 0 | 0 | **PASS** |
| `GC_clean` | 0 | 0 | **PASS** |
| `GG_clean` | 0 | 0 | **PASS** |
| `GC_attacked` | 0 | 0 | **PASS** |
| `GG_attacked` | 0 | 0 | **PASS** |
| `P_net_clean` | 0 | 0 | **PASS** |
| `P_net_attacked` | 0 | 0 | **PASS** |
| `is_attacked` | 0 | 0 | **PASS** |
| `attack_type` | 0 | 0 | **PASS** |
| `attack_phase` | 0 | 0 | **PASS** |
| `attack_target` | 0 | 0 | **PASS** |
| `attack_param` | 0 | 0 | **PASS** |
| `is_actual` | 0 | 0 | **PASS** |

Both representations contain **0 missing values** across all 19 columns and all 15,729,792 rows.

---

## 6. Attack Distribution Invariants

### 6.1 Attack vs. Non-Attack Observation Counts

| Label | Parquet Count | CSV Count | Relative Frequency (%) | Match Status |
| :--- | :---: | :---: | :---: | :---: |
| `is_attacked == False` (Clean) | 15,283,221 | 15,283,221 | 97.1610% | **EXACT** |
| `is_attacked == True` (Attacked) | 446,571 | 446,571 | 2.8390% | **EXACT** |
| **Total** | **15,729,792** | **15,729,792** | **100.0000%** | **EXACT** |

### 6.2 Attack Type Distribution

| Attack Type | Parquet Count | CSV Count | Match Status |
| :--- | :---: | :---: | :---: |
| `NONE` | 15,283,221 | 15,283,221 | **EXACT** |
| `RAMP` | 179,360 | 179,360 | **EXACT** |
| `SCALING` | 163,784 | 163,784 | **EXACT** |
| `REPLAY` | 86,907 | 86,907 | **EXACT** |
| `COORDINATED` | 16,520 | 16,520 | **EXACT** |
| **Total Attacked** | **446,571** | **446,571** | **EXACT** |

### 6.3 Chronological Attack Phase Distribution

| Attack Phase | Parquet Count | CSV Count | Match Status |
| :--- | :---: | :---: | :---: |
| `1_NORMAL` | 5,238,480 | 5,238,480 | **EXACT** |
| `2_SCALING` | 3,387,072 | 3,387,072 | **EXACT** |
| `3_RAMP` | 3,588,000 | 3,588,000 | **EXACT** |
| `4A_REPLAY` | 1,750,944 | 1,750,944 | **EXACT** |
| `4B_COORDINATED` | 1,765,296 | 1,765,296 | **EXACT** |
| **Total** | **15,729,792** | **15,729,792** | **EXACT** |

### 6.4 Attack Target Distribution

| Attack Target | Parquet Count | CSV Count | Match Status |
| :--- | :---: | :---: | :---: |
| `NONE` | 15,283,221 | 15,283,221 | **EXACT** |
| `GG` | 182,708 | 182,708 | **EXACT** |
| `GC` | 178,223 | 178,223 | **EXACT** |
| `BOTH` | 85,640 | 85,640 | **EXACT** |
| **Total Attacked** | **446,571** | **446,571** | **EXACT** |

---

## 7. Customer Cohort & Temporal Progression Verification

| Invariant | Parquet Property | CSV Property | Verification Result |
| :--- | :---: | :---: | :---: |
| **Unique Customer Count** | 299 | 299 | **PASS (Exact Match)** |
| **Customer ID Set** | $\{1, 3, \dots, 300\}$ | $\{1, 3, \dots, 300\}$ | **PASS (Exact Match)** |
| **Customer 2 Exclusion** | Excluded | Excluded | **PASS (Verified Absent)** |
| **Observations per Customer** | Exactly 52,608 for all 299 | Exactly 52,608 for all 299 | **PASS (100% Uniform)** |
| **Time Index Range** | $[0, 52607]$ | $[0, 52607]$ | **PASS (Exact Range)** |
| **Rows per Time Index** | Exactly 299 | Exactly 299 | **PASS (100% Uniform)** |
| **Date Range** | 2010-07-01 to 2013-06-30 | 2010-07-01 to 2013-06-30 | **PASS (1,096 Days)** |
| **Interval Index Range** | $[0, 47]$ | $[0, 47]$ | **PASS (48 intervals/day)** |

---

## 8. Invariance on Clean Rows (`is_attacked == False`)

For all 15,283,221 non-attacked rows:
- `is_attacked == False` rows in CSV match Parquet perfectly across all rows.
- $GC_{\text{attacked}} \equiv GC_{\text{clean}}$ (max diff: $0.0$).
- $GG_{\text{attacked}} \equiv GG_{\text{clean}}$ (max diff: $0.0$).
- $P_{\text{net,attacked}} \equiv P_{\text{net,clean}}$ (max diff: $8.88 \times 10^{-16}$).
- `attack_type` is exclusively `"NONE"`.
- `attack_target` is exclusively `"NONE"`.
- `attack_param` is exclusively $0.0$.

---

## 9. Discrepancy Summary

- **Total Row Mismatches**: 0
- **Total Column Mismatches**: 0
- **Missing Value Discrepancies**: 0
- **Categorical / Boolean Mismatches**: 0
- **Values Exceeding Numerical Tolerance**: 0
- **Parquet Hash Changes**: 0 (Parquet file remained strictly read-only and unaltered)

---

## 10. Final Verification Status

$$\mathbf{PASS\ —\ CSV\ verified\ equivalent\ to\ frozen\ Parquet}$$

The CSV file `data/processed/ausgrid_solar_attacked.csv` is an exact, high-fidelity representation of the frozen benchmark `data/processed/ausgrid_solar_attacked.parquet`.
