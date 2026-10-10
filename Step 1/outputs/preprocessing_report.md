# Step 1: Preprocessing & Validation Report
**Project:** Major Project — Cybersecurity Experimental Framework (FDIA Detection Under Evolving Attack Distributions)  
**Dataset:** Ausgrid Solar Home Electricity Dataset (300 Solar Households, 2010–2013)  
**Execution Date:** 2026-09-28  
**Artifact:** `data/processed/ausgrid_solar_processed.parquet` (94.41 MB)

---

## 1. Executive Summary
The preprocessing layer for Step 1 of the major project has been fully implemented in `src/data_preprocessing.py` and validated using the test suite in `src/validation.py`. The raw yearly wide-format tables (with heterogeneous date representations, irregular schema headers, and non-canonical metadata rows) have been transformed into a unified, long/structured columnar Parquet time-series dataset.

All 14 validation criteria passed with 100% compliance.

---

## 2. Preprocessing Transformations

### 2.1 Schema Harmonization
- **Line 1 Disclaimer Handling:** Line 1 of all raw CSV files contains a human-readable disclaimer string (`"<Year-Range> Solar home electricity data..."`) followed by empty trailing commas. All file readers explicitly skip Line 1 (`skiprows=1`).
- **Row Quality Schema Alignment:**
  - `Solar home 2010-2011.csv` lacks the `Row Quality` column entirely (53 total columns). It was assigned a default empty string `""` upon loading.
  - `Solar home 2011-2012.csv` and `Solar home 2012-2013.csv` contain `Row Quality` at index 53 (54 total columns).
  - Crucially, `pd.read_csv` was configured with `keep_default_na=False` to prevent the literal string token `"NA"` (denoting utility "Non-Actual" estimated reads) from being coerced into missing `NaN` values.

### 2.2 Customer Cohort Selection & Exclusion of Customer 2
- **Initial Cohort:** 300 customers (IDs 1 through 300).
- **Customer 2 Exclusion:** Comprehensive raw inspection revealed that Customer 2 is missing **81 continuous days** in both General Consumption (GC) and Gross Generation (GG) between **2012-10-12 and 2012-12-31** (284 days present instead of 365 in Year 3).
- **Exclusion Policy:** Per project specifications, Customer 2 was completely excluded from the processed cohort. No imputation was applied, preserving complete experimental integrity and ground-truth purity.
- **Final Retained Cohort:** Exactly **299 customers** (IDs $\{1..300\} \setminus \{2\}$). Each retained customer has complete, contiguous 1,096-day records.

### 2.3 Row Quality and `is_actual` Derivation
- Ausgrid documentation defines:
  - `Blank / ""` = Actual electricity recorded by meter.
  - `"NA"` = Non-Actual where some or all half-hour values are utility substitutes or estimates.
- For 2010–2011, all rows were audited by Ausgrid as 100% actual reads (`is_actual = True`).
- For 2011–2012 and 2012–2013, row-level flags were extracted:
  - `is_actual_gc`: `True` if GC row is actual read.
  - `is_actual_gg`: `True` if GG row is actual read.
  - `is_actual`: Unified logical conjunction (`is_actual_gc & is_actual_gg`).
- Non-actual rows were **not deleted**; they are retained with their `is_actual` flag set to `False` (16,368 total half-hour intervals across 341 customer-days), enabling future experiments to evaluate detection sensitivity against utility estimation artifacts.

### 2.4 Measurement Representation and Integrity
- **Categories Retained:** General Consumption (`GC`) and Gross Generation (`GG`). Controlled Load (`CL`) was excluded from this stage as 161 of 300 households (~54%) do not have controlled load.
- **Zero Alteration Policy:** Original GC and GG measurements were maintained in their raw physical units (kWh per half-hour). No values were rounded, clipped, or normalized.
- **Nighttime Solar Values:** Small non-zero gross generation values (up to 0.013 kWh / 13 Wh) recorded during nocturnal hours (21:00–04:00) were strictly preserved.
- **Derived Net Demand:** Net load was computed as $P_{\text{net}} = \text{GC} - \text{GG}$ and included as a convenient derived column.

### 2.5 Time Representation & Interval Sequencing
- **No UTC or DST Conversions:** Time was kept in canonical meter interval order without applying UTC conversion, artificial resampling, or DST shifts.
- **Interval Indexing:** The 48 source intervals (`0:30`, `1:00`, ..., `23:30`, `0:00`) are mapped to sequential `interval_index` integers from `0` to `47`.
- **Interval Semantics:** The column `0:00` represents the final half-hour interval of the day from 23:30 to 24:00 (midnight).
- **Deterministic Time Index:** For each customer, a continuous chronological `time_index` is computed:
  $$\text{time\_index} = \text{day\_index} \times 48 + \text{interval\_index} \in [0, 52607]$$
