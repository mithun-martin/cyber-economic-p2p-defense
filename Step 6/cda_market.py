"""
Step 6: Continuous Double Auction (CDA) Market Simulator.

Project: Cyber-Economic Resilience Under Evolving Attacks in Peer-to-Peer Energy Markets.
Component: Step 6.2 / 6.2.1 - Core CDA Market Engine and Multi-Regime Evaluation.

Key Architectural Components:
  1. CDAOrderBook: Price-time priority matching engine with partial fill support.
  2. LockedPairingEngine: Deterministic hierarchical pseudo-random seed generator.
  3. IntervalMarketEngine: 30-minute interval clearing, dual-settlement balancing,
     energy conservation invariant checks, and economic surplus calculations.
  4. CDASimulator: High-throughput streaming runner evaluating Regimes A, B, C,
     and Clean counterfactual reference across Ausgrid prosumers.

Design Invariants & Metric Semantics Enforced:
  - Strict Half-Hour Expiry: Zero cross-interval order or energy carryover.
  - Conservation of Energy: Matched volume <= min(Demand, Supply).
  - Exact Surplus Linearity: W_P2P = S_B + S_S = (G_T - FiT) * E_P2P.
  - Quarantined Attack Labels: Ground truth labels are strictly isolated from matching.
  - Locked Pairing: Pseudo-random order arrival and pricing draws are bitwise
    identical across all regimes and independent of participant roles.
  - Orthogonal Cyber Metrics:
      * corrupted_raw_energy_cleared_kWh: energy traded using unmitigated corrupted raw telemetry (y=1 and M=0).
      * attack_targeted_interval_traded_energy_kWh: energy traded in attack-targeted intervals (y=1).
      * fallback_energy_traded_kWh: energy traded from fallback-substituted orders (M=1).
      * clean_counterfactual_exposure_kWh: counterfactual volume of attack targets in the Clean market.
"""

import os
import sys
import time
import bisect
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# Add Step 5 to path for production streaming interface
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.append(os.path.join(PROJECT_ROOT, "Step 5"))

from streaming import Step5MarketStreamer


# ==============================================================================
# 1. DATA MODELS & ENUMS
# ==============================================================================

class OrderRole(str, Enum):
    BUYER = "BUYER"
    SELLER = "SELLER"
    INACTIVE = "INACTIVE"


class PricingRule(str, Enum):
    MIDPOINT = "midpoint"      # k-double auction with k = 0.5: P* = (B* + A*) / 2
    MAKER = "maker"            # Standing-order price rule (sensitivity check)


class BiddingStrategy(str, Enum):
    ZI_C = "zi_c"                          # Zero-Intelligence Constrained: U(FiT, G_T)
    DETERMINISTIC = "deterministic"        # Deterministic: Buyer $0.20, Seller $0.18


class MarketRegime(str, Enum):
    REGIME_A = "REGIME_A"      # Unmitigated: Raw attacked telemetry (NEVER_MITIGATE)
    REGIME_B = "REGIME_B"      # Maximum Defense: 100% fallback substitution (ALWAYS_MITIGATE)
    REGIME_C = "REGIME_C"      # Selective Defense: Fixed threshold tau = 0.50 on balanced p
    CLEAN = "CLEAN"            # Counterfactual Reference: Clean unattacked telemetry


@dataclass
class MarketTariffs:
    g_t: float = 0.3000        # Retail grid import tariff (AUD/kWh)
    fit: float = 0.0800        # Feed-in export tariff (AUD/kWh)
    epsilon: float = 1e-4      # Inactive deadband threshold (kWh, 0.1 Wh)

    def __post_init__(self):
        if self.fit >= self.g_t:
            raise ValueError(f"FiT ({self.fit}) must be strictly less than G_T ({self.g_t}).")
        if self.epsilon <= 0.0:
            raise ValueError(f"Epsilon ({self.epsilon}) must be strictly positive.")


@dataclass
class Order:
    order_id: int
    customer_id: int
    role: OrderRole
    initial_quantity: float     # Submitted volume (kWh)
    remaining_quantity: float   # Unfilled volume remaining (kWh)
    price: float                # Bid or Ask limit price (AUD/kWh)
    arrival_time: float         # Simulated arrival timestamp within [0, 1800] s
    arrival_index: int          # Deterministic queue priority tie-breaker
    day_index: int
    slot_index: int


