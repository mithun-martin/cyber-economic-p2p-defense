"""
Step 5: Master Pipeline Execution Script
Executes the complete Economic-Aware Mitigation Decision Engine workflow:
  1. Loads preflight detector checkpoint, normalization bounds, and interval calibrator.
  2. Runs physical inference and probability calibration on the out-of-time test set (Days 425-1095).
  3. Evaluates Policy A (Fixed Threshold) and Policy B (Economic Expected-Cost Rule).
  4. Executes Cost Sensitivity Analysis across 5 economic scenarios.
  5. Computes trailing 7-day causal fallback baseline substitutions for mitigated observations.
  6. Exports tabular outputs (Parquet for interval decisions, CSV for scorecards).
"""

import json
import os
import pickle
import sys
import time
import yaml
import numpy as np
import pandas as pd
import torch

# Ensure local imports work cleanly
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
sys.path.append(os.path.join(SCRIPT_DIR, "preflight"))

from economic_decision import (
    make_economic_decision,
    make_fixed_threshold_decision,
    DecisionAction
)
from cost_model import ConfigurableCostModel, MarketState
from fallback import FallbackEngine
from train_detector import ConvAE_v2

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_yaml_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def run_pipeline():
    t_start = time.time()
    config_path = os.path.join(SCRIPT_DIR, "config", "step5_config.yaml")
    config = load_yaml_config(config_path)

    print(f"\n{'='*80}")
    print(">>> STEP 5: ECONOMIC-AWARE MITIGATION DECISION PIPELINE <<<")
    print(f"{'='*80}")
    print(f"Loaded configuration: {config_path}")
    print(f"Using device: {DEVICE} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    # 1. Load Preflight Artifacts
    ckpt_path = config["paths"]["detector_checkpoint"]
    calib_path = config["paths"]["interval_calibrator"]
    cache_path = config["paths"]["preflight_cache"]

    print(f"\n[Loading Artifacts]")
    print(f"  -> Checkpoint: {ckpt_path}")
    model = ConvAE_v2().to(DEVICE)
    model.load_state_dict(torch.load(ckpt_path, map_location=DEVICE))
    model.eval()

    print(f"  -> Calibrator: {calib_path}")
    with open(calib_path, "rb") as f:
        calib_dict = pickle.load(f)
    w_int = calib_dict["weight_w"]
    b_int = calib_dict["bias_b"]
    print(f"     Platt parameters: w = {w_int:.6f}, b = {b_int:.6f}")

    print(f"  -> Cache: {cache_path}")
    cache = torch.load(cache_path, map_location="cpu")
    X = cache["X"]                          # [299, 1096, 2, 48]
    y_int = cache["y_interval"].numpy()      # [299, 1096, 48]
    tele_raw = cache["tele_raw"].numpy()     # [299, 1096, 48, 2]
    phase_day = cache["phase_day"].numpy()   # [299, 1096]
    ids = cache["ids"].numpy()
    n_cust, n_days, n_ch, n_slots = X.shape

    # Test set partition: Days 425 to 1095 (671 out-of-time days)
    TEST_START = 425
    TEST_END = 1095
    n_test_days = TEST_END - TEST_START + 1
    total_test_intervals = n_cust * n_test_days * n_slots

    print(f"\n[Evaluation Partition]")
    print(f"  -> Test Days: {TEST_START} to {TEST_END} ({n_test_days} days)")
    print(f"  -> Prosumers: {n_cust}")
    print(f"  -> Total Intervals to Evaluate: {total_test_intervals:,}")

    # 2. Compute Reconstruction Errors & Calibrated Probabilities on Test Set
    print("\n[Inference] Running forward passes across test telemetry on GPU...")
    sub_X = X[:, TEST_START:TEST_END + 1].reshape(-1, n_ch, n_slots)
    n_windows = len(sub_X)
    batch_size = 64
    int_errs = []

    with torch.no_grad():
        for i in range(0, n_windows, batch_size):
            bx = sub_X[i:i + batch_size].to(DEVICE)
            recon = model(bx)
            diff2 = (bx - recon) ** 2
            err = diff2.mean(dim=1) # [B, 48]
            int_errs.append(err.cpu().numpy())

    test_errors = np.concatenate(int_errs, axis=0) # [n_cust * n_test_days, 48]
    test_errors = test_errors.reshape(n_cust, n_test_days, n_slots)

    # Compute Calibrated Probabilities via Platt Sigmoid
    feat = np.log(test_errors + 1e-12)
    test_p_attack = 1.0 / (1.0 + np.exp(-(w_int * feat + b_int)))
    print(f"  -> Calibrated p_attack range: [{test_p_attack.min():.4f}, {test_p_attack.max():.4f}], mean: {test_p_attack.mean():.4f}")

    # Extract ground truth slice for evaluation only (NEVER given to decision engine)
    test_y_true = y_int[:, TEST_START:TEST_END + 1] # [n_cust, n_test_days, 48]
    test_tele = tele_raw[:, TEST_START:TEST_END + 1] # [n_cust, n_test_days, 48, 2]

    # Flatten arrays for vector evaluation
    flat_p = test_p_attack.flatten()
    flat_y = test_y_true.flatten()
    flat_gc = test_tele[:, :, :, 0].flatten()
    flat_gg = test_tele[:, :, :, 1].flatten()
    flat_pnet = flat_gc - flat_gg

    # 3. Policy Evaluation: Policy A (Fixed Thresholds) vs. Policy B (Baseline Economic)
    print("\n[Policy Comparison] Evaluating Policy A vs. Policy B on Baseline Scenario...")
    baseline_cfg = config["baseline_costs"]
    c_fn = baseline_cfg["C_FN"]
    c_fp = baseline_cfg["C_FP"]
    c_m = baseline_cfg["C_M"]

    # Policy B: Economic Decision Engine
    econ_decisions = make_economic_decision(flat_p, c_fn, c_fp, c_m)
    b_dec = econ_decisions["decision"] # array of 'ALLOW' / 'MITIGATE'
    b_loss_allow = econ_decisions["expected_loss_allow"]
    b_loss_mitigate = econ_decisions["expected_loss_mitigate"]
    b_modeled_loss = np.where(b_dec == DecisionAction.MITIGATE, b_loss_mitigate, b_loss_allow)

    # Policy A: Fixed Thresholds (tau = 0.50, 0.30, 0.70)
    thresh_primary = config["fixed_threshold_policy"]["primary_threshold"]
    fixed_decisions_50 = make_fixed_threshold_decision(flat_p, threshold=thresh_primary)["decision"]
    fixed_decisions_30 = make_fixed_threshold_decision(flat_p, threshold=0.30)["decision"]
    fixed_decisions_70 = make_fixed_threshold_decision(flat_p, threshold=0.70)["decision"]

    def compute_policy_metrics(decisions_arr, loss_arr, policy_name, threshold_val=None):
        mit_mask = (decisions_arr == DecisionAction.MITIGATE)
        n_mit = int(mit_mask.sum())
        n_allow = len(decisions_arr) - n_mit
        mit_rate = n_mit / len(decisions_arr) * 100.0

        # Confusion Matrix against ground truth
        tp = int(((decisions_arr == DecisionAction.MITIGATE) & (flat_y == 1)).sum())
        fp = int(((decisions_arr == DecisionAction.MITIGATE) & (flat_y == 0)).sum())
        tn = int(((decisions_arr == DecisionAction.ALLOW) & (flat_y == 0)).sum())
        fn = int(((decisions_arr == DecisionAction.ALLOW) & (flat_y == 1)).sum())

        recall = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
        precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        # Disagreement with Economic Policy B
        disagree_with_econ = int((decisions_arr != b_dec).sum())
        disagree_pct = disagree_with_econ / len(decisions_arr) * 100.0

        return {
            "Policy": policy_name,
            "Threshold": threshold_val if threshold_val is not None else "Dynamic Expected-Cost",
            "Mitigation_Rate_%": mit_rate,
            "ALLOW_Count": n_allow,
            "MITIGATE_Count": n_mit,
            "True_Positives": tp,
            "False_Positives": fp,
            "True_Negatives": tn,
            "False_Negatives": fn,
            "Recall_DR_%": recall,
            "Precision_%": precision,
            "F1_Score_%": f1,
            "Total_Modeled_Loss_AUD": float(loss_arr.sum()),
            "Mean_Loss_Per_Interval_AUD": float(loss_arr.mean()),
            "Disagreement_With_Policy_B_%": disagree_pct
        }

    # Modeled loss for fixed thresholds evaluated under baseline economic cost structure
    fixed_loss_50 = np.where(fixed_decisions_50 == DecisionAction.MITIGATE, b_loss_mitigate, b_loss_allow)
    fixed_loss_30 = np.where(fixed_decisions_30 == DecisionAction.MITIGATE, b_loss_mitigate, b_loss_allow)
    fixed_loss_70 = np.where(fixed_decisions_70 == DecisionAction.MITIGATE, b_loss_mitigate, b_loss_allow)

    policy_rows = [
        compute_policy_metrics(b_dec, b_modeled_loss, "Policy B: Economic-Aware Expected Cost (Baseline 5:1)", None),
        compute_policy_metrics(fixed_decisions_50, fixed_loss_50, "Policy A: Fixed Threshold (tau = 0.50)", 0.50),
        compute_policy_metrics(fixed_decisions_30, fixed_loss_30, "Policy A: Fixed Threshold (tau = 0.30)", 0.30),
        compute_policy_metrics(fixed_decisions_70, fixed_loss_70, "Policy A: Fixed Threshold (tau = 0.70)", 0.70),
    ]
    df_policies = pd.DataFrame(policy_rows)

    print("\n" + "=" * 115)
    print(" ⚖️ POLICY HEAD-TO-HEAD COMPARISON ON 9.63 MILLION TEST INTERVALS")
    print("=" * 115)
    print(df_policies[["Policy", "Mitigation_Rate_%", "Recall_DR_%", "Precision_%", "F1_Score_%", "Total_Modeled_Loss_AUD", "Disagreement_With_Policy_B_%"]].to_string(index=False))

    policy_csv_path = os.path.join(SCRIPT_DIR, "outputs", "step5_policy_comparison.csv")
    df_policies.to_csv(policy_csv_path, index=False)
    print(f"\n[Saved] Policy comparison scorecard: {policy_csv_path}")

    # 4. Cost Sensitivity Analysis across Scenarios
    print("\n[Sensitivity Analysis] Executing Economic Cost Sensitivity Scenarios...")
    sensitivity_rows = []

    for sc in config["sensitivity_scenarios"]:
        sc_id = sc["id"]
        sc_name = sc["name"]
        sc_fn = sc["C_FN"]
        sc_fp = sc["C_FP"]
        sc_m = sc["C_M"]

        sc_res = make_economic_decision(flat_p, sc_fn, sc_fp, sc_m)
        s_dec = sc_res["decision"]
        s_loss = np.where(s_dec == DecisionAction.MITIGATE, sc_res["expected_loss_mitigate"], sc_res["expected_loss_allow"])

        # Breakeven probability: where E[Loss(ALLOW)] == E[Loss(MITIGATE)]
        # p * C_FN = (1-p) * C_FP + C_M => p*(C_FN + C_FP) = C_FP + C_M => p* = (C_FP + C_M) / (C_FN + C_FP)
        p_breakeven = (sc_fp + sc_m) / (sc_fn + sc_fp) if (sc_fn + sc_fp) > 0 else 0.50

        s_metrics = compute_policy_metrics(s_dec, s_loss, sc_name)
        s_metrics.update({
            "Scenario_ID": sc_id,
            "C_FN_AUD": sc_fn,
            "C_FP_AUD": sc_fp,
            "C_M_AUD": sc_m,
            "Cost_Ratio_FN_to_FP": sc_fn / sc_fp if sc_fp > 0 else float("inf"),
            "Breakeven_Probability_p*": p_breakeven
        })
        sensitivity_rows.append(s_metrics)

    df_sensitivity = pd.DataFrame(sensitivity_rows)
    # Order columns
    sc_cols = [
        "Scenario_ID", "Policy", "C_FN_AUD", "C_FP_AUD", "C_M_AUD", "Cost_Ratio_FN_to_FP",
        "Breakeven_Probability_p*", "Mitigation_Rate_%", "Recall_DR_%", "Precision_%",
        "F1_Score_%", "Total_Modeled_Loss_AUD", "Disagreement_With_Policy_B_%"
    ]
    df_sensitivity = df_sensitivity[sc_cols]

    print("\n" + "=" * 125)
    print(" 📊 COST SENSITIVITY SCORECARD (5 ECONOMIC SCENARIOS)")
    print("=" * 125)
    print(df_sensitivity[["Scenario_ID", "Cost_Ratio_FN_to_FP", "Breakeven_Probability_p*", "Mitigation_Rate_%", "Recall_DR_%", "Precision_%", "F1_Score_%", "Total_Modeled_Loss_AUD"]].to_string(index=False))

    sensitivity_csv_path = os.path.join(SCRIPT_DIR, "outputs", "step5_sensitivity_analysis.csv")
    df_sensitivity.to_csv(sensitivity_csv_path, index=False)
    print(f"\n[Saved] Sensitivity scorecard: {sensitivity_csv_path}")

    # 5. Trailing 7-Day Historical Baseline Fallback
    print("\n[Fallback Engine] Computing strictly causal trailing 7-day baselines...")
    fallback_engine = FallbackEngine(trailing_days=7)
    fallback_gc, fallback_gg = fallback_engine.compute_all_trailing_baselines(tele_raw)
    print(f"  -> Precomputed historical fallback tensor shape: {fallback_gc.shape}")

    # 6. Generate Parquet Output for Sample Cohort (Step 6 CDA Contract)
    # Extract 10 sample prosumers across test days to provide concrete Parquet schema for Step 6
    sample_cust_count = config["output_settings"]["sample_customers_count"]
    sample_cust_indices = list(range(min(sample_cust_count, n_cust)))
    sample_ids = ids[sample_cust_indices]

    print(f"\n[Exporting Sample Parquet] Exporting interval-level decisions for {len(sample_cust_indices)} prosumers...")
    sample_records = []

    # Map dates for test days
    # Days 425 to 1095 start from 2011-08-30 (Day 0 = 2010-07-01)
    base_date = pd.Timestamp("2010-07-01")

    for c_idx in sample_cust_indices:
        cid = int(ids[c_idx])
        for d_rel, d_abs in enumerate(range(TEST_START, TEST_END + 1)):
            day_date = str((base_date + pd.Timedelta(days=d_abs)).date())
            p_day = test_p_attack[c_idx, d_rel] # [48]
            y_day = test_y_true[c_idx, d_rel]   # [48]
            err_day = test_errors[c_idx, d_rel] # [48]
            raw_gc_day = tele_raw[c_idx, d_abs, :, 0]
            raw_gg_day = tele_raw[c_idx, d_abs, :, 1]
            fb_gc_day = fallback_gc[c_idx, d_abs]
            fb_gg_day = fallback_gg[c_idx, d_abs]

            # Evaluate economic decision for the 48 intervals
            dec_dict = make_economic_decision(p_day, c_fn, c_fp, c_m)

            for s in range(n_slots):
                time_idx = d_abs * n_slots + s
                p_val = float(p_day[s])
                dec = dec_dict["decision"][s]
                reason = dec_dict["decision_reason"][s]
                la = float(dec_dict["expected_loss_allow"][s])
                lm = float(dec_dict["expected_loss_mitigate"][s])

                # Energy substitution: use fallback if MITIGATE, else raw
                if dec == DecisionAction.MITIGATE:
                    sub_gc = float(fb_gc_day[s])
                    sub_gg = float(fb_gg_day[s])
                    strat = "trailing_7day_slot_average"
                else:
                    sub_gc = float(raw_gc_day[s])
                    sub_gg = float(raw_gg_day[s])
                    strat = "none (raw observation allowed)"

                sample_records.append({
                    "customer_id": cid,
                    "date": day_date,
                    "day_index": d_abs,
                    "time_index": time_idx,
                    "interval_index": s,
                    "raw_GC_kWh": float(raw_gc_day[s]),
                    "raw_GG_kWh": float(raw_gg_day[s]),
                    "raw_P_net_kWh": float(raw_gc_day[s] - raw_gg_day[s]),
                    "reconstruction_error": float(err_day[s]),
                    "p_attack": p_val,
                    "C_FN_AUD": c_fn,
                    "C_FP_AUD": c_fp,
                    "C_M_AUD": c_m,
                    "expected_loss_allow": la,
                    "expected_loss_mitigate": lm,
                    "decision": dec,
                    "decision_reason": reason,
                    "mitigation_strategy": strat,
                    "substituted_GC_kWh": sub_gc,
                    "substituted_GG_kWh": sub_gg,
                    "substituted_P_net_kWh": float(sub_gc - sub_gg),
                    "is_attacked_ground_truth": int(y_day[s])
                })

    df_sample = pd.DataFrame(sample_records)
    sample_parquet_path = os.path.join(SCRIPT_DIR, "outputs", "step5_decisions_sample.parquet")
    df_sample.to_parquet(sample_parquet_path, index=False)
    print(f"[Saved] Sample decisions Parquet: {sample_parquet_path} ({len(df_sample):,} rows, {os.path.getsize(sample_parquet_path):,} bytes)")

    elapsed_min = (time.time() - t_start) / 60.0
    print(f"\n[Complete] Step 5 Pipeline finished successfully in {elapsed_min:.2f} minutes.")
    return df_policies, df_sensitivity, df_sample


if __name__ == "__main__":
    run_pipeline()
