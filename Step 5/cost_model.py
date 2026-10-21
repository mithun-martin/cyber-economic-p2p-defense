"""
Step 5: Cost Model and Market-State Interface
Provides configurable economic cost parameters (C_FN, C_FP, C_M) and defines
the injectable interface for Step 6 Continuous Double Auction (CDA) market states.

When market state is absent (Step 5 standalone), uses verified baseline cost configurations.
When market state is injected by Step 6, calculates dynamic economic impacts based on
order volume, clearing prices, and grid imbalance tariffs.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Union
import numpy as np
import pandas as pd


@dataclass
class MarketState:
    """
    Market State Interface for Step 6 CDA Simulator.
    Contains economic telemetry required to calculate state-dependent costs.
    """
    net_volume_kwh: float                    # P_net = GC - GG (positive = buyer, negative = seller)
    order_price: Optional[float] = None      # Bid or ask price ($/kWh)
    market_clearing_price: Optional[float] = None # Cleared P2P price ($/kWh) if available
    retail_tariff: float = 0.30              # Utility grid consumption tariff ($/kWh)
    feed_in_tariff: float = 0.08             # Solar feed-in tariff ($/kWh)
    imbalance_penalty_rate: float = 0.45     # Grid imbalance penalty rate ($/kWh)
    mitigation_fee: float = 0.01             # Administrative mitigation fee ($)


class BaseCostModel:
    """Base cost model protocol."""
    def get_costs(
        self,
        market_state: Optional[Union[MarketState, Dict]] = None
    ) -> Tuple_Costs:
        raise NotImplementedError


# Named tuple or dict type alias for costs
Tuple_Costs = Dict[str, float]


class ConfigurableCostModel(BaseCostModel):
    """
    Configurable Cost Model supporting both static scenario costs and
    injectable dynamic market-state calculations for Step 6.
    """
    def __init__(
        self,
        c_fn_base: float = 0.50,
        c_fp_base: float = 0.10,
        c_m_base: float = 0.01,
        volume_scaling_enabled: bool = False,
        fn_per_kwh: float = 0.35,
        fp_per_kwh: float = 0.11
    ):
        if c_fn_base < 0 or c_fp_base < 0 or c_m_base < 0:
            raise ValueError("Cost parameters must be non-negative.")
        self.c_fn_base = float(c_fn_base)
        self.c_fp_base = float(c_fp_base)
        self.c_m_base = float(c_m_base)
        self.volume_scaling_enabled = volume_scaling_enabled
        self.fn_per_kwh = float(fn_per_kwh)
        self.fp_per_kwh = float(fp_per_kwh)

    def get_costs(
        self,
        market_state: Optional[Union[MarketState, Dict]] = None,
        volume_kwh: Optional[float] = None
    ) -> Tuple_Costs:
        """
        Calculates C_FN, C_FP, and C_M for an observation.
        If market_state is None and volume_scaling_enabled is False, returns constant baseline.
        """
        # Step 6 Dynamic Market State Injection
        if market_state is not None:
            if isinstance(market_state, dict):
                vol = abs(market_state.get("net_volume_kwh", 0.0))
                imbalance_rate = market_state.get("imbalance_penalty_rate", 0.45)
                g_t = market_state.get("retail_tariff", 0.30)
                fit = market_state.get("feed_in_tariff", 0.08)
                p_p2p = market_state.get("market_clearing_price", (g_t + fit) / 2.0)
                c_m = market_state.get("mitigation_fee", self.c_m_base)
            else:
                vol = abs(market_state.net_volume_kwh)
                imbalance_rate = market_state.imbalance_penalty_rate
                g_t = market_state.retail_tariff
                fit = market_state.feed_in_tariff
                p_p2p = market_state.market_clearing_price or ((g_t + fit) / 2.0)
                c_m = market_state.mitigation_fee

            # Financial harm of undetected false negative:
            # Unmitigated corrupt telemetry drives physical deviation settled at penalty rate
            c_fn = max(self.c_fn_base, imbalance_rate * vol)
            # Opportunity cost of false positive (unnecessary fallback):
            # Forfeited P2P trading surplus relative to default utility tariff
            surplus_spread = abs(p_p2p - fit) if market_state.net_volume_kwh < 0 else abs(g_t - p_p2p)
            c_fp = max(self.c_fp_base, surplus_spread * vol)
            return {"C_FN": float(c_fn), "C_FP": float(c_fp), "C_M": float(c_m)}

        # Optional Volume-Scaled Cost (based solely on observed net energy)
        if self.volume_scaling_enabled and volume_kwh is not None:
            vol = abs(volume_kwh)
            c_fn = self.c_fn_base + self.fn_per_kwh * vol
            c_fp = self.c_fp_base + self.fp_per_kwh * vol
            return {"C_FN": float(c_fn), "C_FP": float(c_fp), "C_M": self.c_m_base}

        # Baseline Static Cost Model
        return {
            "C_FN": self.c_fn_base,
            "C_FP": self.c_fp_base,
            "C_M": self.c_m_base
        }

    def get_costs_vectorized(
        self,
        volumes_kwh: Optional[Union[np.ndarray, pd.Series]] = None
    ) -> Dict[str, Union[float, np.ndarray]]:
        """
        Returns cost arrays or broadcastable scalars for vectorized batch evaluation.
        """
        if self.volume_scaling_enabled and volumes_kwh is not None:
            v_arr = np.abs(np.asarray(volumes_kwh, dtype=np.float64))
            c_fn_arr = self.c_fn_base + self.fn_per_kwh * v_arr
            c_fp_arr = self.c_fp_base + self.fp_per_kwh * v_arr
            return {
                "C_FN": c_fn_arr,
                "C_FP": c_fp_arr,
                "C_M": self.c_m_base
            }
        return {
            "C_FN": self.c_fn_base,
            "C_FP": self.c_fp_base,
            "C_M": self.c_m_base
        }
