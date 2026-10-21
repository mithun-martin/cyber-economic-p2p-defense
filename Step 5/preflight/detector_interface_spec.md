# Step 5 Detector Interface Specification: Physical-to-Economic Bridge

**Project**: Cyber-Economic Resilience Under Evolving Attacks in Peer-to-Peer Energy Markets  
**Charter Reference**: Major Project Plan — Steps 4 to 5 Interface Protocol  
**Document Status**: AUTHORITATIVE & FROZEN  
**File Location**: `Step 5/preflight/detector_interface_spec.md`  

---

## 1. Overview and Purpose

This specification defines the formal mathematical, algorithmic, and programmatic contract between the **Physical Threat Detection Layer (Step 4 / Step 5 Preflight)** and the downstream **Economic Mitigation Engine (Step 5)** and **Continuous Double Auction (CDA) Simulator (Step 6)**.

The objective of this interface is to provide a clean, calibrated, and reproducible attack probability:
$$p_{i, t} \in [0.0, 1.0]$$
for each prosumer $i \in \{1, \dots, 299\}$ at each 30-minute trading interval $t \in \{0, \dots, 47\}$ of every market day. This probability directly feeds into the Step 5 risk-adjusted economic decision rule:
$$\text{Action}_i(t) = \begin{cases} \text{MITIGATE}, & \text{if } p_{i, t} \cdot C_{\text{FN}}(t) > (1 - p_{i, t}) \cdot C_{\text{FP}}(t) + \Omega_{\text{mit}} \\ \text{ALLOW}, & \text{otherwise} \end{cases}$$

---

## 2. Input Telemetry Schema and Feature Order

### 2.1 Raw Input Requirements
The detector operates on diurnal (24-hour) smart-meter energy telemetry sourced from `data/processed/ausgrid_solar_attacked.parquet`.

| Dimension | Shape | Data Type | Physical Unit | Description |
| :--- | :---: | :---: | :---: | :--- |
| **Batch Size ($B$)** | `B` | `int` | — | Number of daily windows processed concurrently. |
| **Channels ($C$)** | `2` | `float32` | kWh / 30-min | Exact ordering: **Channel 0 = GC, Channel 1 = GG**. |
| **Time Steps ($T$)** | `48` | `float32` | 30-min slots | 48 half-hour intervals spanning a complete 24-hour day (00:00 to 23:30). |

```text
Input Tensor: X ∈ ℝ^[B, 2, 48]
  X[:, 0, :] → General Consumption (GC_attacked)
  X[:, 1, :] → General Generation (GG_attacked)
```

### 2.2 Prohibited Features (Data Hygiene)
The following columns present in `ausgrid_solar_attacked.parquet` **MUST NEVER** be fed into the detector as input features:
- `is_attacked` (Ground truth label; strictly for evaluation and calibration targets)
- `attack_type` (Ground truth target)
- `attack_phase` (Ground truth target)
- `clean_GC`, `clean_GG` (Ground truth baseline)
- `generator_capacity` (Fixed static attribute)

---

## 3. Normalization Protocol and Scaler Parameters

### 3.1 Mathematical Normalization Rule
Telemetry data is normalized using customer-specific Min-Max scaling fitted exclusively on that customer's Phase 1 clean baseline (Days 0 to 364):
$$\tilde{x}_{c, k, t} = \frac{x_{c, k, t} - \min_{c, k}}{\max_{c, k} - \min_{c, k} + \epsilon}$$
where:
- $c \in \{1, \dots, 299\}$ is the customer index.
- $k \in \{0 (\text{GC}), 1 (\text{GG})\}$ is the telemetry channel.
- $\epsilon = 10^{-6}$ is a numerical stability epsilon preventing division by zero for non-solar prosumers.

### 3.2 Parameter Storage
Standalone customer normalization bounds are stored in:
`Step 5/preflight/normalization_bounds.json`
Schema:
```json
{
  "1": {
    "min_GC": 0.0,
    "max_GC": 4.128,
    "min_GG": 0.0,
    "max_GG": 3.491
  },
  ...
}
```

---

## 4. Detector Model Specification

### 4.1 Architecture: `ConvAE_v2`
- **Total Trainable Parameters**: $23,258$
- **Bottleneck Dimensionality**: $24$ latent features (yielding a $4:1$ compression ratio from the $96$ input elements).
- **PyTorch Definition**:
  ```python
  class ConvAE_v2(nn.Module):
      def __init__(self, in_channels: int = 2, latent_dim: int = 24):
          super().__init__()
          self.encoder = nn.Sequential(
              nn.Conv1d(in_channels, 16, kernel_size=4, stride=2, padding=1),
              nn.ReLU(),
              nn.Conv1d(16, 32, kernel_size=4, stride=2, padding=1),
              nn.ReLU(),
              nn.Flatten(),
              nn.Linear(32 * 12, latent_dim)
          )
          self.decoder_fc = nn.Sequential(
              nn.Linear(latent_dim, 32 * 12),
              nn.ReLU()
          )
          self.decoder = nn.Sequential(
              nn.ConvTranspose1d(32, 16, kernel_size=4, stride=2, padding=1),
              nn.ReLU(),
              nn.ConvTranspose1d(16, in_channels, kernel_size=4, stride=2, padding=1)
          )

      def forward(self, x):
          z = self.encoder(x)
          return self.decoder(self.decoder_fc(z).view(-1, 32, 12))
  ```

