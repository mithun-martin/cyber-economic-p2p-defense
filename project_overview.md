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

#### Step 3: Privacy-Aware Collaboration (Federated Learning) **[AI] & [Cybersecurity]** — [✅ COMPLETED]
*   **Status:** Complete. Evaluated across all 299 prosumers under dual protocols (Protocol A & Protocol B) with 16 IEEE figures generated.
*   **Input:** Local model weights from smart meters across the community. *(Note: 100% data locality; 0 bytes of raw telemetry exchanged).*
*   **Action:** Deployed Federated Averaging (FedAvg). Virtual prosumer clients trained locally on their private smart meter readings, while the aggregation server coordinated weight averaging over 30 rounds.
*   **Output:** Global federated model weights (`federated_conv2_A.pt`, `federated_conv2_B.pt`), comprehensive client scorecard CSVs, and 16 IEEE publication-quality figures (`Step 3/outputs/figures/`).
*   **Empirical Findings Across All 299 Prosumers:**
    *   **Federated vs. Local Superiority ($p = 4.10 \times 10^{-7}$):** Federated Learning significantly outperforms isolated Local defense, winning on 176/299 prosumers in Protocol A ($p < 0.001$) and 162/299 in Protocol B ($p = 0.009$).
    *   **Near-Zero Privacy Penalty ($p = 0.601$):** Federated Learning matches the theoretical upper-bound Centralized model (13.39% vs 13.21% F1 in Protocol B) while completely preserving privacy.
    *   **Literature Discrepancy Revealed:** In balanced benchmark testing (Protocol B), precision reaches 57.20%, proving literature figures (~95%) stem from artificial 50/50 balanced test sets rather than realistic deployment (~10% attack prevalence).
    *   **Scientific Need for Step 4:** Static anomaly detection rates drop across evolving attack phases (8%–15%), establishing the critical empirical necessity for Step 4 (Continual Learning).

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
