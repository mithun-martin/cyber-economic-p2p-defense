# Step 1 → Step 2 Handoff
## Cyber-Economic Resilience Under Evolving Attacks

## 1. Purpose

This package contains the finalized and frozen output of **Step 1.2 — Data Preparation & Evolving Attacks**.

Step 1.2 transformed the clean Ausgrid Solar Home Electricity dataset into a chronological benchmark containing normal telemetry plus scaling, ramp, replay, and coordinated false-data injection attacks.

**Step 1.2 is COMPLETE, VERIFIED, and FROZEN.**

The benchmark must not be regenerated or modified during Step 2.

---

## 2. Overall Project

Research question:

> How can a data-local continual federated detector adapt to evolving FDIAs while translating uncertain cyber-threat predictions into economically resilient mitigation decisions in P2P energy markets?

### Layer 1 — Cybersecurity & Machine Learning

1. Data Preparation & Evolving Attacks
2. Local AI Defense
3. Privacy-Aware Collaboration
4. Continual Learning

### Layer 2 — Economic Resilience

5. Economic-Aware Mitigation Decision
6. Economic Resilience Evaluation

This handoff transfers Step 1.2 to the person responsible for Step 2.

---

## 3. Step 2 Responsibility — Local AI Defense

The intended Step 2 pipeline is:

```text
Frozen telemetry benchmark
        ↓
Temporal sliding windows
        ↓
1-D Convolutional Autoencoder
        ↓
Reconstruction Error
        ↓
Error → Attack Probability Calibration
        ↓
Local Attack Detector
```

The detector should ultimately produce:

```text
p_t = estimated probability of attack at time t
```

This probability will later be used by Steps 3–5.

Do not implement Steps 3–6 unless explicitly requested.

---

## 4. Dataset Files

Two representations of the same frozen benchmark are provided:

```text
DATA/ausgrid_solar_attacked.parquet
DATA/ausgrid_solar_attacked.csv
```

The **Parquet is the archival source of truth**.

The CSV is a verified equivalent representation provided for convenience.

You may use either for Step 2.

---

## 5. Benchmark Size

- **15,729,792 rows**
- **299 customers**
- **52,608 observations per customer**
- **1,096 days**
- **48 half-hour observations per day**
- **19 columns**

Customer 2 is intentionally excluded because of the continuous missing period identified during original dataset inspection.

---

## 6. Time Structure

The data is half-hourly:

```text
48 intervals per day
interval_index = 0 ... 47
```

The original source ordering is preserved. No UTC conversion, resampling, or artificial DST shifting was performed.

```text
time_index = day_index × 48 + interval_index
```

Range:

```text
0 ... 52607
```

Date range:

```text
2010-07-01 → 2013-06-30
```

Preserve this temporal structure.

**Do not randomly shuffle the entire dataset before creating temporal windows.**

---

## 7. Dataset Columns

```text
customer_id
postcode
generator_capacity
date
time_index
interval_index
interval_label
GC_clean
GG_clean
GC_attacked
GG_attacked
P_net_clean
P_net_attacked
is_attacked
attack_type
attack_phase
attack_target
attack_param
is_actual
```

### Main telemetry

- `GC` — General Consumption
- `GG` — Gross Generation
- `P_net` — net representation, derived as `GC - GG`

Both clean and attacked versions are included.

---

## 8. CRITICAL — Prevent Data Leakage

The following fields are **ground-truth/evaluation metadata**:

```text
is_attacked
attack_type
attack_phase
attack_target
attack_param
```

**Do NOT use them as detector input features.**

They may be used for:

- evaluation
- confusion matrices
- attack-type analysis
- phase/concept-drift analysis
- figures and tables
- false-positive/false-negative analysis

But they must never tell the detector whether a sample is attacked.

The detector must learn from telemetry.

---

## 9. Clean vs Attacked Telemetry

The benchmark includes:

```text
GC_clean
GC_attacked

GG_clean
GG_attacked

P_net_clean
P_net_attacked
```

For non-attacked observations:

```text
GC_attacked = GC_clean
GG_attacked = GG_clean
P_net_attacked ≈ P_net_clean
```

For attacked observations, the attacked columns contain the simulated FDIA.

The exact model input representation must be decided and documented during Step 2.

---

## 10. Chronological Attack Progression

The benchmark intentionally represents evolving attacks.

