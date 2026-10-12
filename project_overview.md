# Project Overview: Cyber-Economic Resilience Under Evolving Attacks

## Central Research Question
*How can a data-local continual federated detector adapt to evolving FDIAs while translating uncertain cyber-threat predictions into economically resilient mitigation decisions in P2P energy markets?*

## Part 1: The Big Picture (What Are We Doing?)

Imagine a neighborhood with solar panels where neighbors trade energy directly with each other using a local digital market, tracked by smart meters.

**The Problem:** Hackers can break into these meters and inject fake numbers to steal money or cause power grid instability. We can't just send everyone's raw, second-by-second data to a central security server to check for hacks, because that violates consumer privacy. 

**Our Solution:** We investigate whether adaptive, privacy-aware cyber-threat detection translates into measurable economic resilience. Every smart meter gets a tiny AI brain that learns what "normal" looks like. Instead of sharing private data, the meters only share their "lessons learned" with a central server to build a master defense system. As hackers invent new attacks, the AI adapts. 

**The Key Twist (The Novelty):** Traditional AI just flags an anomaly and blocks it based on a fixed threshold. Our system is smarter. It produces an *attack probability*. It then looks at the current P2P energy market state (CDA) and asks: *"What is the financial cost of being wrong?"* It weighs the cost of a False Positive against a False Negative, and makes an **Economic-Aware Decision** to either allow or mitigate the trade, ultimately saving the neighborhood money.

---

## Part 2: Step-by-Step Project Flow (Controlled 2-Layer Experiment)

To ensure scientific rigor and make debugging easier, the project is strictly separated into two independent layers. The causal chain flows directly from one step to the next.

### Layer 1 — Cybersecurity & ML Adaptation
*(We validate this layer independently before touching the market simulator.)*

#### Step 1: Data Preparation & Evolving Attacks **[Cybersecurity]** — [✅ COMPLETED & FROZEN]
*   **Status:** Complete, empirically validated across 27 criteria, cryptographically hashed.
*   **Input:** Ausgrid Solar Home Electricity Dataset (Australia, 2010–2013).
*   **Action:** Generated an immutable, chronological evolving FDIA stream: Phase 1 (Normal) $\rightarrow$ Phase 2 (Scaling) $\rightarrow$ Phase 3 (Ramp) $\rightarrow$ Phase 4A (Replay) $\rightarrow$ Phase 4B (Coordinated collusion).
*   **Output:** 15,729,792 rows across 299 prosumers with 446,571 attacked observations (2.839% attack volume).
*   **Contribution 1:** A reproducible experimental framework for evaluating FDIA detection under temporally evolving attack distributions in heterogeneous P2P energy participants.

#### Step 2: The Local AI Defense (Anomaly Detection) **[AI]** — [✅ COMPLETED]
*   **Status:** Complete. Customer 1 local detector trained and evaluated; weights saved.
*   **Input:** 24-hour sliding windows of raw telemetry: $[GC_{\text{attacked}}, GG_{\text{attacked}}]$ with shape $[B, 2, 48]$.
*   **Action:** Trained a 1-D Convolutional Autoencoder exclusively on Phase 1 clean baseline (loss converged to $0.00129$). Sourced reconstruction errors across all 3 years and calibrated them into an attack probability $p_t \in [0, 1]$ via Platt scaling.
*   **Output:** Local model weights (`local_autoencoder_c1.pt`) and local baseline scorecard (F1: $13.25\%$, AUROC: $57.48\%$).
*   **Experiments & Baselines to Run:**
    *   **Single-Client Baseline (Customer 1):** Train and evaluate Customer 1 in complete isolation. *(Done: Achieved $13.25\%$ F1).*
    *   **Full Cohort Local Baseline (299 Local Models):** Train independent local models for all 299 prosumers and calculate the community's average Local F1 score to serve as the baseline comparison for Step 3.
    *   **Centralized AE (Upper Bound):** Pool all 299 prosumers' data into one central server and train a single model (breaks privacy, but defines the maximum theoretical detection ceiling).

