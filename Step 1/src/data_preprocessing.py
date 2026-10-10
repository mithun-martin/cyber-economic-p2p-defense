"""
Ausgrid Solar Home Electricity Dataset - Preprocessing Layer
Part of Step 1: Data Preparation & Evolving Attacks.

This module ingests raw half-hourly electricity meter records across three years
(2010-2011, 2011-2012, 2012-2013), harmonizes schema differences, filters the
customer cohort according to data integrity criteria, and converts wide interval
tables into a long, structured, validated time-series representation.
"""

import os
import sys
import time
import argparse
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Canonical 48 half-hourly measurement interval columns in chronological sequence
INTERVAL_COLS: List[str] = [
    '0:30', '1:00', '1:30', '2:00', '2:30', '3:00', '3:30', '4:00',
    '4:30', '5:00', '5:30', '6:00', '6:30', '7:00', '7:30', '8:00',
    '8:30', '9:00', '9:30', '10:00', '10:30', '11:00', '11:30', '12:00',
    '12:30', '13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00',
    '16:30', '17:00', '17:30', '18:00', '18:30', '19:00', '19:30', '20:00',
    '20:30', '21:00', '21:30', '22:00', '22:30', '23:00', '23:30', '0:00'
]

# Source files configuration: (filename, date_format, has_row_quality_column)
YEAR_SPECS: List[Dict[str, any]] = [
    {
        "year_label": "2010-2011",
        "filename": "Solar home 2010-2011.csv",
        "date_format": "%d-%b-%y",
        "has_row_quality": False,
        "expected_days": 365,
    },
    {
        "year_label": "2011-2012",
        "filename": "Solar home 2011-2012.csv",
        "date_format": "%d/%m/%Y",
        "has_row_quality": True,
        "expected_days": 366,  # Leap year (includes 2012-02-29)
    },
    {
        "year_label": "2012-2013",
        "filename": "Solar home 2012-2013.csv",
        "date_format": "%d/%m/%Y",
        "has_row_quality": True,
        "expected_days": 365,
    },
]

# Customer exclusion: Customer 2 is missing 81 continuous days (2012-10-12 to 2012-12-31)
EXCLUDED_CUSTOMERS: List[int] = [2]
EXPECTED_TOTAL_DAYS: int = 1096
EXPECTED_TIMEPOINTS_PER_CUST: int = EXPECTED_TOTAL_DAYS * 48  # 52,608
EXPECTED_RETAINED_CUSTOMERS: int = 299


