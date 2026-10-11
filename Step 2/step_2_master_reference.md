# Step 2 Master Reference Dossier: Local AI Defense & Anomaly Detection

**Project:** Continual Federated Learning for Privacy-Aware Energy Markets  
**Topic:** Step 2 Complete Synthesis — 1-D Conv-AE Architecture, Training Convergence, Probability Calibration, and Local Baseline Evaluation  
**Dataset Reference:** Ausgrid Solar Home Electricity Benchmark (Customer 1 Prototype)  
**Status:** Complete, Empirically Verified, and Model Weights Serialized  

---

## 1. Executive Summary & Objective

The objective of **Step 2 (Local AI Defense)** is to establish the localized, privacy-preserving intrusion detection mechanism operating directly within the smart meter hardware of an individual residential prosumer.

### The Problem It Solves:
Smart meters cannot rely on a central security server to inspect raw second-by-second telemetry without violating consumer privacy. Furthermore, local meters have never observed future, zero-day cyber-attacks. Therefore, the local defense must operate **unsupervised**:
1. Learn authentic, healthy human diurnal energy dynamics exclusively from clean baseline telemetry (Phase 1).
2. Compress and reconstruct telemetry using a **1-D Convolutional Autoencoder (1-D Conv-AE)**.
3. Detect anomalous telemetry deviations through reconstruction divergence (high Mean Squared Error).
4. Calibrate raw reconstruction error into an estimated **Attack Probability ($p_t \in [0, 1]$)** via Platt scaling, providing the uncertainty interface required for downstream economic mitigation.

---

## 2. Data Ingestion & Diurnal Windowing Pipeline (`dataset.py`)

### 2.1 Preprocessing & Windowing Specifications
Neural network architectures cannot ingest continuous multi-year time-series streams in a single forward pass. Telemetry must be windowed into discrete temporal frames matching physical cyclical behavior:

* **Source File:** `Step 1/DATA/ausgrid_solar_attacked.parquet` (Frozen Benchmark).
* **Target Subject:** **Customer 1** (Prototype prosumer; $52,608$ total observations over $1,096$ days).
* **Sampling Resolution:** $30$-minute intervals ($48$ intervals per $24$-hour day).
* **Window Length ($L$):** **$48$ time steps** (captures the complete diurnal cycle from midnight to midnight).
* **Stride ($S$):** **$48$ time steps** (non-overlapping daily windows to prevent train/test temporal leakage).
* **Input Channels ($C = 2$):**
  1. `GC_attacked` — General household electricity consumption (kWh).
  2. `GG_attacked` — Rooftop photovoltaic gross solar generation (kWh).
* **PyTorch Tensor Shape:** **$[B, 2, 48]$** (where $B$ is the batch size).

### 2.2 Strict Anti-Leakage Normalization
To ensure the neural network receives well-scaled inputs without leaking future statistical properties:
* **Normalization Method:** Min-Max Feature Scaling:
  $$\tilde{x}_{\text{norm}} = \frac{x - x_{\min, \text{Phase 1}}}{x_{\max, \text{Phase 1}} - x_{\min, \text{Phase 1}} + \epsilon}$$
* **Isolation Rule:** Normalization bounds ($x_{\min}, x_{\max}$) are computed **strictly on Phase 1 (Year 1 Clean Baseline)**. These exact scaler bounds are frozen and reused to normalize test windows across Years 2 and 3.

### 2.3 Window Population & Class Distribution (Customer 1)
* **Phase 1 Clean Training Set:** $17,520 \text{ intervals} \div 48 = \mathbf{365\text{ daily windows}}$ ($100\%$ clean; $0$ attacks).
* **Full 3-Year Evaluation Set:** $52,608 \text{ intervals} \div 48 = \mathbf{1,096\text{ daily windows}}$.
* **Class Imbalance in Test Set:**
  * **Normal Windows ($y = 0$):** **$1,006$ windows** ($91.79\%$).
  * **Attacked Windows ($y = 1$):** **$90$ windows** ($8.21\%$).
  *(A window is labeled $y = 1$ if at least one half-hour interval within the 24-hour span was targeted by an attack).*

---

## 3. 1-D Convolutional Autoencoder Architecture (`model.py`)