- **Total Timeline:** 1,096 continuous days from `2010-07-01` to `2013-06-30` (including the 2012 leap year day `2012-02-29`).

---

## 3. Processed Dataset Schema & Dimensions

- **Storage Location:** `data/processed/ausgrid_solar_processed.parquet`
- **File Format:** Apache Parquet (Snappy compression, 94.41 MB on disk)
- **Total Rows:** **15,729,792** ($299 \text{ customers} \times 52,608 \text{ time points}$)
- **Total Columns:** 13

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `customer_id` | `int32` | Customer ID (1–300, excluding 2) |
| `postcode` | `int32` | Australian Postcode (100 unique NSW postcodes) |
| `generator_capacity` | `float64` | Rated solar panel capacity in kWp |
| `date` | `string` | Canonical calendar date in ISO `YYYY-MM-DD` |
| `time_index` | `int32` | Deterministic sequential timeline index (0–52,607) |
| `interval_index` | `int8` | Chronological half-hour index within the day (0–47) |
| `interval_label` | `string` | Original half-hour column label (`0:30` to `0:00`) |
| `GC` | `float64` | General Consumption (kWh per half-hour) |
| `GG` | `float64` | Gross Generation (kWh per half-hour) |
| `P_net` | `float64` | Derived net demand ($P_{\text{net}} = \text{GC} - \text{GG}$) |
| `is_actual` | `bool` | True if both GC and GG are actual meter readings |
| `is_actual_gc` | `bool` | True if GC reading is actual |
| `is_actual_gg` | `bool` | True if GG reading is actual |

---

## 4. Comprehensive Validation Results

The validation pipeline `src/validation.py` was executed against `data/processed/ausgrid_solar_processed.parquet`. All 14 tests produced a **PASS** result:

| # | Validation Criterion | Result | Actual Reported Metric |
| :---: | :--- | :---: | :--- |
| **01** | Exactly 299 retained customers | **PASS** | 299 unique customer IDs ($[1, 300]$) |
| **02** | Customer 2 absent from cohort | **PASS** | Customer 2 present = `False`; cohort strictly matches $\{1..300\} \setminus \{2\}$ |
| **03** | Each customer has exactly 52,608 time points | **PASS** | Min = 52,608, Max = 52,608 across all 299 customers |
| **04** | Total expected observations = 299 × 52,608 | **PASS** | Exactly 15,729,792 rows |
| **05** | Continuous deterministic `time_index` (0–52,607) | **PASS** | Strict sequential monotonic progression ($0..52607$) per customer |
| **06** | `interval_index` range is always 0–47 | **PASS** | Min = 0, Max = 47, unique count = 48 |
| **07** | Exactly 48 intervals per date | **PASS** | Min = 48, Max = 48 across all 327,704 customer-days |
| **08** | No missing GC values | **PASS** | 0 null/NaN entries in GC |
| **09** | No missing GG values | **PASS** | 0 null/NaN entries in GG |
| **10** | Non-negative measurements | **PASS** | GC $\in [0.0000, 7.8050]$ kWh, GG $\in [0.0000, 4.4190]$ kWh |
| **11** | Original measurement fidelity audit | **PASS** | Audited 864 values against raw CSV files; 100% identical bit-for-bit |
| **12** | `is_actual` correctly derived from Row Quality | **PASS** | Year 1 is 100% actual; 16,368 non-actual intervals correctly flagged (341 customer-days) |
| **13** | Schema & annual harmonization | **PASS** | Year 1: 5,238,480; Year 2: 5,252,832 (leap year); Year 3: 5,238,480 |
| **14** | Date range continuity (2010-07-01 to 2013-06-30)| **PASS** | Min: `2010-07-01`, Max: `2013-06-30`, 1,096 continuous dates matching calendar set |

---

## 5. Artifacts and Source Code Summary
1. [`src/data_preprocessing.py`](file:///home/scarlet/Documents/Sem%207/Major%20Project/src/data_preprocessing.py) — Ingestion, schema alignment, cohort filtering, and long-format Parquet writer.
2. [`src/validation.py`](file:///home/scarlet/Documents/Sem%207/Major%20Project/src/validation.py) — 14-point validation engine verifying data integrity, continuity, and fidelity.
3. [`data/processed/ausgrid_solar_processed.parquet`](file:///home/scarlet/Documents/Sem%207/Major%20Project/data/processed/ausgrid_solar_processed.parquet) — Canonical 15,729,792 observation dataset.
4. [`outputs/preprocessing_report.md`](file:///home/scarlet/Documents/Sem%207/Major%20Project/outputs/preprocessing_report.md) — Comprehensive documentation of the preprocessing and validation stage.