@dataclass
class Trade:
    trade_id: int
    day_index: int
    slot_index: int
    buyer_id: int
    seller_id: int
    quantity: float             # Matched energy (kWh)
    price: float                # Transaction clearing price (AUD/kWh)
    bid_price: float            # Submitted buyer limit price
    ask_price: float            # Submitted seller limit price
    buyer_arrival_index: int
    seller_arrival_index: int
    pricing_rule: str
    buyer_surplus: float        # (G_T - P*) * Q
    seller_surplus: float       # (P* - FiT) * Q
    total_surplus: float        # (G_T - FiT) * Q


@dataclass
class IntervalResult:
    day_index: int
    slot_index: int
    regime: str
    n_buyers: int
    n_sellers: int
    n_inactive: int
    total_demand_kWh: float
    total_supply_kWh: float
    matched_volume_kWh: float   # E_P2P
    unmet_demand_kWh: float     # E_unmet_B
    unmatched_supply_kWh: float # E_unmatched_S
    match_rate_pct: float
    vwap_aud_per_kwh: float
    buyer_surplus_aud: float    # S_B
    seller_surplus_aud: float   # S_S
    gross_tariff_surplus_aud: float # W_P2P = S_B + S_S
    grid_import_cost_aud: float # E_unmet_B * G_T
    grid_export_revenue_aud: float # E_unmatched_S * FiT
    net_grid_settlement_aud: float # import_cost - export_revenue
    n_trades: int
    corrupted_raw_energy_cleared_kWh: float = 0.0        # Matched energy on corrupted raw telemetry (y=1 and M=0)
    attack_targeted_interval_traded_energy_kWh: float = 0.0 # Matched energy in attack-targeted intervals (y=1)
    fallback_energy_traded_kWh: float = 0.0             # Matched energy from fallback-substituted orders (M=1)
    clean_counterfactual_exposure_kWh: float = 0.0       # Matched energy in targeted intervals in Clean market
    n_corrupted_raw_trades: int = 0
    n_attack_targeted_trades: int = 0
    n_fallback_trades: int = 0
    trades: List[Trade] = field(default_factory=list)


# ==============================================================================
# 2. DETERMINISTIC LOCKED PAIRING ENGINE
# ==============================================================================