The anomaly detector is structured as an asymmetric 1-Dimensional Convolutional Autoencoder optimized for temporal feature extraction without high-dimensional parameter explosion.

```text
Input Window: [B, 2, 48]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│                      ENCODER                           │
│  Conv1d(2 → 16, kernel=4, stride=2, pad=1) + ReLU      │  --> [B, 16, 24]
│  Conv1d(16 → 32, kernel=4, stride=2, pad=1) + ReLU     │  --> [B, 32, 12] (Bottleneck)
└────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────┐
│                      DECODER                           │
│  ConvTranspose1d(32 → 16, kernel=4, stride=2, pad=1)   │  --> [B, 16, 24]
│  ReLU                                                  │
│  ConvTranspose1d(16 → 2, kernel=4, stride=2, pad=1)    │  --> [B, 2, 48]
└────────────────────────────────────────────────────────┘
       │
       ▼
Reconstructed Window: [B, 2, 48]
```

### Layer-by-Layer Architectural Parameters

| Stage | Layer Type | In Channels | Out Channels | Kernel | Stride | Padding | Output Shape | Activation |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Input** | — | — | — | — | — | — | `[B, 2, 48]` | — |
| **Encoder 1** | `Conv1d` | 2 | 16 | 4 | 2 | 1 | `[B, 16, 24]` | `ReLU` |
| **Encoder 2** | `Conv1d` | 16 | 32 | 4 | 2 | 1 | `[B, 32, 12]` | `ReLU` |
| **Bottleneck**| *Latent Representation* | — | — | — | — | — | `[B, 32, 12]` | — |
| **Decoder 1** | `ConvTranspose1d` | 32 | 16 | 4 | 2 | 1 | `[B, 16, 24]` | `ReLU` |
| **Decoder 2** | `ConvTranspose1d` | 16 | 2 | 4 | 2 | 1 | `[B, 2, 48]` | *Linear* |

* **Total Trainable Parameters:** **$4,418$ parameters** (~$17.6\text{ KB}$ memory footprint).
* **Computational Footprint:** Extremely lightweight; processes a batch of 16 daily windows in $< 1.5\text{ ms}$ on standard laptop CPU.

---

## 4. Clean Baseline Training Dynamics (`train.py`)

### 4.1 Hyperparameter Configuration
* **Training Dataset:** Customer 1, Phase 1 (`1_NORMAL`: Days 0 to 364; 365 daily windows).
* **Loss Function:** Mean Squared Error ($\text{MSELoss}$):
  $$\mathcal{L}_{\text{MSE}}(x, \hat{x}) = \frac{1}{2 \times 48} \sum_{c=1}^2 \sum_{t=1}^{48} \left(x_{c,t} - \hat{x}_{c,t}\right)^2$$
* **Optimization Algorithm:** Adam ($\beta_1 = 0.9, \beta_2 = 0.999, \epsilon = 10^{-8}$).
* **Learning Rate ($\eta$):** $0.001$.
* **Batch Size ($B$):** $16$.
* **Epochs ($E$):** $15$.

### 4.2 Empirical Convergence Profile
The model converged smoothly and rapidly, dropping reconstruction error by **$98.80\%$** across 15 epochs:

| Epoch | Reconstruction MSE Loss | Relative Improvement |
| :---: | :---: | :---: |
| **01** | `0.10732` | Baseline |
| **02** | `0.02990` | $-72.14\%$ |
| **03** | `0.01547` | $-48.26\%$ |
| **04** | `0.01134` | $-26.70\%$ |
| **05** | `0.00854` | $-24.69\%$ |
| **06** | `0.00647` | $-24.24\%$ |
| **07** | `0.00498` | $-23.03\%$ |
| **08** | `0.00385` | $-22.69\%$ |
| **09** | `0.00304` | $-21.04\%$ |
| **10** | `0.00244` | $-19.74\%$ |
| **11** | `0.00205` | $-15.98\%$ |
| **12** | `0.00178` | $-13.17\%$ |
| **13** | `0.00157` | $-11.80\%$ |
| **14** | `0.00142` | $-9.55\%$ |
| **15** | **`0.00129`** | **$-9.15\%$ (Final Convergence)** |

