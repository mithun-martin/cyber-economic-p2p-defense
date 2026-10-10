# Ausgrid Solar Home Electricity Dataset — Comprehensive Raw Data Inspection Report

**Date of Inspection:** 2026-09-28  
**Dataset Location:** `data/raw/`  
**Dataset Files:**
1. `Solar home 2010-2011.csv` (63,621,419 bytes)
2. `Solar home 2011-2012.csv` (64,222,510 bytes)
3. `Solar home 2012-2013.csv` (63,782,724 bytes)

---

## 1. File Structure and Header Arrangement

### 1.1 Line 1: Metadata / Disclaimer Row
All three CSV files start with an unindexed descriptive disclaimer row on Line 1 with trailing commas:
```text
"<Year-Range> Solar home electricity data - Before using this data, please read the attached pdf document ""Ausgrid solar home electricity data notes (Aug 2014).pdf""",,,,,...
```
*Implication:* Preprocessing parsers must skip Line 1 (`skiprows=1` or `header=1`).

### 1.2 Line 2: Column Headers
- **2010-2011 (53 Columns):**
  `Customer`, `Generator Capacity`, `Postcode`, `Consumption Category`, `date`, `0:30`, `1:00`, `1:30`, ..., `23:30`, `0:00`
- **2011-2012 (54 Columns):**
  `Customer`, `Generator Capacity`, `Postcode`, `Consumption Category`, `date`, `0:30`, `1:00`, `1:30`, ..., `23:30`, `0:00`, `Row Quality`
- **2012-2013 (54 Columns):**
  `Customer`, `Generator Capacity`, `Postcode`, `Consumption Category`, `date`, `0:30`, `1:00`, `1:30`, ..., `23:30`, `0:00`, `Row Quality`

### 1.3 Measurement Columns (48 Half-Hour Intervals)
Across all three files, the interval columns are named identically:
`['0:30', '1:00', '1:30', '2:00', '2:30', '3:00', '3:30', '4:00', '4:30', '5:00', '5:30', '6:00', '6:30', '7:00', '7:30', '8:00', '8:30', '9:00', '9:30', '10:00', '10:30', '11:00', '11:30', '12:00', '12:30', '13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00', '17:30', '18:00', '18:30', '19:00', '19:30', '20:00', '20:30', '21:00', '21:30', '22:00', '22:30', '23:00', '23:30', '0:00']`
- Each interval represents energy in kilowatt-hours (kWh) consumed or generated in the half-hour ending at the specified timestamp (e.g., `0:30` represents `00:00 - 00:30`, `0:00` represents `23:30 - 24:00`).
- Australian Eastern Standard Time (AEST) / Australian Eastern Daylight Time (AEDT during daylight saving).

---

## 2. Quantitative Summary Statistics

| Metric | 2010–2011 | 2011–2012 | 2012–2013 | Total / Combined |
| :--- | :--- | :--- | :--- | :--- |
| **Total Lines in File** | 269,737 | 270,306 | 268,559 | 808,602 |
| **Data Rows** | 269,735 | 270,304 | 268,557 | 808,596 |
| **GC Rows** | 109,500 (300 × 365) | 109,800 (300 × 366) | 109,419 (299×365 + 284) | 328,719 |
| **GG Rows** | 109,500 (300 × 365) | 109,800 (300 × 366) | 109,419 (299×365 + 284) | 328,719 |
| **CL Rows** | 50,735 | 50,704 | 49,719 | 151,158 |
| **Unique Customers** | 300 (IDs 1–300) | 300 (IDs 1–300) | 300 (IDs 1–300) | 300 |
| **Unique Dates** | 365 | 366 (leap year) | 365 | 1,096 |
| **Date Format** | `D-Mon-YY` (`1-Jul-10`) | `D/MM/YYYY` (`1/07/2011`) | `D/MM/YYYY` (`1/07/2012`) | Heterogeneous |
| **Date Range** | 2010-07-01 to 2011-06-30 | 2011-07-01 to 2012-06-30 | 2012-07-01 to 2013-06-30 | 2010-07-01 to 2013-06-30 |
| **Row Quality Column** | Not present | Present | Present | Present in 2 of 3 |
| **'NA' (Non-Actual) Rows** | 0 (all actual) | 100 (0.037%) | 431 (0.160%) | 531 (0.066%) |
| **Missing Measurement Cells**| 0 | 0 | 0 | 0 |
| **Non-Numeric Entries** | 0 | 0 | 0 | 0 |
| **Negative Measurements** | 0 | 0 | 0 | 0 |
| **Measurement Range (kWh)**| [0.000, 7.073] | [0.000, 7.805] | [0.000, 6.567] | [0.000, 7.805] |
| **Zero Cells** | 5,013,586 (38.7%) | 5,045,766 (38.9%) | 5,019,486 (39.0%) | 15,078,838 (38.8%) |
| **Duplicate (Cust, Cat, Date)**| 0 | 0 | 0 | 0 |

---

## 3. Data Consistency & In-Depth Findings