### Phase 1 — Normal

```text
2010-07-01 → 2011-06-30
```

No attacks.

### Phase 2 — Scaling

```text
2011-07-01 → 2012-02-21
```

Abrupt multiplicative scaling attacks.

### Phase 3 — Ramp

```text
2012-02-22 → 2012-10-27
```

Gradually changing attack factors, representing drift.

### Phase 4A — Replay

```text
2012-10-28 → 2013-02-26
```

Historical observations from the same customer are replayed.

Configured lags:

```text
7 days
14 days
21 days
```

### Phase 4B — Coordinated

```text
2013-02-27 → 2013-06-30
```

Multi-agent/economic-collusion scenario:

- selected net sellers inflate reported generation
- selected net buyers deflate reported consumption
- attacks are synchronized during the configured market window

---

## 11. Attack Targets

Attacks can target:

```text
GC
GG
BOTH
```

Approved allocation:

```text
40% GG
40% GC
20% BOTH
```

These are allocation probabilities/expected proportions, not exact per-episode quotas.

---

## 12. Attack Generation Constraints

The frozen benchmark was generated under these major constraints:

- attacks originate from the clean baseline
- no chained attacks on already-attacked observations
- no overlapping attack episodes for the same customer
- physical plausibility constraints are preserved
- generation cannot exceed installed PV capacity for a half-hour interval
- negative energy values are not introduced
- authentic nighttime GG behavior is preserved
- no artificial upper ceiling is imposed on GC
- replay attacks use the same customer's historical data
- coordinated attacks operate across multiple customers

Master seed:

```text
42
```

---

## 13. Benchmark Statistics

```text
Total observations: 15,729,792
Clean observations: 15,283,221
Attacked observations: 446,571
Attack rate: 2.839%
```

Attack types:

```text
NONE          15,283,221
SCALING          163,784
RAMP             179,360
REPLAY            86,907
COORDINATED       16,520
```

Attack targets:

```text
NONE       15,283,221
GG            182,708
GC            178,223
BOTH           85,640
```

These are orientation statistics; the dataset and generation report are authoritative.

---

## 14. Data Quality / Preprocessing Decisions

### Customer 2

Excluded because of a continuous missing period affecting primary GC/GG telemetry.

No artificial imputation was performed.

### Non-actual observations

Retained and represented by:

```text
is_actual
```

Do not silently delete them.

### GC and GG

Retained separately.

### Nighttime GG

Authentic small nighttime GG readings were preserved.

Do not automatically force nighttime generation to zero.

### Temporal structure

Original source ordering was preserved.

No artificial UTC conversion or resampling was performed.

---

## 15. Temporal Data-Leakage Warning

Avoid creating train/test leakage by randomly distributing heavily overlapping temporal windows between training and test.

For example, two highly overlapping windows must not be allowed to make evaluation artificially optimistic simply because they were randomly split.

The train/validation/test methodology should be temporal and documented before final training.

Do not perform an unrestricted random row-level split.

---

## 16. Sliding Windows

Step 2 should create temporal windows suitable for the 1-D convolutional autoencoder.

The following must be explicitly decided and documented:

- window length
- stride
- input features
- normalization
- training period
- validation period
- test period

Do not silently change these choices to improve results.

---

## 17. Intended Step 2 Architecture

```text
Telemetry Window
       ↓
1-D Convolutional Encoder
       ↓
Latent Representation
       ↓
1-D Convolutional Decoder
       ↓
Reconstructed Window
       ↓
Reconstruction Error
       ↓
Attack Probability Calibration
       ↓
p_t
```

The detector should learn normal/expected temporal behavior and identify deviations through reconstruction error.

Architecture and hyperparameters must be documented.

---

## 18. Reconstruction Error and Probability

The detector should calculate reconstruction error between the original telemetry window and reconstructed window.

This should ultimately be calibrated into:

```text
p_t = attack probability
```

This is important because later economic mitigation uses probability rather than only a binary attack/no-attack output.

Preserve both reconstruction-error and calibration methodology/results.

---

## 19. Evaluation Requirements

Evaluate at minimum:

- overall detection performance
- false positives
- false negatives
- performance by attack type
- performance across chronological phases
- behavior under evolving attacks
- attack-probability calibration

Where appropriate, report results separately for:

```text
Scaling
Ramp
Replay
Coordinated
```