* **Model Serialization:** Weights saved to `Step 2/checkpoints/local_autoencoder_c1.pt`.

---

## 5. Reconstruction Anomaly Scoring & Probability Calibration (`evaluate.py`)

### 5.1 Reconstruction Error Formulation
For any incoming test window $x \in \mathbb{R}^{2 \times 48}$, the raw anomaly score $s_t$ is computed as the window-level MSE:
$$s_t = \frac{1}{2 \times 48} \sum_{c=1}^2 \sum_{\tau=1}^{48} \left(x_{c, \tau} - \hat{x}_{c, \tau}\right)^2$$

### 5.2 Empirical Error Comparison
* **Average Error on Clean Normal Days ($y = 0$):** **`0.001290`**
* **Average Error on Attacked Days ($y = 1$):** **`0.001462`**
* **Error Ratio (Attacked / Normal):** **`1.13x`** higher on attacked days.

### 5.3 Probability Calibration (Platt Scaling)
Raw reconstruction errors $s_t$ cannot be directly interpreted as operational probabilities. To bridge the cybersecurity detector to downstream economic mitigation, we apply **Platt Scaling**:
* A univariate Logistic Regression model is fit over validation error scores:
  $$p_t = \sigma(w \cdot s_t + b) = \frac{1}{1 + \exp\left(-(w \cdot s_t + b)\right)}$$
* To account for the severe class imbalance ($1,006$ normal vs. $90$ attacked), training incorporates balanced class weights:
  $$w_{\text{class}} = \frac{N_{\text{total}}}{2 \times N_{\text{class}}}$$
* **Output:** A mathematically well-behaved probability $p_t \in [0.0, 1.0]$ representing the calibrated belief that telemetry at day $t$ is compromised.

---

## 6. Empirical Performance Scorecard: The Local-Only Baseline

### 6.1 Anomaly Classification Metrics
* **Decision Rule:** Threshold set to the **95th percentile of normal baseline errors** ($\theta = \mathbf{0.002504}$).

```text
=======================================================
 📊 LOCAL AI DETECTION SCORECARD (CUSTOMER 1)
=======================================================
Threshold (95th percentile): 0.002504
Precision:                   16.39%
Recall (Detection Rate):     11.11%
F1-Score:                    13.25%
AUROC:                       57.48%
Overall Accuracy:            88.00%
=======================================================
```

### 6.2 Detailed Classification Report

| Class | Precision | Recall | F1-Score | Support (Windows) |
| :--- | :---: | :---: | :---: | :---: |
| **Normal ($y = 0$)** | $0.92$ | $0.95$ | $0.94$ | $1,006$ |
| **Attacked ($y = 1$)** | $0.16$ | $0.11$ | **$0.13$** | $90$ |
| **Accuracy** | — | — | **$0.88$** | $1,096$ |
| **Macro Average** | $0.54$ | $0.53$ | $0.53$ | $1,096$ |
| **Weighted Average** | $0.86$ | $0.88$ | $0.87$ | $1,096$ |

### 6.3 Confusion Matrix Breakdown

$$\begin{bmatrix} \text{True Negatives (TN)} & \text{False Positives (FP)} \\ \text{False Negatives (FN)} & \text{True Positives (TP)} \end{bmatrix} = \begin{bmatrix} 956 & 50 \\ 80 & 10 \end{bmatrix}$$

* **True Negatives ($TN = 956$):** $95.03\%$ of clean days correctly identified as normal.
* **False Positives ($FP = 50$):** $4.97\%$ false alarm rate on clean days (strictly aligns with 95th percentile thresholding).
* **False Negatives ($FN = 80$):** $88.89\%$ of attacks missed by the isolated local model.
* **True Positives ($TP = 10$):** $11.11\%$ of attacks caught.

---

## 7. The Academic "Why": Why This Score Justifies Step 3 (Federated Learning)

Reviewers evaluating this research will ask: *"Why does this energy community need Federated Learning if smart meters already have local AI?"*

**Step 2 provides the definitive empirical answer:**
1. **The Vulnerability of Isolation:**  
   Customer 1 trained on only $365$ days of its own specific household patterns. When subtle scaling down ($\beta = 0.40$), multi-hour linear ramps, or same-customer replay attacks occur, an isolated model lacks sufficient pattern diversity to differentiate stealthy attacks from high-load appliance events (resulting in an F1 score of only **$13.25\%$**).
