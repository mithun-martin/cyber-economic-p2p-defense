# Processed Benchmark Datasets

This directory stores the clean processed baseline and the evolving false-data injection attack (FDIA) benchmark datasets generated in Step 1.

Due to file size limits on GitHub (>100 MB), large data files are tracked locally and excluded from Git commits. They can be reproduced deterministically using the scripts in `src/`.

---

## 1. Clean Processed Baseline
- **File**: `ausgrid_solar_processed.parquet`
- **Rows**: 15,729,792 (299 customers × 52,608 half-hour intervals)
- **Columns**: 13
- **File Size**: ~94.4 MB
- **SHA-256 Checksum**:
  ```text
  dc6bac0ea84a30b84af343ebd1ad7abd6905f9188989fc533a3a53a1d5c878b7
  ```
- **Generation Command**:
  ```bash
  python src/data_preprocessing.py
  ```

---

## 2. Frozen Attacked Benchmark (Parquet)
- **File**: `ausgrid_solar_attacked.parquet`
- **Rows**: 15,729,792
- **Columns**: 19
- **File Size**: 173,015,190 bytes (~165.00 MB)
- **Status**: **FROZEN & VERIFIED (Step 1.2 Benchmark)**
- **Master Seed**: 42
- **SHA-256 Checksum**:
  ```text
  176fa03152359472b544f2197427bca92f51127e4c2becad84e31ec72f6ca1b4
  ```
- **Generation Command**:
  ```bash
  python src/attack_generator.py
  ```

---

## 3. Frozen Attacked Benchmark (CSV)
- **File**: `ausgrid_solar_attacked.csv`
- **Rows**: 15,729,792
- **Columns**: 19
- **File Size**: 1,705,889,911 bytes (~1,626.86 MB)
- **SHA-256 Checksum**:
  ```text
  819ce00d29b5de917bdf2ff86e76da8befa092f59ca7c15ca32b233ad2747682
  ```
- **Equivalence Status**: Verified 100% equivalent to `ausgrid_solar_attacked.parquet` (maximum numerical difference $\le 8.88 \times 10^{-16}$, 0 discrepancies).