def load_and_harmonize_source_file(
    file_path: str,
    date_format: str,
    has_row_quality: bool,
    excluded_customers: List[int]
) -> pd.DataFrame:
    """
    Loads a single yearly Ausgrid CSV file, skips the non-tabular Line 1 disclaimer,
    harmonizes the column schema, normalizes date strings to ISO YYYY-MM-DD,
    derives row-level is_actual indicators, and filters for GC and GG categories
    and retained customers.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Raw source file not found: {file_path}")

    # Ausgrid raw files contain a descriptive disclaimer on Line 1; Line 2 is the actual header
    # keep_default_na=False is critical because "NA" is a domain value (Non-Actual) rather than missing
    df = pd.read_csv(file_path, skiprows=1, keep_default_na=False, low_memory=False)

    # Standardize column header strings
    df.columns = [col.strip() for col in df.columns]

    # Harmonize schema: 2010-2011 does not have the 'Row Quality' column
    if not has_row_quality or "Row Quality" not in df.columns:
        df["Row Quality"] = ""

    # Parse and normalize 'Row Quality':
    # Blank/empty string represents actual meter readings; 'NA' represents estimated/substituted readings
    raw_rq = df["Row Quality"].fillna("").astype(str).str.strip()
    df["is_actual_row"] = (raw_rq != "NA")

    # Cast customer ID to integer
    df["Customer"] = df["Customer"].astype(int)

    # Exclude designated incomplete customers (Customer 2)
    if excluded_customers:
        df = df[~df["Customer"].isin(excluded_customers)].copy()

    # Filter to General Consumption (GC) and Gross Generation (GG)
    df = df[df["Consumption Category"].isin(["GC", "GG"])].copy()

    # Parse heterogeneous date format into unified datetime
    df["date_parsed"] = pd.to_datetime(df["date"].astype(str).str.strip(), format=date_format)
    df["date_iso"] = df["date_parsed"].dt.strftime("%Y-%m-%d")

    return df


def pivot_year_to_long_arrays(df_year: pd.DataFrame) -> Dict[str, np.ndarray]:
    """
    Separates GC and GG records, verifies exact 1-to-1 customer-date alignment,
    and returns vectorized 1D arrays for customer_id, metadata, timestamps,
    measurements, and quality flags.
    """
    df_gc = df_year[df_year["Consumption Category"] == "GC"].copy()
    df_gg = df_year[df_year["Consumption Category"] == "GG"].copy()

    # Sort deterministically by customer and date
    df_gc = df_gc.sort_values(by=["Customer", "date_parsed"]).reset_index(drop=True)
    df_gg = df_gg.sort_values(by=["Customer", "date_parsed"]).reset_index(drop=True)

    n_days_gc = len(df_gc)
    n_days_gg = len(df_gg)
    if n_days_gc != n_days_gg:
        raise ValueError(f"GC and GG row counts mismatch: GC={n_days_gc}, GG={n_days_gg}")

    # Verify identical customer and date alignment
    if not (df_gc["Customer"].values == df_gg["Customer"].values).all():
        raise ValueError("Customer alignment mismatch between GC and GG rows.")
    if not (df_gc["date_iso"].values == df_gg["date_iso"].values).all():
        raise ValueError("Date alignment mismatch between GC and GG rows.")

    # Extract 2D measurement matrices: shape (n_days, 48)
    gc_mat = df_gc[INTERVAL_COLS].to_numpy(dtype=np.float64)
    gg_mat = df_gg[INTERVAL_COLS].to_numpy(dtype=np.float64)

    # Metadata per day
    cust_day = df_gc["Customer"].to_numpy(dtype=np.int32)
    postcode_day = df_gc["Postcode"].to_numpy(dtype=np.int32)
    capacity_day = df_gc["Generator Capacity"].to_numpy(dtype=np.float64)
    date_day = df_gc["date_iso"].to_numpy(dtype=object)
    is_actual_gc_day = df_gc["is_actual_row"].to_numpy(dtype=bool)
    is_actual_gg_day = df_gg["is_actual_row"].to_numpy(dtype=bool)

    # Vectorized repeat to 48 intervals per day
    cust_expanded = np.repeat(cust_day, 48)
    postcode_expanded = np.repeat(postcode_day, 48)
    capacity_expanded = np.repeat(capacity_day, 48)
    date_expanded = np.repeat(date_day, 48)
    is_actual_gc_expanded = np.repeat(is_actual_gc_day, 48)
    is_actual_gg_expanded = np.repeat(is_actual_gg_day, 48)

    # Interval indices (0-47) and labels
    interval_idx_expanded = np.tile(np.arange(48, dtype=np.int8), n_days_gc)
    interval_label_expanded = np.tile(np.array(INTERVAL_COLS, dtype=object), n_days_gc)

    # Flatten measurement values (row-major order: intervals 0 to 47 for day 0, then day 1, etc.)
    gc_expanded = gc_mat.reshape(-1)
    gg_expanded = gg_mat.reshape(-1)

    return {
        "customer_id": cust_expanded,
        "postcode": postcode_expanded,
        "generator_capacity": capacity_expanded,
        "date": date_expanded,
        "interval_index": interval_idx_expanded,
        "interval_label": interval_label_expanded,
        "GC": gc_expanded,
        "GG": gg_expanded,
        "is_actual_gc": is_actual_gc_expanded,
        "is_actual_gg": is_actual_gg_expanded,
        "n_days": n_days_gc
    }


def preprocess_dataset(
    raw_dir: str,
    output_path: str,
    excluded_customers: List[int] = EXCLUDED_CUSTOMERS
) -> str:
    """
    Main preprocessing pipeline:
    1. Reads and harmonizes all three yearly CSVs.
    2. Filters cohort to 299 complete customers.
    3. Combines multi-year chronological series.
    4. Computes deterministic sequential time_index and net demand P_net.
    5. Saves full long-format table to Parquet.
    """
    start_time = time.time()
    print("=" * 70)
    print("AUSGRID SOLAR HOME ELECTRICITY DATASET: PREPROCESSING PIPELINE")
    print(f"Raw data directory: {raw_dir}")
    print(f"Destination output: {output_path}")
    print(f"Excluding customer IDs: {excluded_customers}")
    print("=" * 70)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    yearly_data = []
    total_days_processed = 0

    for spec in YEAR_SPECS:
        y_label = spec["year_label"]
        fpath = os.path.join(raw_dir, spec["filename"])
        print(f"\n[1/3] Processing Year: {y_label} ({spec['filename']})...")
        t_yr = time.time()

        df_harmonized = load_and_harmonize_source_file(
            file_path=fpath,
            date_format=spec["date_format"],
            has_row_quality=spec["has_row_quality"],
            excluded_customers=excluded_customers
        )
        print(f"      Loaded & harmonized in {time.time() - t_yr:.2f}s | Filtered shape: {df_harmonized.shape}")

        t_piv = time.time()
        year_arrays = pivot_year_to_long_arrays(df_harmonized)
        yearly_data.append(year_arrays)
        total_days_processed += year_arrays["n_days"]
        print(f"      Pivoted to long format in {time.time() - t_piv:.2f}s | Days: {year_arrays['n_days']:,}")

    # Concatenate all three years across each array key
    print("\n[2/3] Merging 3-year timelines and constructing indices...")
    t_merge = time.time()
    merged_arrays: Dict[str, np.ndarray] = {}
    array_keys = [
        "customer_id", "postcode", "generator_capacity", "date",
        "interval_index", "interval_label", "GC", "GG",
        "is_actual_gc", "is_actual_gg"
    ]
    for key in array_keys:
        merged_arrays[key] = np.concatenate([y[key] for y in yearly_data])

    total_rows = len(merged_arrays["customer_id"])
    expected_rows = EXPECTED_RETAINED_CUSTOMERS * EXPECTED_TIMEPOINTS_PER_CUST
    print(f"      Total concatenated observation rows: {total_rows:,} (Expected: {expected_rows:,})")
    if total_rows != expected_rows:
        raise ValueError(f"Total row count {total_rows} does not match expected {expected_rows}")

    # Build DataFrame to ensure global customer-chronological sorting
    df_combined = pd.DataFrame(merged_arrays)
    # Sort primarily by customer_id and secondarily by date and interval_index
    df_combined = df_combined.sort_values(
        by=["customer_id", "date", "interval_index"]
    ).reset_index(drop=True)

    # Compute deterministic sequential time_index: 0 to 52,607 for each customer
    print("      Computing continuous time_index (0..52,607 per customer)...")
    time_indices = np.tile(np.arange(EXPECTED_TIMEPOINTS_PER_CUST, dtype=np.int32), EXPECTED_RETAINED_CUSTOMERS)
    df_combined["time_index"] = time_indices

    # Derive net demand P_net = GC - GG
    print("      Deriving net demand P_net = GC - GG...")
    df_combined["P_net"] = df_combined["GC"] - df_combined["GG"]

    # Unified is_actual flag: True if both GC and GG are actual meter readings
    print("      Synthesizing unified is_actual flag (is_actual_gc & is_actual_gg)...")
    df_combined["is_actual"] = df_combined["is_actual_gc"] & df_combined["is_actual_gg"]

    # Reorder columns logically
    ordered_cols = [
        "customer_id",
        "postcode",
        "generator_capacity",
        "date",
        "time_index",
        "interval_index",
        "interval_label",
        "GC",
        "GG",
        "P_net",
        "is_actual",
        "is_actual_gc",
        "is_actual_gg"
    ]
    df_combined = df_combined[ordered_cols]

    print(f"      Merge and index assembly complete in {time.time() - t_merge:.2f}s")

    # [3/3] Export to columnar Parquet
    print(f"\n[3/3] Writing processed dataset to Parquet: {output_path}...")
    t_write = time.time()

    # Define strict PyArrow schema to guarantee precision and columnar compression
    arrow_schema = pa.schema([
        ("customer_id", pa.int32()),
        ("postcode", pa.int32()),
        ("generator_capacity", pa.float64()),
        ("date", pa.string()),
        ("time_index", pa.int32()),
        ("interval_index", pa.int8()),
        ("interval_label", pa.string()),
        ("GC", pa.float64()),
        ("GG", pa.float64()),
        ("P_net", pa.float64()),
        ("is_actual", pa.bool_()),
        ("is_actual_gc", pa.bool_()),
        ("is_actual_gg", pa.bool_()),
    ])

    arrow_table = pa.Table.from_pandas(df_combined, schema=arrow_schema, preserve_index=False)
    pq.write_table(arrow_table, output_path, compression="snappy")

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"      Written successfully in {time.time() - t_write:.2f}s | Output size: {file_size_mb:.2f} MB")
    print("=" * 70)
    print(f"PREPROCESSING COMPLETED IN {time.time() - start_time:.2f} SECONDS")
    print(f"Final dataset dimensions: {len(df_combined):,} rows × {len(df_combined.columns)} columns")
    print("=" * 70)

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Ausgrid Solar Home Preprocessing Pipeline")
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="/home/scarlet/Documents/Sem 7/Major Project/data/raw",
        help="Path to raw CSV directory"
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default="/home/scarlet/Documents/Sem 7/Major Project/data/processed/ausgrid_solar_processed.parquet",
        help="Path to output Parquet file"
    )
    args = parser.parse_args()
    preprocess_dataset(args.raw_dir, args.output_path)


if __name__ == "__main__":
    main()