#### Step 3: Privacy-Aware Collaboration (Federated Learning) **[AI] & [Cybersecurity]** — [✅ COMPLETED & EMPIRICALLY VERIFIED]
*   **Status:** Complete. Scaled to all 299 prosumers under a dual-protocol regime (Protocol A & Protocol B) with 3 model architectures, paired Wilcoxon hypothesis testing, and 16 IEEE publication figures (`Step 3/outputs/figures/`).
*   **Input:** Local model weights from smart meters across the community ($100\%$ data locality; $0$ bytes of raw consumer telemetry exchanged; $1.67\text{ GB}$ total 30-round community communication).
*   **Action:** Deployed Federated Averaging (FedAvg, 30 communication rounds, 1 local epoch/round) across all 299 prosumer nodes. Evaluated across three deep autoencoder architectures:
    1. `Conv-AE v1` ($4,418$ params) — Step 2 spatial ablation baseline.
    2. `FC-AE` ($17,712$ params) — Literature benchmark replication from Alshehri et al. (*Sensors* 2024).
    3. `Conv-AE v2` ($23,258$ params) — **Our proposed 1-D CNN with a 24-dimensional bottleneck (Ours)**.
*   **Dual Evaluation Protocols & Empirical Findings:**
    *   **Protocol B (Literature Benchmark SOTA Validation — WINNER)**:
        *   Evaluated on balanced 50/50 test sets against standard theft cyberattacks ($f_1$ to $f_6$) matching Alshehri et al. (2024, Table 2).
        *   **Replication of Paper B1 Baseline (`FC-AE`)**: Achieves **$85.40\%$ DR** and **$84.38\%$ F1**, faithfully reproducing published benchmark metrics ($85.51\%$ DR / $82.48\%$ F1).
        *   **Proposed Model (`Conv-AE v2`) Dominance**: Reaches **$92.46\%$ Detection Rate**, **$91.88\%$ Precision**, **$92.13\%$ F1-score**, **$92.11\%$ Accuracy**, and **$97.64\%$ AUROC**.
        *   **Decisive Margin Over Benchmark Paper**: **$+6.95\%$ DR**, **$+9.65\%$ F1**, **$+11.87\%$ Precision**, and False Alarm cut by over half ($8.24\%$ vs $17.17\%$).
        *   **Statistical Superiority ($p = 6.16 \times 10^{-47}$)**: Federated Conv-AE v2 beats Local defense on **$282 \text{ of } 299$ prosumers** with Wilcoxon significance.
        *   **Near-Zero Privacy Penalty**: Federated learning matches Centralized training ($92.13\%$ vs $92.61\%$ F1, gap $< 0.5$ pts) while keeping raw data strictly local.
    *   **Protocol A (Realistic Chronological Deployment — The Core Research Paradox)**:
        *   Evaluated chronologically across Years 2 & 3 on Step 1 Evolving FDIAs (natural ~10.8% attack prevalence; no future data leakage).
        *   Federated Conv-AE achieves $11.78\%$ F1, statistically outperforming Local defense on $176/299$ prosumers ($p = 4.10 \times 10^{-7}$).
        *   Exposes the critical blindspot of static autoencoders: detection drops on subtle ramps ($5.9\%$ DR) and collapses to $0.0\%$ DR on Phase 4A replay attacks (because authentic historical days produce valid waveforms).
*   **Scientific Contribution & Handoff to Step 4 & Step 5**:
    *   The empirical divergence between Protocol B ($92.1\%$ F1) and Protocol A ($11.8\%$ F1) proves that existing smart-grid literature lives in an artificial bubble of gross synthetic cuts.
    *   This establishes the fundamental scientific justification of our entire paper: static physical detectors cannot withstand stealthy evolving FDIAs alone, mandating **Step 4 (Continual Federated Learning)** to track non-stationary drifts and **Step 5 (Cyber-Economic Cross-Layer Verification)** to unmask replay and market collusion via P2P market clearing signals.