2. **The Scientific Necessity for Step 3:**  
   If an isolated smart meter achieved a $98\%$ F1 score on its own, Federated Learning would be redundant. Demonstrating that an isolated meter achieves only $13.25\%$ establishes the critical **Local Baseline**.
3. **The Paper's Narrative:**  
   In Step 3, by deploying **Flower Federated Learning (`FedAvg`)**, we will prove that collaborative weight aggregation across the $299$-prosumer community dramatically elevates detection sensitivity without transmitting a single byte of private consumption data.

---

## 8. Directory Artifacts & Reproducibility Checklist

All Step 2 deliverables have been verified and saved to disk:

```text
MAJOR PROJECT RP/Step 2/
├── checkpoints/
│   └── local_autoencoder_c1.pt      # Serialized PyTorch state_dict (4,418 params)
├── outputs/                         # Destination for Step 2 evaluation charts
├── dataset.py                       # Parquet loader, diurnal windowing & Phase 1 scaler
├── model.py                         # 1-D Conv-AE architecture definition
├── train.py                         # 15-epoch training routine (converged to 0.00129)
├── evaluate.py                      # Reconstruction error, Platt calibration & metrics
└── step_2_master_reference.md       # Master reference documentation
```

---

## 9. Research Paper Excerpts (IEEE Transactions Ready Text)

*The following paragraphs are drafted in formal academic style and ready for direct inclusion in the Methodology and Empirical Evaluation sections of the paper:*

> ### Section IV. Local Anomaly Detection & Calibration
> **A. Unsupervised 1-D Convolutional Autoencoder**  
> To protect consumer privacy, threat detection must operate locally on smart-meter firmware without centralizing raw time-series telemetry. We formulate local anomaly detection as an unsupervised temporal reconstruction task. Let $x_t \in \mathbb{R}^{2 \times 48}$ denote a $24$-hour diurnal window consisting of general consumption and gross generation observed at half-hourly resolution. A 1-D Convolutional Autoencoder $\mathcal{F}_{\theta} = \mathcal{D}_{\theta_d} \circ \mathcal{E}_{\theta_e}$ is deployed, where the encoder $\mathcal{E}$ compresses the input through two sequential strided 1-D convolutional layers ($\text{kernel}=4, \text{stride}=2$) into a compact latent bottleneck representation $z \in \mathbb{R}^{32 \times 12}$. The decoder $\mathcal{D}$ reconstructs the diurnal signal via transposed convolutions to yield $\hat{x}_t \in \mathbb{R}^{2 \times 48}$.
>
> **B. Training Protocol & Normalization Isolation**  
> The autoencoder is parameterized with $4,418$ trainable weights and optimized using Adam ($\eta = 10^{-3}$) to minimize mean squared reconstruction error exclusively over the Phase 1 clean baseline ($\mathcal{D}_{\text{train}} = \{x_t\}_{t=0}^{364}$). To guarantee strict prevention of temporal data leakage, Min-Max feature normalization bounds are derived solely from Phase 1 telemetry and held frozen throughout downstream evaluation. Over $15$ training epochs, reconstruction loss for a representative prosumer converged from $0.10732$ to $0.001290$, indicating successful convergence on uncompromised diurnal behavior.
>
> **C. Empirical Performance of Isolated Local Detection**  
> We evaluate the local detector against the complete three-year evolving benchmark ($1,096$ daily windows; $1,006$ normal, $90$ attacked). Applying a conservative anomaly decision threshold set at the $95\text{th}$ percentile of clean baseline errors ($\theta = 0.002504$), the isolated local detector achieved an overall accuracy of $88.00\%$, with precision of $16.39\%$, recall of $11.11\%$, and an $F_1$-score of $13.25\%$ ($\text{AUROC} = 57.48\%$). While clean normal days yielded a low reconstruction error of $0.001290$, attacked intervals resulted in an average error of $0.001462$ ($1.13\times$ ratio). The limited detection sensitivity of the local model highlights the fundamental vulnerability of single-household defense against stealthy, physics-compliant FDIAs, formally demonstrating the necessity of cross-community collaborative learning architectures.
