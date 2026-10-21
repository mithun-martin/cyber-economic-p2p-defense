# Paper-Writing Checklist & Execution Workflow

**Project**: Cyber-Economic Resilience Under Evolving Attacks in Peer-to-Peer Energy Markets  
**Target Output**: Master's Thesis / Peer-Reviewed Conference or Journal Manuscript  
**Companion Artifact**: [`PAPER_CLAIMS_AND_EVIDENCE_REGISTER.csv`](PAPER_CLAIMS_AND_EVIDENCE_REGISTER.csv)  
**Main Reference**: [`RESEARCH_HANDOFF_FOR_PAPER_WRITING.md`](RESEARCH_HANDOFF_FOR_PAPER_WRITING.md)  

---

## Stage 1: Research Onboarding & Scope Alignment
- [x] Read `RESEARCH_HANDOFF_FOR_PAPER_WRITING.md` end-to-end to understand system architecture and experimental design.
- [x] Review the 671-day simulation scope: Test Days 425 to 1095, 299 prosumers, 48 slots/day, 128,832 total trading sessions.
- [x] Understand the distinction between Layer 1 (Cybersecurity ML Detection) and Layer 2 (Economic CDA Market Clearing).
- [x] Internalize the core finding: Anomaly detector is weak (AUROC ~0.5237); selective mitigation (Regime C) is an operational heuristic dominated by false alarms (95.5% of mitigations), yet successfully curtails 73.51% of cleared corrupt energy while retaining 81.76% of clean P2P gross tariff surplus.
- [x] Understand the critical settlement accounting rule: Simulated net grid settlement (-$79.22k) is an unmetered demand truncation artifact, NOT physical electricity bill savings. Under fixed physical load/supply, prosumers' net physical grid purchases increase by +$9,024.06 (+1.43%).

---

## Stage 2: Literature Review & Novelty Positioning
- [ ] Conduct a structured literature search on False Data Injection Attacks (FDIAs) in P2P energy trading and transactive energy microgrids (2020–2026).
- [ ] Identify top 5 benchmark papers investigating cybersecurity in Continuous Double Auctions (e.g., IEEE Trans. Smart Grid, IEEE Trans. Industrial Informatics, Applied Energy).
- [ ] Determine how prior work handles detection errors in market clearing (do they assume perfect detection, or evaluate economic resilience under false alarms?).
- [ ] Define the paper's exact novelty claim: "First longitudinal (671-day) empirical evaluation of how imperfect ML intrusion detection and median fallback substitution interact with Continuous Double Auction liquidity, tariff surplus, and dual-settlement grid accounting."
- [ ] Verify that no text claims "state-of-the-art detector superiority" unless backed by direct comparative tables against published models.
- [ ] Select target publication venue (e.g., IEEE Transactions on Sustainable Energy, IEEE Transactions on Smart Grid, ACM e-Energy, or IEEE PES General Meeting) and download author formatting template.

---

## Stage 3: Claims and Evidence Audit
- [x] Audit all prospective paper claims against `PAPER_CLAIMS_AND_EVIDENCE_REGISTER.csv`.
- [x] Ensure every numerical value cited in the text originates from verified output CSVs (`step6_3_1_corrected_aggregate_summary.csv` or `step6_3_1_corrected_regime_c_detector_diagnostics.csv`).
- [ ] Confirm no claims assert "the detector is highly accurate" or "production-ready."
- [ ] Confirm no claims state "attacks increase real social welfare" based on Regime A's 100.61% retention ratio.
- [ ] Confirm no claims describe the AUD 79,217.54 simulated settlement reduction as "consumer bill savings."
- [ ] Ensure the attribution-based nature of `corrupted_raw_energy_cleared_kWh` is explicitly documented alongside its causal limits (order displacement).

---

## Stage 4: Methodology and Threat Model Formulation
- [ ] Formalize the threat model: 4-phase evolving FDIA (Normal, Scaling, Ramp, Replay, Coordinated) attacking `GC`, `GG`, or both, with 20% prosumer penetration.
- [ ] Document the data pipeline: Ausgrid 300-household dataset, exclusion of Customer 2 (81 days missing), contiguous 299-customer cohort.
- [ ] Detail the detector architecture: 1-D Convolutional Autoencoder (`ConvAE_v2`, 4,418 parameters, 48-slot diurnal window) trained strictly on clean Phase 1 (Days 0–364).
- [ ] Specify probability calibration: Balanced Platt scaling ($w_{\text{bal}} = 0.07566, b_{\text{bal}} = 0.50988$) on interval MSE feature $\ln(\text{MSE} + 10^{-12})$.
- [ ] Formulate the CDA market mechanism: Continuous Double Auction, price-time priority, midpoint execution pricing, retail import tariff $G_T = \$0.30/\text{kWh}$, feed-in tariff $\text{FiT} = \$0.08/\text{kWh}$, deadband $\epsilon = 10^{-4}\text{ kWh}$.
- [ ] Document the locked pairing protocol: Common random numbers (CRN) for arrival permutations and 2D customer-level valuations, ensuring cross-regime variance reduction.