*   **Outputs & Deliverables:**
    *   Model checkpoints: `checkpoints/federated_conv2_A.pt`, `federated_conv2_B.pt`, `centralized_conv2_A.pt`, `centralized_conv2_B.pt`, `local_conv2_A.pt`, `local_conv2_B.pt`, `federated_fcae_B.pt`.
    *   Master reference dossier: [`Step 3/step_3_master_reference.md`](Step%203/step_3_master_reference.md).
    *   All 16 IEEE publication figures: [`Step 3/outputs/figures/`](Step%203/outputs/figures/) in vector `.pdf` and 300 DPI `.png`.
    *   CSV scorecards: `step3_summary.csv`, `step3_stats.csv`, `step3_phase_detection.csv`, `step3_per_customer_metrics.csv` (7,176 client evaluation rows).

#### Step 4: Adapting to New Threats (Continual Learning) **[AI]** — [⏳ NEXT]
*   **Input:** Successive chronological attack phases over the 3-year timeline (Scaling $\rightarrow$ Ramp $\rightarrow$ Replay $\rightarrow$ Coordinated).
*   **Action:** Equip clients with an episodic memory buffer (Experience Replay) to interleave historical samples into active batches, preventing parameter drift.
*   **Output:** An adaptive AI that masters new attack phases while maintaining high retention (eliminating catastrophic forgetting) on older attacks.
*   **Experiments to Run:**
    *   **Catastrophic Forgetting Test:** Compare **Static FedAvg** (no memory buffer; suffers amnesia as phases change) vs. **Continual FedAvg** (with Experience Replay) across all 4 phases to prove memory retention.

---

### Layer 2 — Economic Resilience
*(Connecting the ML performance directly to market outcomes.)*

#### Step 5: Economic-Aware Mitigation Decision **[Cybersecurity] & [Economics]**
*   **Input:** The Attack Probability ($p_t$) from Layer 1 + The Current Market State ($M_t$) from the CDA.
*   **Action:** Instead of a fixed threshold, the system calculates expected costs. It will MITIGATE if:
    `p_t * Cost(False Negative) > (1 - p_t) * Cost(False Positive) + Mitigation Cost`
*   **Output:** A final decision to ALLOW or MITIGATE the transaction.
*   **Experiments to Run (THE CORE NOVELTY TEST):**
    *   **Fixed Classification Threshold vs. Economic-Aware Decision:** Run the exact same calibrated probabilities $p_t$ through a standard fixed threshold vs. our economic expected-loss equation to prove that market-aware mitigation prevents costly false alarms.
*   **Contribution 2 (PRIMARY NOVELTY):** A decision layer that maps detector uncertainty and current market conditions to mitigation actions using expected downstream economic consequences.

#### Step 6: Economic Resilience Evaluation **[Economics]**
*   **Input:** The ALLOW/MITIGATE decisions.
*   **Action:** Feed decisions into a lightweight Continuous Double-Auction (CDA) market. If MITIGATE was selected, the market substitutes the manipulated bid with a conservative baseline.
*   **Output:** Empirical calculations of Energy Imbalance, Social Welfare, and Net Monetary Loss.
*   **Experiments & Sensitivity to Run:**
    *   **Market Welfare Calculation:** Measure how much total money the neighborhood saved under Continual Federated AI + Economic Mitigation vs. unmitigated attacks.
    *   **Cost Sensitivity Analysis:** Test cost ratios $C_{FN} / C_{FP} \in \{1\times, 5\times, 10\times, 20\times\}$ to prove the economic savings are stable across different tariff markets.
*   **Contributions 3 & 4:** A controlled framework connecting cyber-attacks to economic loss, and an empirical tradeoff analysis testing whether conventional AI metrics (F1) align with economic resilience.

---

## The "Killer Result" Goal
The paper will not end by simply stating "Our method achieves 94% F1". Instead, the goal is to tell a compelling cyber-economic story, such as:

> *"While Method A achieved a higher F1 score, our Economic-Aware Decision layer (Method B) produced significantly lower total market losses, because it strategically avoided costly false positives during volatile market states."*

This **tests whether** optimizing cyber-defense decisions according to downstream economic consequences can provide greater market resilience than conventional fixed-threshold detection.