### 4.2 Checkpoint Path
- **Primary Model Checkpoint**: `Step 5/preflight/detector_checkpoint.pt`
- **Training Protocol**: FedAvg across all 299 prosumers over 30 global communication rounds on clean Phase 1 telemetry (Days 0 to 304).

---

## 5. Reconstruction Error Formulation

For an input window $\mathbf{X} \in \mathbb{R}^{2 \times 48}$ and reconstructed output $\hat{\mathbf{X}} = \text{Model}(\mathbf{X}) \in \mathbb{R}^{2 \times 48}$:

### 5.1 Interval Reconstruction Error
The reconstruction error at half-hour interval $t \in \{1, \dots, 48\}$:
$$e_t = \frac{1}{2} \left[ (X_{0, t} - \hat{X}_{0, t})^2 + (X_{1, t} - \hat{X}_{1, t})^2 \right]$$

### 5.2 Max Daily Reconstruction Error
The peak anomalous error across the diurnal cycle:
$$e_{\text{max}} = \max_{t \in \{1, \dots, 48\}} e_t$$

---

## 6. Probability Calibration Protocol

### 6.1 Calibration Method: Platt Scaling
The raw reconstruction score is transformed into a calibrated attack probability using a logistic sigmoid over log-transformed reconstruction error:
$$p_t = \sigma(w \cdot \ln(e + \epsilon_{\text{log}}) + b) = \frac{1}{1 + \exp\left( - (w \cdot \ln(e + 10^{-12}) + b) \right)}$$

### 6.2 Fitted Parameters and Storage
- **Calibrator Artifact**: `Step 5/preflight/probability_calibrator.pkl`
- **Configuration & Coefficients**: `Step 5/preflight/calibration_config.json`
- **Fitted Parameters**: Recorded from empirical fitting on the designated calibration set (Days 305 to 424, containing both clean days and verified Phase 2 attack days).

### 6.3 Temporal Granularity Resolution
1. **Option A (Daily Probability)**:
   - Evaluates $e_{\text{max}}$ for the customer-day.
   - Computes daily probability $p_{\text{day}} = \sigma(w \cdot \ln(e_{\text{max}} + 10^{-12}) + b)$.
   - Associates $p_{i, t} = p_{i, \text{day}}$ for all $t \in \{0, \dots, 47\}$.
2. **Option B (Interval-Level Probability)**:
   - Evaluates $e_t$ for each 30-minute interval independently.
   - Computes interval probability $p_{i, t} = \sigma(w_{\text{int}} \cdot \ln(e_t + 10^{-12}) + b_{\text{int}})$.
3. **Recommendation for Economic Integration**:
   - The economic market clears every 30 minutes. Option B provides high-resolution, interval-specific targeting that minimizes false positive penalties during unattacked hours of an attacked day. Option A provides high diurnal detection sensitivity. Both calibrated models are serialized in `Step 5/preflight/`.

---

## 7. Mapping Between Customers, Dates, Time Indices, and Decisions

Every record produced by the inference engine exposes the unified market tuple:

```python
{
    "customer_id": int,          # {1, ..., 300} (299 unique prosumers)
    "date": str,                 # "YYYY-MM-DD"
    "time_index": int,           # 0 to 52,607 (global Ausgrid interval index)
    "half_hour_slot": int,       # 0 to 47 (interval within the 24-hour day)
    "raw_GC": float,             # Unscaled consumption (kWh)
    "raw_GG": float,             # Unscaled generation (kWh)
    "P_net": float,              # GC - GG (kWh); >0 = Buyer, <0 = Seller
    "reconstruction_error": float, # e_t or e_max
    "p_attack": float,           # Calibrated probability ∈ [0.0, 1.0]
    "attack_phase": str,         # Ground truth benchmark phase (eval only)
    "is_attacked_ground_truth": int # {0, 1} (eval only)
}
```

---

## 8. Missing-Value, Exception, and Edge-Case Handling

1. **Missing / Corrupted Telemetry**:
   If telemetry values contain `NaN` or negative energy readings ($GC < 0$ or $GG < 0$), values are clamped to $0.0$ via `np.nan_to_num()`.
2. **Division by Zero in Normalization**:
   If a prosumer has identical $\min$ and $\max$ (e.g., zero solar generation year-round), the epsilon $+10^{-6}$ prevents `ZeroDivisionError` and normalizes generation to $0.0$.
3. **Extreme Probability Saturation**:
   Calibrated probabilities are clipped to $[10^{-6}, 1 - 10^{-6}]$ to prevent infinite log-loss penalties in downstream expected-utility computations.
4. **Model Device Fallback**:
   Inference automatically executes on CUDA if available, falling back seamlessly to CPU with identical tensor mathematics.

---

## 9. Reproducibility and Audit Verification

All artifacts are deterministically reproducible with fixed seed `42`:
```bash
# 1. Rebuild Cache
python "Step 5/preflight/build_cache.py"

# 2. Train Detector
python "Step 5/preflight/train_detector.py"

# 3. Fit Calibrator
python "Step 5/preflight/calibrate_detector.py"

# 4. Compare Resolutions
python "Step 5/preflight/compare_temporal_resolution.py"

# 5. Run Smoke Test
python "Step 5/preflight/smoke_test.py"
```