---

## 20. Step 1 → Step 2 Boundary

### Step 1 owns

```text
Raw dataset inspection
        ↓
Preprocessing
        ↓
Attack specification
        ↓
Attack generation
        ↓
Attack validation
        ↓
Frozen benchmark
```

### Step 2 owns

```text
Frozen benchmark
        ↓
Window generation
        ↓
Local AI model
        ↓
Reconstruction error
        ↓
Probability calibration
        ↓
Local detector evaluation
```

Do not move responsibilities across this boundary without discussion.

---

## 21. FROZEN DATASET RULE

The following benchmark files are immutable:

```text
ausgrid_solar_attacked.parquet
ausgrid_solar_attacked.csv
```

Do NOT:

- regenerate attacks
- change attack parameters
- change attack labels
- modify telemetry values
- remove attack observations
- add synthetic attacks
- impute benchmark values
- resample the benchmark
- alter chronological ordering
- overwrite either benchmark file

You MAY create derived Step 2 artifacts such as:

```text
windowed datasets
training tensors
validation tensors
test tensors
normalized features
model predictions
reconstruction errors
calibration outputs
```

Keep derived artifacts separate from the frozen benchmark.

---

## 22. If Something Looks Wrong

Do not "fix" the benchmark yourself.

If something appears unusual:

1. Check `attack_model_specification.md`.
2. Check `attack_generation_report.md`.
3. Check the original dataset documentation.
4. Document the observation.
5. Raise it for review.

Some unusual values are intentional and reflect the source dataset or attack-model assumptions.

---

## 23. CSV Conversion Verification

The CSV was generated directly from the frozen Parquet and independently verified across the complete dataset.

```text
Rows:                    15,729,792
Columns:                 19
Row mismatches:          0
Column mismatches:       0
Missing discrepancies:   0
Categorical mismatches:  0
Boolean mismatches:      0
Tolerance failures:      0
```

Maximum numeric difference after CSV round-trip:

```text
8.88 × 10^-16
```

The Parquet remained unchanged.

---

## 24. Benchmark Hashes

### Frozen Parquet SHA-256

```text
176fa03152359472b544f2197427bca92f51127e4c2becad84e31ec72f6ca1b4
```

### CSV SHA-256

```text
819ce00d29b5de917bdf2ff86e76da8befa092f59ca7c15ca32b233ad2747682
```

The hashes are expected to differ because the files use different formats.

The conversion audit established that their contents are equivalent.

---

## 25. Supporting Documentation

Included documentation:

```text
attack_model_specification.md
attack_generation_report.md
parquet_to_csv_conversion_report.md
attack_config.yaml
```

Use them as follows:

- `attack_model_specification.md` — authoritative cybersecurity attack-model definition
- `attack_generation_report.md` — final generation statistics and validation
- `parquet_to_csv_conversion_report.md` — CSV/Parquet equivalence audit
- `attack_config.yaml` — configuration used to generate the frozen benchmark

---

## 26. Reproducibility

Attack-generation master seed:

```text
42
```

The benchmark is a fixed experimental artifact.

For every Step 2 experiment, record:

- random seed
- window length
- stride
- feature selection
- normalization
- train/validation/test temporal boundaries
- model architecture
- hyperparameters
- calibration method
- evaluation metrics

These records will be needed for reproducibility and paper writing.

---

## 27. Expected Step 2 Deliverables

Before moving to Step 3, produce at minimum:

1. Documented windowing strategy
2. Documented feature/input strategy
3. Documented temporal train/validation/test strategy
4. Local 1-D convolutional autoencoder
5. Reconstruction-error outputs
6. Attack-probability calibration
7. Local detector evaluation
8. Performance by attack type/phase where appropriate
9. Saved model/configuration artifacts
10. Step 2 experiment/report document
11. Reproducibility information

Do not proceed to federated learning until the Step 2 local detector and its output interface are documented.

---

## 28. Final Status

```text
STEP 1.2 — COMPLETE
STEP 1.2 — VERIFIED
STEP 1.2 — FROZEN

STEP 2 — READY TO BEGIN
```

The objective of Step 2 is now to determine how effectively a local detector can identify the evolving attacks represented in the frozen benchmark while producing a calibrated attack probability suitable for the later federated and economic-resilience stages.

---

## END OF HANDOFF
