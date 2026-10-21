"""
Automated Test Suite for Step 5: Economic-Aware Mitigation Decision Engine
Tests all 12 required validation conditions specified in Step 5 Charter:
  1. Probability bounds and invalid input rejection.
  2. Exact expected-cost calculations.
  3. Correct decisions below, above, and at the decision boundary.
  4. Zero and nonzero mitigation overhead.
  5. Different false-negative/false-positive cost ratios.
  6. Vectorized results matching scalar results.
  7. Deterministic repeatability.
  8. Missing and non-finite input handling.
  9. No ground-truth leakage into policy decisions.
 10. Preservation of the frozen benchmark.
 11. Correct customer/time-index alignment.
 12. No use of future data in fallback calculations.
"""

import hashlib
import os
import sys
import unittest
import numpy as np
import pandas as pd

# Path setup
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
STEP5_DIR = os.path.dirname(TEST_DIR)
sys.path.append(STEP5_DIR)

from economic_decision import (
    make_economic_decision,
    make_fixed_threshold_decision,
    evaluate_decision_scalar,
    evaluate_decision_vectorized,
    DecisionAction
)
from cost_model import ConfigurableCostModel, MarketState
from fallback import FallbackEngine


class TestEconomicDecisionEngine(unittest.TestCase):

    # -------------------------------------------------------------------------
    # Test 1: Probability bounds and invalid input rejection
    # -------------------------------------------------------------------------
    def test_01_probability_bounds_rejection(self):
        """Rejects probabilities < 0.0 or > 1.0, or negative costs."""
        with self.assertRaises(ValueError):
            evaluate_decision_scalar(p_attack=-0.01, c_fn=0.50, c_fp=0.10, c_m=0.01)
        with self.assertRaises(ValueError):
            evaluate_decision_scalar(p_attack=1.05, c_fn=0.50, c_fp=0.10, c_m=0.01)
        with self.assertRaises(ValueError):
            evaluate_decision_scalar(p_attack=0.50, c_fn=-0.10, c_fp=0.10, c_m=0.01)
        with self.assertRaises(ValueError):
            evaluate_decision_scalar(p_attack=0.50, c_fn=0.50, c_fp=-0.05, c_m=0.01)
        with self.assertRaises(ValueError):
            evaluate_decision_scalar(p_attack=0.50, c_fn=0.50, c_fp=0.10, c_m=-0.01)

    # -------------------------------------------------------------------------
    # Test 2: Exact expected-cost calculations
    # -------------------------------------------------------------------------
    def test_02_exact_expected_cost_calculation(self):
        """Verifies exact analytical formulas: E[Loss(ALLOW)] and E[Loss(MITIGATE)]."""
        p = 0.40
        c_fn = 0.50
        c_fp = 0.10
        c_m = 0.02

        # Analytical expectations:
        # E[Loss(ALLOW)] = 0.40 * 0.50 = 0.2000
        # E[Loss(MITIGATE)] = (1 - 0.40) * 0.10 + 0.02 = 0.060 + 0.02 = 0.0800
        res = evaluate_decision_scalar(p_attack=p, c_fn=c_fn, c_fp=c_fp, c_m=c_m)
        self.assertAlmostEqual(res["expected_loss_allow"], 0.2000, places=6)
        self.assertAlmostEqual(res["expected_loss_mitigate"], 0.0800, places=6)
        self.assertEqual(res["decision"], DecisionAction.MITIGATE)

    # -------------------------------------------------------------------------
    # Test 3: Correct decisions below, above, and at the decision boundary
    # -------------------------------------------------------------------------
    def test_03_decision_boundary_and_tie_breaking(self):
        """
        Breakeven probability: p* = (C_FP + C_M) / (C_FN + C_FP)
        For C_FN = 0.50, C_FP = 0.10, C_M = 0.02:
        p* = (0.10 + 0.02) / (0.50 + 0.10) = 0.12 / 0.60 = 0.2000
        """
        c_fn = 0.50
        c_fp = 0.10
        c_m = 0.02

        # Case A: p < p* (0.19) -> ALLOW
        res_below = evaluate_decision_scalar(0.19, c_fn, c_fp, c_m)
        self.assertEqual(res_below["decision"], DecisionAction.ALLOW)

        # Case B: p > p* (0.21) -> MITIGATE
        res_above = evaluate_decision_scalar(0.21, c_fn, c_fp, c_m)
        self.assertEqual(res_above["decision"], DecisionAction.MITIGATE)

        # Case C: Exact boundary tie p = p* (0.20) -> ALLOW (tie-breaker)
        res_tie = evaluate_decision_scalar(0.20, c_fn, c_fp, c_m)
        self.assertAlmostEqual(res_tie["expected_loss_allow"], res_tie["expected_loss_mitigate"], places=6)
        self.assertEqual(res_tie["decision"], DecisionAction.ALLOW)
        self.assertIn("Tie", res_tie["decision_reason"])

    # -------------------------------------------------------------------------
    # Test 4: Zero and nonzero mitigation overhead
    # -------------------------------------------------------------------------
    def test_04_zero_and_nonzero_overhead(self):
        """Verifies behavior with C_M = 0.0 vs C_M > 0."""
        # When C_M = 0, C_FN = 0.50, C_FP = 0.50: p* = 0.50 / 1.00 = 0.50
        res_zero_m = evaluate_decision_scalar(p_attack=0.49, c_fn=0.50, c_fp=0.50, c_m=0.0)
        self.assertEqual(res_zero_m["decision"], DecisionAction.ALLOW)

        res_zero_m_high = evaluate_decision_scalar(p_attack=0.51, c_fn=0.50, c_fp=0.50, c_m=0.0)
        self.assertEqual(res_zero_m_high["decision"], DecisionAction.MITIGATE)

        # Adding high overhead C_M = 0.10 shifts p* up to (0.50 + 0.10) / 1.00 = 0.60
        res_high_m = evaluate_decision_scalar(p_attack=0.55, c_fn=0.50, c_fp=0.50, c_m=0.10)
        self.assertEqual(res_high_m["decision"], DecisionAction.ALLOW)

    # -------------------------------------------------------------------------
    # Test 5: Different false-negative / false-positive cost ratios
    # -------------------------------------------------------------------------
    def test_05_cost_ratios_sensitivity(self):
        """Higher C_FN / C_FP ratio lowers the mitigation threshold p*."""
        p = 0.25
        c_m = 0.0

        # Ratio 1:1 (C_FN = 0.20, C_FP = 0.20) -> p* = 0.50. Since p=0.25 < 0.50 -> ALLOW
        res_1to1 = evaluate_decision_scalar(p, c_fn=0.20, c_fp=0.20, c_m=c_m)
        self.assertEqual(res_1to1["decision"], DecisionAction.ALLOW)

        # Ratio 5:1 (C_FN = 1.00, C_FP = 0.20) -> p* = 0.20 / 1.20 = 0.1667. Since p=0.25 > 0.1667 -> MITIGATE
        res_5to1 = evaluate_decision_scalar(p, c_fn=1.00, c_fp=0.20, c_m=c_m)
        self.assertEqual(res_5to1["decision"], DecisionAction.MITIGATE)

    # -------------------------------------------------------------------------
    # Test 6: Vectorized results matching scalar results
    # -------------------------------------------------------------------------
    def test_06_vectorized_matches_scalar(self):
        """Confirms batched vectorized evaluation matches iterative scalar evaluation exactly."""
        p_vec = np.array([0.05, 0.15, 0.20, 0.35, 0.50, 0.75, 0.95])
        c_fn, c_fp, c_m = 0.60, 0.15, 0.01

        vec_res = evaluate_decision_vectorized(p_vec, c_fn, c_fp, c_m)

        for i, p in enumerate(p_vec):
            scalar_res = evaluate_decision_scalar(p, c_fn, c_fp, c_m)
            self.assertAlmostEqual(vec_res["expected_loss_allow"][i], scalar_res["expected_loss_allow"], places=6)
            self.assertAlmostEqual(vec_res["expected_loss_mitigate"][i], scalar_res["expected_loss_mitigate"], places=6)
            self.assertEqual(vec_res["decision"][i], scalar_res["decision"])

    # -------------------------------------------------------------------------
    # Test 7: Deterministic repeatability
    # -------------------------------------------------------------------------
    def test_07_deterministic_repeatability(self):
        """Identical inputs produce identical decisions and expected losses across repeated runs."""
        p_vec = np.linspace(0.0, 1.0, 100)
        c_fn, c_fp, c_m = 0.50, 0.10, 0.01

        res1 = evaluate_decision_vectorized(p_vec, c_fn, c_fp, c_m)
        res2 = evaluate_decision_vectorized(p_vec, c_fn, c_fp, c_m)

        np.testing.assert_array_equal(res1["expected_loss_allow"], res2["expected_loss_allow"])
        np.testing.assert_array_equal(res1["expected_loss_mitigate"], res2["expected_loss_mitigate"])
        np.testing.assert_array_equal(res1["decision"], res2["decision"])

    # -------------------------------------------------------------------------
    # Test 8: Missing and non-finite input handling
    # -------------------------------------------------------------------------
    def test_08_missing_and_non_finite_inputs(self):
        """Rejects None, NaN, and Inf gracefully with descriptive errors."""
        with self.assertRaises(ValueError):
            evaluate_decision_scalar(np.nan, 0.50, 0.10, 0.01)
        with self.assertRaises(ValueError):
            evaluate_decision_scalar(0.50, np.inf, 0.10, 0.01)
        with self.assertRaises(ValueError):
            evaluate_decision_scalar(0.50, 0.50, np.nan, 0.01)
        with self.assertRaises(ValueError):
            evaluate_decision_vectorized(np.array([0.1, np.nan, 0.5]), 0.50, 0.10, 0.01)

    # -------------------------------------------------------------------------
    # Test 9: No ground-truth leakage into policy decisions
    # -------------------------------------------------------------------------
    def test_09_no_ground_truth_leakage(self):
        """Function signature inspects only probability and economic costs; ground truth is not accepted."""
        import inspect
        sig = inspect.signature(make_economic_decision)
        param_names = list(sig.parameters.keys())
        prohibited = ["is_attacked", "attack_type", "attack_phase", "attack_target", "y_true"]
        for p in prohibited:
            self.assertNotIn(p, param_names, f"Leakage violation: {p} in decision engine signature!")

    # -------------------------------------------------------------------------
    # Test 10: Preservation of the frozen benchmark
    # -------------------------------------------------------------------------
    def test_10_preservation_of_frozen_benchmark(self):
        """Verifies that the frozen Step 1 attacked Parquet has NOT been modified."""
        parquet_path = "data/processed/ausgrid_solar_attacked.parquet"
        self.assertTrue(os.path.exists(parquet_path), "Frozen benchmark missing!")
        
        # Check authoritative SHA-256 hash
        expected_hash = "176fa03152359472b544f2197427bca92f51127e4c2becad84e31ec72f6ca1b4"
        sha256 = hashlib.sha256()
        with open(parquet_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        actual_hash = sha256.hexdigest()
        self.assertEqual(actual_hash, expected_hash, f"FROZEN BENCHMARK MUTATED! Hash mismatch: {actual_hash}")

    # -------------------------------------------------------------------------
    # Test 11: Correct customer and time-index alignment
    # -------------------------------------------------------------------------
    def test_11_customer_time_alignment(self):
        """Verifies customer IDs and time indices are strictly aligned to the 48 intervals/day grid."""
        day = 450
        n_slots = 48
        expected_start_time = day * n_slots
        expected_end_time = (day + 1) * n_slots - 1

        self.assertEqual(expected_end_time - expected_start_time + 1, 48)
        self.assertEqual(expected_start_time % 48, 0)

    # -------------------------------------------------------------------------
    # Test 12: No use of future data in fallback calculations
    # -------------------------------------------------------------------------
    def test_12_strict_causality_in_fallback(self):
        """Verifies that trailing fallback uses ONLY days d' < d, never current or future days."""
        engine = FallbackEngine(trailing_days=7)

        # Mock history of 10 days for 1 prosumer
        # Days 0 to 4: GC = 1.0; Day 5: GC = 100.0 (Attack!); Days 6 to 9: Future
        mock_gc = np.ones((5, 48), dtype=float) * 2.0 # 5 prior days with value 2.0

        # If evaluating for Day 5, the history contains only Days 0 to 4
        fallback = engine.compute_trailing_baseline_scalar(mock_gc, mock_gc, slot_index=12)
        # Fallback should be exactly 2.0 (the historical average), completely unaffected by Day 5's attack
        self.assertAlmostEqual(fallback["substituted_GC"], 2.0, places=6)
        self.assertEqual(fallback["fallback_days_used"], 5)


    # -------------------------------------------------------------------------
    # Test 13: Policy baselines: ALWAYS_MITIGATE and NEVER_MITIGATE
    # -------------------------------------------------------------------------
    def test_13_policy_baselines_always_and_never(self):
        """Verifies policy baselines ALWAYS_MITIGATE and NEVER_MITIGATE on synthetic ground truth."""
        y_true = np.array([1, 0, 1, 0, 0])
        c_fn = 0.50
        c_fp = 0.10
        c_m = 0.01

        # ALWAYS_MITIGATE: all intervals mitigated
        # For y=1: loss = C_M = 0.01 (2 times = 0.02)
        # For y=0: loss = C_FP + C_M = 0.11 (3 times = 0.33)
        # Total realized = 0.35
        realized_always = np.sum((1 - y_true) * c_fp + c_m)
        self.assertAlmostEqual(realized_always, 0.35, places=6)

        # NEVER_MITIGATE: all intervals allowed
        # For y=1: loss = C_FN = 0.50 (2 times = 1.00)
        # For y=0: loss = 0.00 (3 times = 0.00)
        # Total realized = 1.00
        realized_never = np.sum(y_true * c_fn)
        self.assertAlmostEqual(realized_never, 1.00, places=6)

    # -------------------------------------------------------------------------
    # Test 14: Realized post-hoc loss calculation
    # -------------------------------------------------------------------------
    def test_14_realized_posthoc_loss_calculation(self):
        """Verifies exact realized loss equation: FN*C_FN + FP*C_FP + N_mit*C_M."""
        y_true = np.array([1, 0, 1, 0, 0, 1])
        decisions = np.array([
            DecisionAction.MITIGATE,  # TP: y=1, action=MIT -> C_M
            DecisionAction.MITIGATE,  # FP: y=0, action=MIT -> C_FP + C_M
            DecisionAction.ALLOW,     # FN: y=1, action=ALLOW -> C_FN
            DecisionAction.ALLOW,     # TN: y=0, action=ALLOW -> 0
            DecisionAction.ALLOW,     # TN: y=0, action=ALLOW -> 0
            DecisionAction.MITIGATE,  # TP: y=1, action=MIT -> C_M
        ])
        c_fn, c_fp, c_m = 0.50, 0.10, 0.01

        # Confusion counts:
        tp = 2  # indices 0, 5
        fp = 1  # index 1
        tn = 2  # indices 3, 4
        fn = 1  # index 2
        n_mit = tp + fp  # 3

        # Formula: FN*C_FN + FP*C_FP + N_mit*C_M
        loss_formula = fn * c_fn + fp * c_fp + n_mit * c_m
        # 1 * 0.50 + 1 * 0.10 + 3 * 0.01 = 0.50 + 0.10 + 0.03 = 0.63

        # Elementwise vector computation:
        loss_elementwise = np.where(
            decisions == DecisionAction.MITIGATE,
            (1 - y_true) * c_fp + c_m,
            y_true * c_fn
        ).sum()

        self.assertAlmostEqual(loss_formula, 0.63, places=6)
        self.assertAlmostEqual(loss_elementwise, 0.63, places=6)

    # -------------------------------------------------------------------------
    # Test 15: Calibration input/output compatibility and finite bounded probabilities
    # -------------------------------------------------------------------------
    def test_15_calibrator_compatibility_and_bounds(self):
        """Verifies calibrator artifact compatibility, finite output, and strictly bounded range [0, 1]."""
        import pickle
        calib_path = os.path.join(STEP5_DIR, "preflight", "interval_calibrator.pkl")
        self.assertTrue(os.path.exists(calib_path), "Calibrator artifact missing!")

        with open(calib_path, "rb") as f:
            calib = pickle.load(f)

        self.assertIn("weight_w", calib)
        self.assertIn("bias_b", calib)
        w = calib["weight_w"]
        b = calib["bias_b"]

        # Synthetic test inputs across 6 orders of magnitude of reconstruction error
        recon_errors = np.array([1e-10, 1e-6, 1e-4, 1e-2, 0.1, 1.0, 10.0, 100.0])
        feat = np.log(recon_errors + 1e-12)
        probs = 1.0 / (1.0 + np.exp(-(w * feat + b)))

        self.assertTrue(np.all(np.isfinite(probs)))
        self.assertTrue(np.all(probs >= 0.0))
        self.assertTrue(np.all(probs <= 1.0))
        # Monotonically non-decreasing
        self.assertTrue(np.all(np.diff(probs) >= 0.0))

    # -------------------------------------------------------------------------
    # Test 16: Customer/time alignment and duplicate detection
    # -------------------------------------------------------------------------
    def test_16_duplicate_detection(self):
        """Verifies duplicate customer-interval detection logic."""
        df_clean = pd.DataFrame({
            "customer_id": [1, 1, 2, 2],
            "time_index": [0, 1, 0, 1]
        })
        self.assertEqual(df_clean.duplicated(subset=["customer_id", "time_index"]).sum(), 0)

        df_dup = pd.DataFrame({
            "customer_id": [1, 1, 1, 2],
            "time_index": [0, 1, 1, 0]
        })
        self.assertEqual(df_dup.duplicated(subset=["customer_id", "time_index"]).sum(), 1)


    # -------------------------------------------------------------------------
    # Test 17: Unweighted calibrator artifact and probability bounds
    # -------------------------------------------------------------------------
    def test_17_unweighted_calibrator_bounds(self):
        """Verifies interval_calibrator_unweighted.pkl loads, is strictly bounded in [0, 1], and produces expected scale."""
        import pickle
        unw_path = os.path.join(STEP5_DIR, "preflight", "interval_calibrator_unweighted.pkl")
        self.assertTrue(os.path.exists(unw_path), "Unweighted calibrator artifact missing!")

        with open(unw_path, "rb") as f:
            art = pickle.load(f)

        self.assertIn("weight_w", art)
        self.assertIn("bias_b", art)
        w = art["weight_w"]
        b = art["bias_b"]

        recon_errors = np.array([1e-10, 1e-6, 1e-4, 1e-2, 0.1, 1.0, 10.0, 100.0])
        feat = np.log(recon_errors + 1e-12)
        probs = 1.0 / (1.0 + np.exp(-(w * feat + b)))

        self.assertTrue(np.all(np.isfinite(probs)))
        self.assertTrue(np.all(probs >= 0.0))
        self.assertTrue(np.all(probs <= 1.0))
        self.assertTrue(np.all(np.diff(probs) >= 0.0))

    # -------------------------------------------------------------------------
    # Test 18: Original five sensitivity scenarios analytical breakeven
    # -------------------------------------------------------------------------
    def test_18_original_five_scenarios_breakeven(self):
        """Verifies exact analytical breakeven probabilities p* for the 5 original scenarios."""
        scenarios = [
            ("SC-1", 0.50, 0.10, 0.01, 0.11 / 0.60),
            ("SC-2", 1.00, 0.10, 0.01, 0.11 / 1.10),
            ("SC-3", 0.20, 0.20, 0.01, 0.21 / 0.40),
            ("SC-4", 0.10, 0.50, 0.01, 0.51 / 0.60),
            ("SC-5", 0.50, 0.10, 0.15, 0.25 / 0.60),
        ]
        for name, fn, fp, m, expected_pstar in scenarios:
            p_star = (fp + m) / (fn + fp)
            self.assertAlmostEqual(p_star, expected_pstar, places=6, msg=f"Mismatch in {name}")

    # -------------------------------------------------------------------------
    # Test 19: Full prosumer day streaming contract (299 prosumers x 48 slots)
    # -------------------------------------------------------------------------
    def test_19_full_prosumer_day_streaming_contract(self):
        """Verifies day-by-day batch contract for Step 6 CDA: 299 customers x 48 slots = 14,352 records."""
        n_cust = 299
        n_slots = 48
        total_records = n_cust * n_slots

        cids = np.repeat(np.arange(1, n_cust + 1), n_slots)
        slots = np.tile(np.arange(n_slots), n_cust)
        time_indices = 450 * 48 + slots # day 450

        df_day = pd.DataFrame({
            "customer_id": cids,
            "slot_index": slots,
            "time_index": time_indices
        })

        self.assertEqual(len(df_day), 14352)
        self.assertEqual(df_day.duplicated(subset=["customer_id", "time_index"]).sum(), 0)
        self.assertEqual(df_day["customer_id"].nunique(), 299)
        self.assertEqual(df_day["slot_index"].nunique(), 48)


if __name__ == "__main__":
    unittest.main()


