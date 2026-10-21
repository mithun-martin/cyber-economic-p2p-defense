"""
Step 5 Production Streaming Engine for Step 6 CDA Market Simulator.

Provides an optimized, strictly causal, chunked daily batch generator:
  stream_market_days() yields:
    (day_index, date_str, df_day_market)
for every test day d in [start_day, end_day].

Contract Invariants Enforced:
  1. Full Population Coverage: 299 active prosumers x 48 intervals = 14,352 records/day.
  2. Index Alignment & Key Uniqueness: (customer_id, time_index) composite key is guaranteed unique.
  3. Strict Causality: Fallback substitutions use ONLY historical observations from d' < d.
  4. Telemetry Conservation: Raw telemetry columns remain unmodified.
  5. Information Isolation: Attack labels are strictly excluded from order dispatch fields.
  6. Sign Conventions: Positive P_net => BUYER (Bid), Negative P_net => SELLER (Ask), Zero => BALANCED.
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
import torch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
sys.path.append(os.path.join(SCRIPT_DIR, "preflight"))

from train_detector import ConvAE_v2
from fallback import FallbackEngine
from economic_decision import make_economic_decision, DecisionAction

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
BASE_DATE = pd.Timestamp("2010-07-01")


class Step5MarketStreamer:
    """
    Production-grade streaming generator providing Step 6 CDA with order-ready market records.
    """
    def __init__(
        self,
        cache_path: str = os.path.join(SCRIPT_DIR, "preflight", "cache_299.pt"),
        ckpt_path: str = os.path.join(SCRIPT_DIR, "preflight", "detector_checkpoint.pt"),
        calib_path: str = os.path.join(SCRIPT_DIR, "preflight", "interval_calibrator.pkl"),
        c_fn: float = 0.50,
        c_fp: float = 0.10,
        c_m: float = 0.01,
        trailing_fallback_days: int = 7
    ):
        self.c_fn = c_fn
        self.c_fp = c_fp
        self.c_m = c_m

        # 1. Load dataset cache
        cache = torch.load(cache_path, map_location="cpu")
        self.X = cache["X"]                       # [299, 1096, 2, 48]
        self.tele_raw = cache["tele_raw"].numpy() # [299, 1096, 48, 2]
        self.ids = cache["ids"].numpy()           # [299]
        self.y_interval = cache["y_interval"].numpy() # [299, 1096, 48] (quarantined)

        self.n_cust, self.n_days, self.n_ch, self.n_slots = self.X.shape

        # 2. Load model
        self.model = ConvAE_v2().to(DEVICE)
        self.model.load_state_dict(torch.load(ckpt_path, map_location=DEVICE))
        self.model.eval()

        # 3. Load calibrator
        with open(calib_path, "rb") as f:
            calib_dict = pickle.load(f)
        self.w = float(calib_dict["weight_w"])
        self.b = float(calib_dict["bias_b"])

        # 4. Precompute strictly causal historical baseline fallback tensor
        fallback_engine = FallbackEngine(trailing_days=trailing_fallback_days)
        self.fallback_gc, self.fallback_gg = fallback_engine.compute_all_trailing_baselines(self.tele_raw)

    def generate_day(
        self,
        day_index: int,
        calibrated_probs_day: np.ndarray,
        recon_errors_day: np.ndarray,
        include_quarantined_ground_truth: bool = False
    ) -> pd.DataFrame:
        """
        Generates the 14,352-record market DataFrame for a single trading day across all 299 prosumers.
        """
        date_str = str((BASE_DATE + pd.Timedelta(days=day_index)).date())
        
        # Grid indices
        cids = np.repeat(self.ids, self.n_slots)                          # [14352]
        slots = np.tile(np.arange(self.n_slots), self.n_cust)             # [14352]
        time_indices = day_index * self.n_slots + slots                    # [14352]
        day_indices = np.full(len(cids), day_index, dtype=np.int64)

        # Raw Telemetry
        raw_gc = self.tele_raw[:, day_index, :, 0].flatten()              # [14352]
        raw_gg = self.tele_raw[:, day_index, :, 1].flatten()              # [14352]
        raw_pnet = raw_gc - raw_gg

        # Flattened probabilities and errors
        p_day = calibrated_probs_day.flatten()                            # [14352]
        err_day = recon_errors_day.flatten()                              # [14352]

        # Economic Decision
        dec_res = make_economic_decision(p_day, self.c_fn, self.c_fp, self.c_m)
        decisions = dec_res["decision"]                                   # [14352] array of 'ALLOW'/'MITIGATE'
        is_mit = (decisions == DecisionAction.MITIGATE)

        # Fallback values
        fb_gc = self.fallback_gc[:, day_index, :].flatten()               # [14352]
        fb_gg = self.fallback_gg[:, day_index, :].flatten()               # [14352]

        # Effective telemetry (mitigation substitution)
        eff_gc = np.where(is_mit, fb_gc, raw_gc)
        eff_gg = np.where(is_mit, fb_gg, raw_gg)
        eff_pnet = eff_gc - eff_gg

        # Market Role
        roles = np.where(eff_pnet > 1e-9, "BUYER", np.where(eff_pnet < -1e-9, "SELLER", "BALANCED"))
        strategies = np.where(is_mit, "trailing_7day_slot_average", "none (raw observation allowed)")

        record_dict = {
            "customer_id": cids,
            "date": np.full(len(cids), date_str),
            "day_index": day_indices,
            "time_index": time_indices,
            "slot_index": slots,
            "raw_GC_kWh": raw_gc.astype(np.float64),
            "raw_GG_kWh": raw_gg.astype(np.float64),
            "raw_P_net_kWh": raw_pnet.astype(np.float64),
            "reconstruction_error": err_day.astype(np.float64),
            "p_attack": p_day.astype(np.float64),
            "C_FN_AUD": np.full(len(cids), self.c_fn, dtype=np.float64),
            "C_FP_AUD": np.full(len(cids), self.c_fp, dtype=np.float64),
            "C_M_AUD": np.full(len(cids), self.c_m, dtype=np.float64),
            "expected_loss_allow": dec_res["expected_loss_allow"].astype(np.float64),
            "expected_loss_mitigate": dec_res["expected_loss_mitigate"].astype(np.float64),
            "decision": decisions,
            "decision_reason": dec_res["decision_reason"],
            "mitigation_strategy": strategies,
            "substituted_GC_kWh": eff_gc.astype(np.float64),
            "substituted_GG_kWh": eff_gg.astype(np.float64),
            "substituted_P_net_kWh": eff_pnet.astype(np.float64),
            "market_role": roles
        }

        if include_quarantined_ground_truth:
            y_day = self.y_interval[:, day_index, :].flatten()
            record_dict["is_attacked_ground_truth"] = y_day.astype(np.int64)

        return pd.DataFrame(record_dict)

    def stream_test_period(
        self,
        start_day: int = 425,
        end_day: int = 1095,
        include_quarantined_ground_truth: bool = False
    ):
        """
        Chronologically yields market order batches for each day in [start_day, end_day].
        Precomputes GPU inferences in efficient vectorized batches, then yields day-by-day.
        """
        n_eval_days = end_day - start_day + 1

        # Run forward inference over the evaluation window
        sub_X = self.X[:, start_day:end_day + 1].reshape(-1, self.n_ch, self.n_slots)
        n_windows = len(sub_X)
        batch_size = 128
        int_errs = []

        with torch.no_grad():
            for i in range(0, n_windows, batch_size):
                bx = sub_X[i:i + batch_size].to(DEVICE)
                recon = self.model(bx)
                err = ((bx - recon) ** 2).mean(dim=1)
                int_errs.append(err.cpu().numpy())

        # Shape: [n_cust, n_eval_days, 48]
        recon_errors = np.concatenate(int_errs, axis=0).reshape(self.n_cust, n_eval_days, self.n_slots)
        feat = np.log(recon_errors + 1e-12)
        calibrated_probs = 1.0 / (1.0 + np.exp(-(self.w * feat + self.b)))

        # Chronological day-by-day generator
        for d_rel, d_abs in enumerate(range(start_day, end_day + 1)):
            date_str = str((BASE_DATE + pd.Timedelta(days=d_abs)).date())
            df_day = self.generate_day(
                day_index=d_abs,
                calibrated_probs_day=calibrated_probs[:, d_rel, :],
                recon_errors_day=recon_errors[:, d_rel, :],
                include_quarantined_ground_truth=include_quarantined_ground_truth
            )
            yield d_abs, date_str, df_day