class LockedPairingEngine:
    """
    Guarantees bitwise repeatability and anti-confounding across market regimes.
    Arrival sequences and prosumer valuation draws are identical across Regimes
    A, B, C, and Clean baseline.
    """
    def __init__(
        self,
        base_seed: int = 42,
        tariffs: Optional[MarketTariffs] = None,
        authoritative_cids: Optional[np.ndarray] = None
    ):
        self.base_seed = base_seed
        self.tariffs = tariffs or MarketTariffs()
        self.authoritative_cids = authoritative_cids

    def get_arrival_permutation(self, day_index: int, slot_index: int, n_prosumers: int = 299) -> np.ndarray:
        """
        Deterministic arrival order permutation for a 30-minute interval.
        Seed: base_seed + day_index * 100000 + slot_index * 1000.
        """
        seed = int(self.base_seed + day_index * 100000 + slot_index * 1000) & 0xFFFFFFFF
        rng = np.random.RandomState(seed)
        return rng.permutation(n_prosumers)

    def get_slot_valuations(
        self,
        day_index: int,
        slot_index: int,
        n_prosumers: int = 299,
        strategy: BiddingStrategy = BiddingStrategy.ZI_C
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Fast vectorized valuation draws for all prosumers in a single half-hour interval.
        Returns: (bids_array, asks_array) of shape [n_prosumers].
        Each prosumer receives an independently defined Buyer valuation (col 0)
        and Seller valuation (col 1), invariant to active counts or role assignment.
        """
        if strategy == BiddingStrategy.DETERMINISTIC:
            return np.full(n_prosumers, 0.2000), np.full(n_prosumers, 0.1800)

        seed = int(self.base_seed + day_index * 100000 + slot_index * 1000) & 0xFFFFFFFF
        rng = np.random.RandomState(seed)
        uv = rng.uniform(0.0, 1.0, size=(n_prosumers, 2))

        fit = self.tariffs.fit
        g_t = self.tariffs.g_t
        bids = fit + uv[:, 0] * (g_t - fit)
        asks = fit + uv[:, 1] * (g_t - fit)
        return bids, asks

    def get_prosumer_valuation(
        self,
        day_index: int,
        slot_index: int,
        customer_id: Optional[int] = None,
        prosumer_idx: Optional[int] = None,
        customer_ids: Optional[np.ndarray] = None,
        strategy: BiddingStrategy = BiddingStrategy.ZI_C
    ) -> Tuple[float, float]:
        """
        Single prosumer valuation lookup helper for unit testing.
        Guarantees exact parity with get_slot_valuations.
        """
        if strategy == BiddingStrategy.DETERMINISTIC:
            return (0.2000, 0.1800)

        cids_ref = customer_ids if customer_ids is not None else self.authoritative_cids
        if cids_ref is not None and customer_id is not None:
            cids_list = list(cids_ref)
            idx = cids_list.index(customer_id) if customer_id in cids_list else 0
            n_p = len(cids_ref)
        else:
            idx = prosumer_idx if prosumer_idx is not None else (customer_id if customer_id is not None else 0)
            n_p = max(idx + 1, 299)

        bids, asks = self.get_slot_valuations(day_index, slot_index, n_prosumers=n_p, strategy=strategy)
        return float(bids[idx]), float(asks[idx])


# ==============================================================================
# 3. CONTINUOUS DOUBLE AUCTION ORDER BOOK
# ==============================================================================

class CDAOrderBook:
    """
    High-performance price-time priority Continuous Double Auction matching engine.
    Maintains parallel sorted key caches for O(log K) bisect insertions without
    recomputing keys over standing orders.
    """
    def __init__(self, tariffs: MarketTariffs, pricing_rule: PricingRule = PricingRule.MIDPOINT):
        self.tariffs = tariffs
        self.pricing_rule = pricing_rule
        self.bids: List[Order] = []
        self.bid_keys: List[Tuple[float, int]] = []
        self.asks: List[Order] = []
        self.ask_keys: List[Tuple[float, int]] = []
        self.trade_counter = 0

    def _bid_key(self, order: Order) -> Tuple[float, int]:
        # Highest price first (-price), earliest arrival first (arrival_index)
        return (-order.price, order.arrival_index)

    def _ask_key(self, order: Order) -> Tuple[float, int]:
        # Lowest price first (+price), earliest arrival first (arrival_index)
        return (order.price, order.arrival_index)

    def submit_order(self, order: Order) -> List[Trade]:
        """
        Submits an incoming order to the order book.
        Immediately matches against standing orders if crossing conditions are met.
        Any unfilled residual is inserted into the standing queue.
        """
        executed_trades: List[Trade] = []

        if order.role == OrderRole.BUYER:
            # Match against standing sell book (asks)
            while self.asks and order.remaining_quantity > 1e-9:
                best_ask = self.asks[0]
                if order.price < best_ask.price:
                    break  # Crossing condition fails (Bid < Ask)

                match_q = min(order.remaining_quantity, best_ask.remaining_quantity)
                if match_q <= 1e-9:
                    break

                # Determine transaction price
                if self.pricing_rule == PricingRule.MIDPOINT:
                    trade_p = (order.price + best_ask.price) / 2.0
                elif self.pricing_rule == PricingRule.MAKER:
                    trade_p = best_ask.price  # Resting order price
                else:
                    trade_p = (order.price + best_ask.price) / 2.0

                self.trade_counter += 1
                b_surplus = (self.tariffs.g_t - trade_p) * match_q
                s_surplus = (trade_p - self.tariffs.fit) * match_q
                t_surplus = (self.tariffs.g_t - self.tariffs.fit) * match_q

                trade = Trade(
                    trade_id=self.trade_counter,
                    day_index=order.day_index,
                    slot_index=order.slot_index,
                    buyer_id=order.customer_id,
                    seller_id=best_ask.customer_id,
                    quantity=match_q,
                    price=trade_p,
                    bid_price=order.price,
                    ask_price=best_ask.price,
                    buyer_arrival_index=order.arrival_index,
                    seller_arrival_index=best_ask.arrival_index,
                    pricing_rule=self.pricing_rule.value,
                    buyer_surplus=b_surplus,
                    seller_surplus=s_surplus,
                    total_surplus=t_surplus
                )
                executed_trades.append(trade)

                # Deduct matched quantity
                order.remaining_quantity -= match_q
                best_ask.remaining_quantity -= match_q

                if best_ask.remaining_quantity <= 1e-9:
                    self.asks.pop(0)
                    self.ask_keys.pop(0)

            # Insert remaining bid into standing buy book
            if order.remaining_quantity > 1e-9:
                target_key = self._bid_key(order)
                idx = bisect.bisect_right(self.bid_keys, target_key)
                self.bids.insert(idx, order)
                self.bid_keys.insert(idx, target_key)

        elif order.role == OrderRole.SELLER:
            # Match against standing buy book (bids)
            while self.bids and order.remaining_quantity > 1e-9:
                best_bid = self.bids[0]
                if order.price > best_bid.price:
                    break  # Crossing condition fails (Ask > Bid)

                match_q = min(order.remaining_quantity, best_bid.remaining_quantity)
                if match_q <= 1e-9:
                    break

                # Determine transaction price
                if self.pricing_rule == PricingRule.MIDPOINT:
                    trade_p = (best_bid.price + order.price) / 2.0
                elif self.pricing_rule == PricingRule.MAKER:
                    trade_p = best_bid.price  # Resting order price
                else:
                    trade_p = (best_bid.price + order.price) / 2.0

                self.trade_counter += 1
                b_surplus = (self.tariffs.g_t - trade_p) * match_q
                s_surplus = (trade_p - self.tariffs.fit) * match_q
                t_surplus = (self.tariffs.g_t - self.tariffs.fit) * match_q

                trade = Trade(
                    trade_id=self.trade_counter,
                    day_index=order.day_index,
                    slot_index=order.slot_index,
                    buyer_id=best_bid.customer_id,
                    seller_id=order.customer_id,
                    quantity=match_q,
                    price=trade_p,
                    bid_price=best_bid.price,
                    ask_price=order.price,
                    buyer_arrival_index=best_bid.arrival_index,
                    seller_arrival_index=order.arrival_index,
                    pricing_rule=self.pricing_rule.value,
                    buyer_surplus=b_surplus,
                    seller_surplus=s_surplus,
                    total_surplus=t_surplus
                )
                executed_trades.append(trade)

                # Deduct matched quantity
                order.remaining_quantity -= match_q
                best_bid.remaining_quantity -= match_q

                if best_bid.remaining_quantity <= 1e-9:
                    self.bids.pop(0)
                    self.bid_keys.pop(0)

            # Insert remaining ask into standing sell book
            if order.remaining_quantity > 1e-9:
                target_key = self._ask_key(order)
                idx = bisect.bisect_right(self.ask_keys, target_key)
                self.asks.insert(idx, order)
                self.ask_keys.insert(idx, target_key)

        return executed_trades

    def clear_interval(self) -> Tuple[float, float]:
        """
        Expires all standing orders at the close of the 30-minute interval.
        Returns: (unmet_buyer_demand_kWh, unmatched_seller_supply_kWh)
        """
        unmet_demand = sum(o.remaining_quantity for o in self.bids)
        unmatched_supply = sum(o.remaining_quantity for o in self.asks)
        self.bids.clear()
        self.bid_keys.clear()
        self.asks.clear()
        self.ask_keys.clear()
        return float(unmet_demand), float(unmatched_supply)


# ==============================================================================
# 4. INTERVAL MARKET SIMULATION ENGINE
# ==============================================================================

class IntervalMarketEngine:
    """
    Executes a single 30-minute Continuous Double Auction session.
    Enforces all physical energy-conservation equations and economic accounting.
    """
    def __init__(
        self,
        tariffs: MarketTariffs,
        pairing_engine: LockedPairingEngine,
        pricing_rule: PricingRule = PricingRule.MIDPOINT,
        bidding_strategy: BiddingStrategy = BiddingStrategy.ZI_C
    ):
        self.tariffs = tariffs
        self.pairing_engine = pairing_engine
        self.pricing_rule = pricing_rule
        self.bidding_strategy = bidding_strategy

    def simulate_interval(
        self,
        day_index: int,
        slot_index: int,
        customer_ids: np.ndarray,
        p_net_eff: np.ndarray,
        regime_name: str = "REGIME_A",
        ground_truth_attacks: Optional[np.ndarray] = None,
        mitigation_flags: Optional[np.ndarray] = None
    ) -> IntervalResult:
        """
        Simulates trading across prosumers in interval (day_index, slot_index).
        """
        order_book = CDAOrderBook(self.tariffs, self.pricing_rule)
        n_prosumers = len(customer_ids)

        # 1. Classify Roles and Quantities
        roles = []
        quantities = []
        for pnet in p_net_eff:
            if pnet > self.tariffs.epsilon:
                roles.append(OrderRole.BUYER)
                quantities.append(float(pnet))
            elif pnet < -self.tariffs.epsilon:
                roles.append(OrderRole.SELLER)
                quantities.append(float(abs(pnet)))
            else:
                roles.append(OrderRole.INACTIVE)
                quantities.append(0.0)

        n_buyers = sum(1 for r in roles if r == OrderRole.BUYER)
        n_sellers = sum(1 for r in roles if r == OrderRole.SELLER)
        n_inactive = n_prosumers - n_buyers - n_sellers

        total_demand = sum(q for r, q in zip(roles, quantities) if r == OrderRole.BUYER)
        total_supply = sum(q for r, q in zip(roles, quantities) if r == OrderRole.SELLER)

        # 2. Obtain Locked Arrival Permutation & Vectorized Valuations
        arrival_perm = self.pairing_engine.get_arrival_permutation(day_index, slot_index, n_prosumers)
        bids_slot, asks_slot = self.pairing_engine.get_slot_valuations(
            day_index, slot_index, n_prosumers, self.bidding_strategy
        )

        # 3. Create Orders in Locked Arrival Sequence
        all_executed_trades: List[Trade] = []
        submitted_buyer_volumes: Dict[int, float] = {}
        submitted_seller_volumes: Dict[int, float] = {}

        for arrival_idx in arrival_perm:
            cid = int(customer_ids[arrival_idx])
            role = roles[arrival_idx]
            q = quantities[arrival_idx]

            if role == OrderRole.INACTIVE or q <= 1e-9:
                continue

            if role == OrderRole.BUYER:
                order_p = float(bids_slot[arrival_idx])
                submitted_buyer_volumes[cid] = q
            else:
                order_p = float(asks_slot[arrival_idx])
                submitted_seller_volumes[cid] = q

            arr_time = (arrival_idx / max(1, n_prosumers)) * 1800.0

            order = Order(
                order_id=cid,
                customer_id=cid,
                role=role,
                initial_quantity=q,
                remaining_quantity=q,
                price=order_p,
                arrival_time=arr_time,
                arrival_index=int(arrival_idx),
                day_index=day_index,
                slot_index=slot_index
            )

            trades = order_book.submit_order(order)
            all_executed_trades.extend(trades)

        # 4. Close Interval and Grid Dual-Settlement
        unmet_demand, unmatched_supply = order_book.clear_interval()
        matched_volume = sum(t.quantity for t in all_executed_trades)

        # 5. Energy Conservation & Invariant Checks
        tol = 1e-8
        max_possible = min(total_demand, total_supply)
        if matched_volume > max_possible + tol:
            raise AssertionError(
                f"Conservation violated: Matched {matched_volume:.6f} > min(D, S) {max_possible:.6f}"
            )
        if abs((matched_volume + unmet_demand) - total_demand) > tol:
            raise AssertionError(
                f"Demand conservation violated: {matched_volume:.6f} + {unmet_demand:.6f} != {total_demand:.6f}"
            )
        if abs((matched_volume + unmatched_supply) - total_supply) > tol:
            raise AssertionError(
                f"Supply conservation violated: {matched_volume:.6f} + {unmatched_supply:.6f} != {total_supply:.6f}"
            )

        # Check individual prosumer fill invariants
        buyer_fills: Dict[int, float] = {}
        seller_fills: Dict[int, float] = {}
        for t in all_executed_trades:
            buyer_fills[t.buyer_id] = buyer_fills.get(t.buyer_id, 0.0) + t.quantity
            seller_fills[t.seller_id] = seller_fills.get(t.seller_id, 0.0) + t.quantity

        for bid, fq in buyer_fills.items():
            sub_q = submitted_buyer_volumes.get(bid, 0.0)
            if fq > sub_q + tol:
                raise AssertionError(f"Buyer {bid} overfilled: {fq:.6f} > submitted {sub_q:.6f}")

        for sid, fq in seller_fills.items():
            sub_q = submitted_seller_volumes.get(sid, 0.0)
            if fq > sub_q + tol:
                raise AssertionError(f"Seller {sid} overfilled: {fq:.6f} > submitted {sub_q:.6f}")

        for t in all_executed_trades:
            if t.bid_price < t.ask_price - tol:
                raise AssertionError(f"Trade crossed inverted prices: Bid {t.bid_price} < Ask {t.ask_price}")
            if not (self.tariffs.fit - tol <= t.price <= self.tariffs.g_t + tol):
                raise AssertionError(f"Trade price {t.price} outside tariff bounds [{self.tariffs.fit}, {self.tariffs.g_t}]")

        # 6. Economic Surplus and Tariff Balancing
        if matched_volume > 1e-9:
            vwap = sum(t.price * t.quantity for t in all_executed_trades) / matched_volume
            b_surplus = sum(t.buyer_surplus for t in all_executed_trades)
            s_surplus = sum(t.seller_surplus for t in all_executed_trades)
            gross_surplus = b_surplus + s_surplus
            match_rate = (matched_volume / max_possible * 100.0) if max_possible > 1e-9 else 0.0
        else:
            vwap = (self.tariffs.g_t + self.tariffs.fit) / 2.0  # Nominal midpoint $0.19
            b_surplus = 0.0
            s_surplus = 0.0
            gross_surplus = 0.0
            match_rate = 0.0

        grid_import_cost = unmet_demand * self.tariffs.g_t
        grid_export_revenue = unmatched_supply * self.tariffs.fit
        net_grid_settlement = grid_import_cost - grid_export_revenue

        # 7. Post-Hoc Quarantined Cyber Metrics (Orthogonal Multi-Label Breakdown)
        corrupted_raw_vol = 0.0
        attack_targeted_vol = 0.0
        fallback_vol = 0.0
        n_corrupted_trades = 0
        n_targeted_trades = 0
        n_fallback_trades = 0

        is_clean_regime = (regime_name == MarketRegime.CLEAN.value)

        if ground_truth_attacks is not None:
            # Map cid -> is_attack_targeted
            is_targeted_map = {int(cid): bool(att) for cid, att in zip(customer_ids, ground_truth_attacks)}

            # Map cid -> is_mitigated
            if mitigation_flags is not None:
                is_mit_map = {int(cid): bool(mit) for cid, mit in zip(customer_ids, mitigation_flags)}
            else:
                is_mit_map = {int(cid): False for cid in customer_ids}

            for t in all_executed_trades:
                b_id = t.buyer_id
                s_id = t.seller_id

                b_target = is_targeted_map.get(b_id, False)
                s_target = is_targeted_map.get(s_id, False)

                b_mit = is_mit_map.get(b_id, False)
                s_mit = is_mit_map.get(s_id, False)

                # Metric 1: Corrupted raw energy cleared (y=1 and M=0 on active prosumer)
                # In Clean regime, corrupted raw energy is strictly 0.0
                if not is_clean_regime:
                    b_corrupt = b_target and (not b_mit)
                    s_corrupt = s_target and (not s_mit)
                    if b_corrupt or s_corrupt:
                        corrupted_raw_vol += t.quantity
                        n_corrupted_trades += 1

                # Metric 2: Traded volume in intervals targeted by benchmark attack (y=1)
                if b_target or s_target:
                    attack_targeted_vol += t.quantity
                    n_targeted_trades += 1

                # Metric 3: Fallback-substituted energy traded (M=1)
                # In Clean regime, fallback is strictly 0.0
                if not is_clean_regime:
                    if b_mit or s_mit:
                        fallback_vol += t.quantity
                        n_fallback_trades += 1

        clean_cf_exposure = attack_targeted_vol if is_clean_regime else 0.0

        return IntervalResult(
            day_index=day_index,
            slot_index=slot_index,
            regime=regime_name,
            n_buyers=n_buyers,
            n_sellers=n_sellers,
            n_inactive=n_inactive,
            total_demand_kWh=total_demand,
            total_supply_kWh=total_supply,
            matched_volume_kWh=matched_volume,
            unmet_demand_kWh=unmet_demand,
            unmatched_supply_kWh=unmatched_supply,
            match_rate_pct=match_rate,
            vwap_aud_per_kwh=vwap,
            buyer_surplus_aud=b_surplus,
            seller_surplus_aud=s_surplus,
            gross_tariff_surplus_aud=gross_surplus,
            grid_import_cost_aud=grid_import_cost,
            grid_export_revenue_aud=grid_export_revenue,
            net_grid_settlement_aud=net_grid_settlement,
            n_trades=len(all_executed_trades),
            corrupted_raw_energy_cleared_kWh=corrupted_raw_vol,
            attack_targeted_interval_traded_energy_kWh=attack_targeted_vol,
            fallback_energy_traded_kWh=fallback_vol,
            clean_counterfactual_exposure_kWh=clean_cf_exposure,
            n_corrupted_raw_trades=n_corrupted_trades,
            n_attack_targeted_trades=n_targeted_trades,
            n_fallback_trades=n_fallback_trades,
            trades=all_executed_trades
        )


# ==============================================================================
# 5. MULTI-REGIME MASTER CDA SIMULATOR
# ==============================================================================

class CDASimulator:
    """
    Orchestrates the multi-regime streaming Continuous Double Auction simulation.
    Processes Regimes A, B, C, and Clean counterfactual reference across Ausgrid test days.
    """
    def __init__(
        self,
        tariffs: Optional[MarketTariffs] = None,
        pricing_rule: PricingRule = PricingRule.MIDPOINT,
        bidding_strategy: BiddingStrategy = BiddingStrategy.ZI_C,
        base_seed: int = 42,
        parquet_path: str = os.path.join(PROJECT_ROOT, "data", "processed", "ausgrid_solar_attacked.parquet"),
        streamer: Optional[Step5MarketStreamer] = None
    ):
        self.tariffs = tariffs or MarketTariffs()
        self.pricing_rule = pricing_rule
        self.bidding_strategy = bidding_strategy
        self.base_seed = base_seed
        self.parquet_path = parquet_path

        self.streamer = streamer
        self.pairing_engine = LockedPairingEngine(base_seed=self.base_seed, tariffs=self.tariffs)
        self.market_engine = IntervalMarketEngine(
            tariffs=self.tariffs,
            pairing_engine=self.pairing_engine,
            pricing_rule=self.pricing_rule,
            bidding_strategy=self.bidding_strategy
        )

    def _ensure_streamer(self):
        if self.streamer is None:
            self.streamer = Step5MarketStreamer()
            self.pairing_engine.authoritative_cids = self.streamer.ids

    def load_clean_telemetry(self, start_day: int, end_day: int) -> pd.DataFrame:
        """
        Loads clean unattacked telemetry directly from authoritative parquet.
        Time range: [start_day * 48, (end_day + 1) * 48).
        """
        t_start = start_day * 48
        t_end = (end_day + 1) * 48
        table = pq.read_table(
            self.parquet_path,
            columns=["customer_id", "time_index", "P_net_clean"],
            filters=[("time_index", ">=", t_start), ("time_index", "<", t_end)]
        )
        return table.to_pandas()

    def simulate_day_regimes(
        self,
        day_index: int,
        df_stream_day: pd.DataFrame,
        df_clean_day: pd.DataFrame
    ) -> Dict[str, List[IntervalResult]]:
        """
        Simulates all 4 regimes for a single 48-slot trading day across 299 prosumers.
        """
        self._ensure_streamer()
        unique_cids = self.streamer.ids
        n_cust = len(unique_cids)

        # Telemetry matrices shaped [n_cust, 48]
        raw_pnet = df_stream_day["raw_P_net_kWh"].values.reshape(n_cust, 48)
        p_attack = df_stream_day["p_attack"].values.reshape(n_cust, 48)

        # Fallback net load: fb_gc - fb_gg
        fb_gc = self.streamer.fallback_gc[:, day_index, :]
        fb_gg = self.streamer.fallback_gg[:, day_index, :]
        fb_pnet = fb_gc - fb_gg

        # Selective defense policy (tau = 0.50 on balanced p)
        mitigate_c = (p_attack >= 0.50)
        pnet_c = np.where(mitigate_c, fb_pnet, raw_pnet)

        if isinstance(df_clean_day, np.ndarray):
            clean_pnet = df_clean_day
        else:
            clean_pnet = df_clean_day["P_net_clean"].values.reshape(n_cust, 48)

        # Quarantined ground-truth labels for post-hoc evaluation only
        gt_attacks = df_stream_day["is_attacked_ground_truth"].values.reshape(n_cust, 48)

        regimes_pnet = {
            MarketRegime.REGIME_A.value: raw_pnet,
            MarketRegime.REGIME_B.value: fb_pnet,
            MarketRegime.REGIME_C.value: pnet_c,
            MarketRegime.CLEAN.value: clean_pnet
        }

        regimes_mit = {
            MarketRegime.REGIME_A.value: np.zeros((n_cust, 48), dtype=bool),
            MarketRegime.REGIME_B.value: np.ones((n_cust, 48), dtype=bool),
            MarketRegime.REGIME_C.value: mitigate_c,
            MarketRegime.CLEAN.value: np.zeros((n_cust, 48), dtype=bool)
        }

        results: Dict[str, List[IntervalResult]] = {r: [] for r in regimes_pnet}

        for slot in range(48):
            gt_slot = gt_attacks[:, slot]
            for reg_name, pnet_matrix in regimes_pnet.items():
                pnet_slot = pnet_matrix[:, slot]
                mit_slot = regimes_mit[reg_name][:, slot]
                res = self.market_engine.simulate_interval(
                    day_index=day_index,
                    slot_index=slot,
                    customer_ids=unique_cids,
                    p_net_eff=pnet_slot,
                    regime_name=reg_name,
                    ground_truth_attacks=gt_slot,
                    mitigation_flags=mit_slot
                )
                results[reg_name].append(res)

        return results

    def run_simulation(
        self,
        start_day: int = 425,
        end_day: int = 429
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
        """
        Runs complete multi-regime simulation across days [start_day, end_day].
        """
        self._ensure_streamer()
        t0 = time.time()

        df_clean = self.load_clean_telemetry(start_day, end_day)

        interval_rows = []
        stream_gen = self.streamer.stream_test_period(
            start_day=start_day,
            end_day=end_day,
            include_quarantined_ground_truth=True
        )

        n_days = end_day - start_day + 1
        clean_pnet_all = df_clean["P_net_clean"].values.reshape(len(self.streamer.ids), n_days, 48)

        for d_rel, (d_abs, date_str, df_stream_day) in enumerate(stream_gen):
            clean_day_pnet = clean_pnet_all[:, d_rel, :]
            day_results = self.simulate_day_regimes(d_abs, df_stream_day, clean_day_pnet)

            for reg_name, slot_res_list in day_results.items():
                for res in slot_res_list:
                    interval_rows.append({
                        "day_index": res.day_index,
                        "date": date_str,
                        "slot_index": res.slot_index,
                        "regime": res.regime,
                        "n_buyers": res.n_buyers,
                        "n_sellers": res.n_sellers,
                        "n_inactive": res.n_inactive,
                        "total_demand_kWh": res.total_demand_kWh,
                        "total_supply_kWh": res.total_supply_kWh,
                        "matched_volume_kWh": res.matched_volume_kWh,
                        "unmet_demand_kWh": res.unmet_demand_kWh,
                        "unmatched_supply_kWh": res.unmatched_supply_kWh,
                        "match_rate_pct": res.match_rate_pct,
                        "vwap_aud_per_kwh": res.vwap_aud_per_kwh,
                        "buyer_surplus_aud": res.buyer_surplus_aud,
                        "seller_surplus_aud": res.seller_surplus_aud,
                        "gross_tariff_surplus_aud": res.gross_tariff_surplus_aud,
                        "grid_import_cost_aud": res.grid_import_cost_aud,
                        "grid_export_revenue_aud": res.grid_export_revenue_aud,
                        "net_grid_settlement_aud": res.net_grid_settlement_aud,
                        "n_trades": res.n_trades,
                        "corrupted_raw_energy_cleared_kWh": res.corrupted_raw_energy_cleared_kWh,
                        "attack_targeted_interval_traded_energy_kWh": res.attack_targeted_interval_traded_energy_kWh,
                        "fallback_energy_traded_kWh": res.fallback_energy_traded_kWh,
                        "clean_counterfactual_exposure_kWh": res.clean_counterfactual_exposure_kWh,
                        "n_corrupted_raw_trades": res.n_corrupted_raw_trades,
                        "n_attack_targeted_trades": res.n_attack_targeted_trades,
                        "n_fallback_trades": res.n_fallback_trades
                    })

        t_elapsed = time.time() - t0
        df_intervals = pd.DataFrame(interval_rows)

        # Aggregate daily summary
        daily_agg = df_intervals.groupby(["regime", "day_index", "date"]).agg({
            "matched_volume_kWh": "sum",
            "unmet_demand_kWh": "sum",
            "unmatched_supply_kWh": "sum",
            "total_demand_kWh": "sum",
            "total_supply_kWh": "sum",
            "buyer_surplus_aud": "sum",
            "seller_surplus_aud": "sum",
            "gross_tariff_surplus_aud": "sum",
            "grid_import_cost_aud": "sum",
            "grid_export_revenue_aud": "sum",
            "net_grid_settlement_aud": "sum",
            "n_trades": "sum",
            "corrupted_raw_energy_cleared_kWh": "sum",
            "attack_targeted_interval_traded_energy_kWh": "sum",
            "fallback_energy_traded_kWh": "sum",
            "clean_counterfactual_exposure_kWh": "sum",
            "n_corrupted_raw_trades": "sum",
            "n_attack_targeted_trades": "sum",
            "n_fallback_trades": "sum"
        }).reset_index()

        # Correct daily volume-weighted VWAP
        vwap_daily = []
        for (reg, d_idx), group in df_intervals.groupby(["regime", "day_index"]):
            tot_v = group["matched_volume_kWh"].sum()
            if tot_v > 1e-9:
                day_vwap = (group["vwap_aud_per_kwh"] * group["matched_volume_kWh"]).sum() / tot_v
            else:
                day_vwap = (self.tariffs.g_t + self.tariffs.fit) / 2.0
            vwap_daily.append({"regime": reg, "day_index": d_idx, "vwap_true": day_vwap})
        df_vwap_daily = pd.DataFrame(vwap_daily)
        daily_agg = daily_agg.merge(df_vwap_daily, on=["regime", "day_index"])
        daily_agg["daily_vwap_aud_per_kwh"] = daily_agg["vwap_true"]
        daily_agg.drop(columns=["vwap_true"], inplace=True)

        summary_stats = {
            "start_day": start_day,
            "end_day": end_day,
            "n_days": n_days,
            "n_intervals": len(df_intervals),
            "runtime_seconds": t_elapsed,
            "latency_ms_per_day": (t_elapsed / n_days) * 1000.0,
            "regimes_evaluated": list(daily_agg["regime"].unique())
        }

        return df_intervals, daily_agg, summary_stats