### 3.1 Customer Identifiers & Metadata Invariance
- Exactly 300 customers are numbered sequentially from `1` to `300`.
- Customer metadata (`Generator Capacity` and `Postcode`) was cross-checked across all 3 years:
  - **Result: 0 mismatches.** Every customer has identical capacity and postcode across all three files.
  - Generator Capacity ranges from **1.00 kWp to 9.99 kWp** (Mean = 1.68 kWp, Median = 1.50 kWp).
  - 100 unique NSW postcodes (ranging from 2008 to 2330).

### 3.2 Consistency of General Consumption (GC) & Gross Generation (GG)
- **2010–2011:** All 300 customers have all 365 days for both GC and GG (100% complete).
- **2011–2012:** All 300 customers have all 366 days for both GC and GG (100% complete).
- **2012–2013:** 
  - 299 customers have all 365 days for both GC and GG.
  - **Customer 2** is missing **81 continuous days** in both GC and GG from **2012-10-12 to 2012-12-31**.
- **Summary:** Out of 300 customers, 299 customers have complete 1,096-day (3-year) profiles. Customer 2 has 1,015 days.

### 3.3 Controlled Load (CL) Availability
- Controlled load is **not universal**:
  - Only 139 customers have CL in 2010–2011 and 2011–2012.
  - Only 138 customers have CL in 2012–2013 (Customer 27's CL was discontinued).
  - 161 customers (~54%) do NOT have controlled load.
- *Conclusion:* Focusing primarily on GC and GG avoids having to discard or impute over half of the cohort.

### 3.4 Row Quality Analysis
- The `Row Quality` column indicates whether meter readings are raw actual readings (`Blank` / empty string) or estimated/substituted (`NA` = Non-Actual):
  - **2010–2011:** Column is omitted entirely; per Ausgrid documentation, only customers with 100% actual data were selected for Year 1.
  - **2011–2012:** 100 rows (56 GC, 22 GG, 22 CL) across 6 customers are marked `NA`.
  - **2012–2013:** 431 rows (283 GC, 146 GG, 2 CL) across 30 customers are marked `NA`. Customer 97 (138 rows), Customer 164 (118 rows), and Customer 146 (100 rows) account for 82.6% of all `NA` rows in 2012–2013.
  - Overall `NA` prevalence across 3 years is **0.066%** (531 out of 808,596 rows).

### 3.5 Solar Generation at Night & Physical Plausibility
- Measurement values are strictly non-negative (min = `0.000`).
- Night hours (`21:00` to `04:00`): Small residual non-zero GG readings occur (max = 0.013 kWh = 13 Wh), representing meter baseline noise, inverter standby consumption, or calibration offset.
- Day peak generation corresponds plausibly with customer PV capacity (maximum half-hour generation observed is 7.805 kWh).

---

## 4. Key Decisions for Preprocessing

Before proceeding with preprocessing code in `src/data_preprocessing.py`, the following decisions should be formalized:

1. **Handling Customer 2 Missing Block (81 days in 2012-10-12 to 2012-12-31):**
   - *Option A (Exclude Customer 2):* Keep the remaining 299 customers who possess 100% continuous 3-year timelines (1,096 days).
   - *Option B (Impute/Forward-Fill):* Impute the missing 81 days for Customer 2 using historical baseline data.
   - *Option C (Truncate Timeline):* Keep all 300 customers but only evaluate intervals where all 300 are active.
   - *Recommendation:* **Option A**. 299 customers is an extensive, statistically robust sample, and avoiding synthetic data in the ground truth maintains experimental purity for cybersecurity evaluation.

2. **Handling Row Quality `NA` (Estimated Values):**
   - *Option A:* Retain all rows regardless of `Row Quality` (since `NA` represents utility-sanctioned meter substitutions and constitutes only 0.066% of the data).
   - *Option B:* Exclude the few customers with recurring `NA` estimates (e.g., Customers 97, 164, 146).
   - *Option C:* Flag rows with a binary metadata column `is_actual` (True/False) during unification.
   - *Recommendation:* Retain rows and add an explicit boolean `is_actual` flag during preprocessing so the cybersecurity experiment can optionally filter or analyze robustness against utility-estimated values.

3. **Data Representation Format for Cybersecurity Experiments:**
   - Wide format (current: 48 interval columns per row) vs. Long format (unpivoted time series with ISO timestamps `YYYY-MM-DD HH:MM:SS`).
   - Net Demand representation: $P_{\text{net}} = \text{GC} - \text{GG}$ vs. Multi-channel dual time-series (GC channel + GG channel).

---

## 5. Recommended Preprocessing Plan

1. **Schema Harmonization:**
   - Standardize column names across all three CSVs.
   - Add default `Row Quality = ''` to the 2010–2011 file so all three files share identical 54-column schemas.
   - Map `Row Quality` into a clean boolean `is_actual = (Row_Quality != 'NA')`.

2. **Temporal Harmonization:**
   - Parse heterogeneous dates (`D-Mon-YY` for 2010–2011 vs `D/MM/YYYY` for 2011–2013) into standard ISO `YYYY-MM-DD`.
   - Map 48 half-hour column labels (`0:30` to `0:00`) to unified chronological index offsets `t_0` through `t_47` or exact half-hourly timestamps.

3. **Customer Filtering / Validation:**
   - Validate customer completeness. Exclude Customer 2 from the continuous 3-year cohort (or flag as incomplete).
   - Separate GC and GG matrices per customer for rapid attack injection and baseline modeling.