---

## Stage 5: Results, Tables, and Figures Preparation
- [ ] Generate Figure 1: End-to-end cyber-economic architecture flowchart (Layer 1 Detection $\to$ Fallback Substitution $\to$ Layer 2 CDA Order Book $\to$ Dual-Settlement Accounting).
- [ ] Generate Figure 2: Chronological 1,096-day attack timeline showing the 4 evolving phases and the 671-day test evaluation partition.
- [ ] Generate Table 1: Comprehensive market outcomes across the four regimes (Clean, Regime A, Regime B, Regime C) directly from `step6_3_1_corrected_aggregate_summary.csv`.
- [ ] Generate Table 2: Authoritative confusion matrix and detection diagnostics on the 9,630,192 test customer-intervals directly from `step6_3_1_corrected_regime_c_detector_diagnostics.csv`.
- [ ] Generate Figure 3: Daily time-series plot comparing daily P2P matched volume and cleared corrupted energy across regimes.
- [ ] Generate Table 3: Settlement accounting comparison table explicitly contrasting simulated market residual settlement against the physical-grid counterfactual.
- [ ] Verify all table column headers use corrected names (`unit_tariff_surplus_aud_per_kwh`, `volume_weighted_vwap_aud_per_kwh`, etc.).

---

## Stage 6: Limitations and Threats to Validity
- [ ] Draft dedicated Limitations section addressing:
  - Single-dataset evaluation (Ausgrid Sydney cohort; climate and solar profile specificity).
  - Synthetic attack generation (mathematical FDI models vs. live Advanced Persistent Threats).
  - Unsupervised autoencoder discrimination limits (AUROC 0.5237; inability to reliably separate peak usage from scaling attacks).
  - High false alarm rate (95.5% of mitigations are false alarms under $\tau=0.50$).
  - Historical median fallback bias (underestimates peak solar generation and suppresses midday P2P liquidity).
  - Flat tariff structure (no time-of-use pricing, critical peak pricing, or capacity charges).
  - Unconstrained copper-plate network assumption (no AC power flow solving, line loss, or transformer congestion modeling).
  - Inelastic physical counterfactual assumption (no demand response or battery energy storage modeled).

---

## Stage 7: Manuscript Writing and Terminology Harmonization
- [ ] Draft Results section focusing on the fundamental trade-off: Security protection (Regime B eliminates 100% of corrupt trades; Regime C curtails 73.51%) vs. Economic efficiency (Regime B loses 20.47% welfare; Regime C loses 18.24% welfare).
- [ ] Draft Discussion section highlighting the policy insight: Imperfect intrusion detection causes substantial collateral economic damage in P2P markets through false alarms, which can exceed the direct physical damage of the attack itself.
- [ ] Draft Introduction section establishing the tension between decentralized transactive energy and smart meter vulnerability.
- [ ] Ensure strict terminology separation:
  - "Gross P2P tariff surplus" ($W_{\text{P2P}} = 0.22 \times E_{\text{P2P}}$) vs. "Social welfare."
  - "Simulated market residual settlement" vs. "Physical grid bill."
  - "Attribution-based cleared volume" vs. "Causal attack harm."
- [ ] Draft Abstract and Conclusion summarizing empirical findings, trade-offs, and future research directions.

---

## Stage 8: Reproducibility & Integrity Verification
- [x] Verify benchmark Parquet SHA-256 hash: `176fa03152359472b544f2197427bca92f51127e4c2becad84e31ec72f6ca1b4`.
- [x] Verify detector checkpoint SHA-256 hash: `85e68a1b1da058cecf56829279e2af42872656e797581e81170f2f712f9fbbf2`.
- [x] Verify probability calibrator SHA-256 hash: `81f70abbe29e775ea064e5fd4c46858bcb158f0fdd93a2b0014627742ac4a158`.
- [x] Verify that daily summary sums reproduce aggregate totals across all 12 columns to within $10^{-11}$.
- [x] Verify that all 10 smoke-test and evaluation invariants (CHK-01 to CHK-10) pass.
- [ ] Verify that software environment details in the paper match `step6_3_run_manifest.json` (Python 3.14.7, Linux-7.2.3 CachyOS, PyTorch 2.13.0+cu130, RTX 4050 GPU).
- [ ] Confirm code repository is cleanly organized with instructions for running verification scripts.

---

## Stage 9: Final Author Review & Submission Package
- [ ] Conduct word-by-word number audit matching every sentence in the draft against `PAPER_CLAIMS_AND_EVIDENCE_REGISTER.csv`.
- [ ] Verify all citations are genuine, peer-reviewed, and accurately reflect cited authors' findings.
- [ ] Verify that all co-authors have reviewed and approved the paper-facing wording and claims register.
- [ ] Prepare supplementary material document containing full invariant audit logs and mathematical proofs.
- [ ] Compile manuscript PDF using journal LaTeX template and perform visual formatting inspection.
- [ ] Submit package to target venue.
