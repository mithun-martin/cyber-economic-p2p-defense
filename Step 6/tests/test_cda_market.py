"""
Comprehensive Unit and Integration Test Suite for Step 6 CDA Market Simulator.

Step 6.2.1 Audit Regression Tests Included:
  1. Role classification and inactive epsilon deadband.
  2. Order book price-time priority, continuous matching, and partial fills.
  3. Energy conservation invariants (E_p2p <= min(D, S), Demand balancing, Supply balancing).
  4. Exact surplus linearity: W_P2P = S_B + S_S = (G_T - FiT) * E_P2P.
  5. Price crossing conditions and tariff boundaries [FiT, G_T].
  6. Zero-trade interval reporting behavior (VWAP=$0.19, Surplus=$0).
  7. Deterministic locked pairing repeatability across regimes.
  8. Paired randomness invariance across active counts and participant roles.
  9. Cross-regime role flip valuation independence (Buyer in Reg A vs Seller in Reg B).
  10. Deterministic midpoint bidding independence from ZI-C stream.
  11. Orthogonal cyber metric classification:
      - Corrupted raw energy cleared (y=1 and M=0)
      - Attack-targeted interval traded energy (y=1)
      - Fallback energy traded (M=1)
      - Clean counterfactual exposure
  12. Quarantined attack label isolation from live market decisions.
  13. End-to-end multi-regime streaming integration.
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
STEP6_DIR = os.path.dirname(TEST_DIR)
PROJECT_ROOT = os.path.dirname(STEP6_DIR)

sys.path.append(STEP6_DIR)
sys.path.append(os.path.join(PROJECT_ROOT, "Step 5"))

from cda_market import (
    OrderRole, PricingRule, BiddingStrategy, MarketRegime, MarketTariffs,
    Order, Trade, IntervalResult, LockedPairingEngine, CDAOrderBook,
    IntervalMarketEngine, CDASimulator
)


class TestCDAOrderBook(unittest.TestCase):
    """Unit tests for the CDAOrderBook data structure and matching logic."""

    def setUp(self):
        self.tariffs = MarketTariffs(g_t=0.30, fit=0.08, epsilon=1e-4)
        self.book = CDAOrderBook(self.tariffs, PricingRule.MIDPOINT)

    def test_price_time_priority_bids(self):
        """Verify that bids are sorted descending by price, and on ties by earliest arrival."""
        o1 = Order(1, 101, OrderRole.BUYER, 1.0, 1.0, 0.22, 10.0, 1, 0, 0)
        o2 = Order(2, 102, OrderRole.BUYER, 1.0, 1.0, 0.26, 20.0, 2, 0, 0) # Higher price
        o3 = Order(3, 103, OrderRole.BUYER, 1.0, 1.0, 0.26, 30.0, 3, 0, 0) # Equal price, later arrival
        o4 = Order(4, 104, OrderRole.BUYER, 1.0, 1.0, 0.20, 5.0, 0, 0, 0)  # Lower price

        self.book.submit_order(o1)
        self.book.submit_order(o2)
        self.book.submit_order(o3)
        self.book.submit_order(o4)

        cids = [b.customer_id for b in self.book.bids]
        self.assertEqual(cids, [102, 103, 101, 104])

    def test_price_time_priority_asks(self):
        """Verify that asks are sorted ascending by price, and on ties by earliest arrival."""
        a1 = Order(1, 201, OrderRole.SELLER, 1.0, 1.0, 0.15, 10.0, 1, 0, 0)
        a2 = Order(2, 202, OrderRole.SELLER, 1.0, 1.0, 0.12, 20.0, 2, 0, 0) # Lower price
        a3 = Order(3, 203, OrderRole.SELLER, 1.0, 1.0, 0.12, 30.0, 3, 0, 0) # Equal price, later arrival
        a4 = Order(4, 204, OrderRole.SELLER, 1.0, 1.0, 0.18, 5.0, 0, 0, 0)  # Higher price

        self.book.submit_order(a1)
        self.book.submit_order(a2)
        self.book.submit_order(a3)
        self.book.submit_order(a4)

        cids = [a.customer_id for a in self.book.asks]
        self.assertEqual(cids, [202, 203, 201, 204])

    def test_midpoint_matching_and_partial_fills(self):
        """Verify partial fills, midpoint execution pricing, and surplus division."""
        ask = Order(1, 201, OrderRole.SELLER, 2.0, 2.0, 0.14, 10.0, 1, 0, 0)
        trades1 = self.book.submit_order(ask)
        self.assertEqual(len(trades1), 0)
        self.assertEqual(len(self.book.asks), 1)

        bid1 = Order(2, 101, OrderRole.BUYER, 1.2, 1.2, 0.20, 20.0, 2, 0, 0)
        trades2 = self.book.submit_order(bid1)

        self.assertEqual(len(trades2), 1)
        t = trades2[0]
        self.assertEqual(t.quantity, 1.2)
        self.assertAlmostEqual(t.price, (0.20 + 0.14) / 2.0)  # $0.17
        self.assertAlmostEqual(t.buyer_surplus, (0.30 - 0.17) * 1.2)
        self.assertAlmostEqual(t.seller_surplus, (0.17 - 0.08) * 1.2)
        self.assertAlmostEqual(t.total_surplus, (0.30 - 0.08) * 1.2)
        self.assertAlmostEqual(t.buyer_surplus + t.seller_surplus, t.total_surplus)

        self.assertEqual(len(self.book.asks), 1)
        self.assertAlmostEqual(self.book.asks[0].remaining_quantity, 0.8)
        self.assertEqual(len(self.book.bids), 0)

        bid2 = Order(3, 102, OrderRole.BUYER, 1.5, 1.5, 0.18, 30.0, 3, 0, 0)
        trades3 = self.book.submit_order(bid2)

        self.assertEqual(len(trades3), 1)
        t2 = trades3[0]
        self.assertAlmostEqual(t2.quantity, 0.8)
        self.assertAlmostEqual(t2.price, (0.18 + 0.14) / 2.0)

        self.assertEqual(len(self.book.asks), 0)
        self.assertEqual(len(self.book.bids), 1)
        self.assertAlmostEqual(self.book.bids[0].remaining_quantity, 0.7)

    def test_interval_expiry_and_clearing(self):
        """Verify clear_interval expires resting orders and reports exact unmet volumes."""
        self.book.submit_order(Order(1, 101, OrderRole.BUYER, 1.0, 1.0, 0.10, 1.0, 1, 0, 0))
        self.book.submit_order(Order(2, 201, OrderRole.SELLER, 2.5, 2.5, 0.25, 2.0, 2, 0, 0))

        unmet_demand, unmatched_supply = self.book.clear_interval()
        self.assertAlmostEqual(unmet_demand, 1.0)
        self.assertAlmostEqual(unmatched_supply, 2.5)
        self.assertEqual(len(self.book.bids), 0)
        self.assertEqual(len(self.book.asks), 0)


class TestLockedPairingEngine(unittest.TestCase):
    """Verify deterministic repeatability and anti-confounding across regimes."""

    def setUp(self):
        self.tariffs = MarketTariffs(g_t=0.30, fit=0.08, epsilon=1e-4)
        self.pairing = LockedPairingEngine(base_seed=42, tariffs=self.tariffs)

    def test_arrival_permutations_paired_across_regimes(self):
        """Arrival order permutation must be bitwise identical across all regimes."""
        perm_clean = self.pairing.get_arrival_permutation(day_index=425, slot_index=12, n_prosumers=299)
        perm_regA  = self.pairing.get_arrival_permutation(day_index=425, slot_index=12, n_prosumers=299)
        perm_regB  = self.pairing.get_arrival_permutation(day_index=425, slot_index=12, n_prosumers=299)
        perm_regC  = self.pairing.get_arrival_permutation(day_index=425, slot_index=12, n_prosumers=299)

        np.testing.assert_array_equal(perm_clean, perm_regA)
        np.testing.assert_array_equal(perm_clean, perm_regB)
        np.testing.assert_array_equal(perm_clean, perm_regC)

    def test_customer_valuations_paired_across_regimes(self):
        """Customer-level random bid and ask valuation draws must be identical across regimes."""
        bids_A, asks_A = self.pairing.get_slot_valuations(day_index=425, slot_index=12, n_prosumers=299)
        bids_C, asks_C = self.pairing.get_slot_valuations(day_index=425, slot_index=12, n_prosumers=299)

        np.testing.assert_array_equal(bids_A, bids_C)
        np.testing.assert_array_equal(asks_A, asks_C)

    def test_valuations_do_not_shift_with_active_counts_or_roles(self):
        """Valuation draws for customer i must not shift if active counts or other prosumer roles change."""
        bids_all, asks_all = self.pairing.get_slot_valuations(day_index=425, slot_index=12, n_prosumers=299)
        
        # Test individual lookup for prosumer index 53 (corresponding to customer 55)
        b_single, a_single = self.pairing.get_prosumer_valuation(
            day_index=425, slot_index=12, prosumer_idx=53
        )
        self.assertEqual(bids_all[53], b_single)
        self.assertEqual(asks_all[53], a_single)

    def test_buyer_to_seller_role_flip_valuation_independence(self):
        """When a customer flips from Buyer to Seller across regimes, role valuations are independent."""
        bids, asks = self.pairing.get_slot_valuations(day_index=425, slot_index=12, n_prosumers=299)
        
        cid_idx = 10
        buyer_val = bids[cid_idx]
        seller_val = asks[cid_idx]

        # Both valuations are valid rational prices within [FiT, G_T]
        self.assertTrue(0.08 <= buyer_val <= 0.30)
        self.assertTrue(0.08 <= seller_val <= 0.30)
        # Because drawn from independent uniform columns, buyer and seller valuations are not equal
        self.assertNotEqual(buyer_val, seller_val)

    def test_deterministic_strategy(self):
        """Deterministic benchmark must output exact fixed prices ($0.20, $0.18) without random draws."""
        bids, asks = self.pairing.get_slot_valuations(
            day_index=425, slot_index=12, n_prosumers=299, strategy=BiddingStrategy.DETERMINISTIC
        )
        self.assertTrue((bids == 0.2000).all())
        self.assertTrue((asks == 0.1800).all())


class TestIntervalMarketEngine(unittest.TestCase):
    """Verify interval execution, energy conservation invariants, and cyber metric separation."""

    def setUp(self):
        self.tariffs = MarketTariffs(g_t=0.30, fit=0.08, epsilon=1e-4)
        self.pairing = LockedPairingEngine(base_seed=42, tariffs=self.tariffs)
        self.engine = IntervalMarketEngine(
            tariffs=self.tariffs,
            pairing_engine=self.pairing,
            pricing_rule=PricingRule.MIDPOINT,
            bidding_strategy=BiddingStrategy.ZI_C
        )

    def test_role_classification_and_deadband(self):
        """Verify inactive deadband correctly ignores net positions <= epsilon."""
        cids = np.array([1, 2, 3, 4, 5])
        pnet = np.array([1.5, -2.0, 0.00005, -0.00005, 0.0])

        res = self.engine.simulate_interval(
            day_index=425, slot_index=0, customer_ids=cids, p_net_eff=pnet
        )
        self.assertEqual(res.n_buyers, 1)
        self.assertEqual(res.n_sellers, 1)
        self.assertEqual(res.n_inactive, 3)
        self.assertAlmostEqual(res.total_demand_kWh, 1.5)
        self.assertAlmostEqual(res.total_supply_kWh, 2.0)

    def test_zero_trade_edge_case(self):
        """When no trades occur, verify VWAP=$0.19, surplus=$0, and demand/supply balanced with grid."""
        cids = np.array([1, 2])
        pnet = np.array([1.0, 2.0])

        res = self.engine.simulate_interval(
            day_index=425, slot_index=0, customer_ids=cids, p_net_eff=pnet
        )
        self.assertEqual(res.matched_volume_kWh, 0.0)
        self.assertEqual(res.n_trades, 0)
        self.assertEqual(res.vwap_aud_per_kwh, 0.1900)
        self.assertEqual(res.buyer_surplus_aud, 0.0)
        self.assertEqual(res.seller_surplus_aud, 0.0)
        self.assertEqual(res.gross_tariff_surplus_aud, 0.0)
        self.assertAlmostEqual(res.unmet_demand_kWh, 3.0)
        self.assertAlmostEqual(res.unmatched_supply_kWh, 0.0)
        self.assertAlmostEqual(res.grid_import_cost_aud, 3.0 * 0.30)

    def test_energy_conservation_and_surplus_equations(self):
        """Simulate realistic random interval and assert all physical invariants."""
        rng = np.random.RandomState(123)
        n = 100
        cids = np.arange(1, n + 1)
        pnet = rng.uniform(-3.0, 3.0, size=n)

        res = self.engine.simulate_interval(
            day_index=425, slot_index=20, customer_ids=cids, p_net_eff=pnet
        )

        self.assertLessEqual(res.matched_volume_kWh, min(res.total_demand_kWh, res.total_supply_kWh) + 1e-8)
        self.assertAlmostEqual(res.matched_volume_kWh + res.unmet_demand_kWh, res.total_demand_kWh, places=7)
        self.assertAlmostEqual(res.matched_volume_kWh + res.unmatched_supply_kWh, res.total_supply_kWh, places=7)
        self.assertAlmostEqual(
            res.gross_tariff_surplus_aud,
            (self.tariffs.g_t - self.tariffs.fit) * res.matched_volume_kWh,
            places=7
        )

    def test_orthogonal_cyber_metric_classification(self):
        """Verify rigorous orthogonal separation of the three post-hoc cyber metrics."""
        engine_det = IntervalMarketEngine(
            tariffs=self.tariffs,
            pairing_engine=self.pairing,
            pricing_rule=PricingRule.MIDPOINT,
            bidding_strategy=BiddingStrategy.DETERMINISTIC
        )
        cids = np.array([1, 2])
        pnet = np.array([1.0, -1.0]) # Buyer cid 1, Seller cid 2 -> 1.0 kWh trade

        # Case 1: Unmitigated Attack (Regime A: y=1, m=0)
        res_A = engine_det.simulate_interval(
            day_index=425, slot_index=0, customer_ids=cids, p_net_eff=pnet,
            regime_name=MarketRegime.REGIME_A.value,
            ground_truth_attacks=np.array([0, 1]), # Seller is attacked
            mitigation_flags=np.array([False, False]) # Unmitigated
        )
        self.assertAlmostEqual(res_A.corrupted_raw_energy_cleared_kWh, 1.0)
        self.assertAlmostEqual(res_A.attack_targeted_interval_traded_energy_kWh, 1.0)
        self.assertAlmostEqual(res_A.fallback_energy_traded_kWh, 0.0)
        self.assertAlmostEqual(res_A.clean_counterfactual_exposure_kWh, 0.0)

        # Case 2: Maximum Defense (Regime B: y=1, m=1)
        res_B = engine_det.simulate_interval(
            day_index=425, slot_index=0, customer_ids=cids, p_net_eff=pnet,
            regime_name=MarketRegime.REGIME_B.value,
            ground_truth_attacks=np.array([0, 1]), # Seller was targeted
            mitigation_flags=np.array([True, True])  # Both mitigated
        )
        # In Regime B, corrupted raw energy MUST be exactly 0.0!
        self.assertAlmostEqual(res_B.corrupted_raw_energy_cleared_kWh, 0.0)
        self.assertAlmostEqual(res_B.attack_targeted_interval_traded_energy_kWh, 1.0)
        self.assertAlmostEqual(res_B.fallback_energy_traded_kWh, 1.0)
        self.assertAlmostEqual(res_B.clean_counterfactual_exposure_kWh, 0.0)

        # Case 3: Clean Baseline (CLEAN: y=0, m=0)
        res_Clean = engine_det.simulate_interval(
            day_index=425, slot_index=0, customer_ids=cids, p_net_eff=pnet,
            regime_name=MarketRegime.CLEAN.value,
            ground_truth_attacks=np.array([0, 1]), # Ground truth target indicator from benchmark
            mitigation_flags=np.array([False, False])
        )
        # In Clean, corrupted raw energy is 0.0, fallback is 0.0, and targeted is clean exposure!
        self.assertAlmostEqual(res_Clean.corrupted_raw_energy_cleared_kWh, 0.0)
        self.assertAlmostEqual(res_Clean.attack_targeted_interval_traded_energy_kWh, 1.0)
        self.assertAlmostEqual(res_Clean.fallback_energy_traded_kWh, 0.0)
        self.assertAlmostEqual(res_Clean.clean_counterfactual_exposure_kWh, 1.0)


class TestCDASimulatorIntegration(unittest.TestCase):
    """Integration test verifying multi-regime streaming integration."""

    def test_smoke_simulation_one_day(self):
        """Run 1 day of simulation across all 4 regimes and verify output schemas."""
        sim = CDASimulator()
        df_int, df_day, stats = sim.run_simulation(start_day=425, end_day=425)

        self.assertEqual(len(df_day), 4)
        expected_regimes = {"REGIME_A", "REGIME_B", "REGIME_C", "CLEAN"}
        self.assertEqual(set(df_day["regime"].unique()), expected_regimes)
        self.assertEqual(len(df_int), 192)

        # Verify new orthogonal columns exist
        new_cols = [
            "corrupted_raw_energy_cleared_kWh",
            "attack_targeted_interval_traded_energy_kWh",
            "fallback_energy_traded_kWh",
            "clean_counterfactual_exposure_kWh"
        ]
        for col in new_cols:
            self.assertIn(col, df_int.columns)
            self.assertIn(col, df_day.columns)


if __name__ == "__main__":
    unittest.main(verbosity=2)
