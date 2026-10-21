"""
Script to compute Step 5.1 Audit Data and export the three required CSV deliverables:
1. Step 5/outputs/step5_1_calibration_audit.csv
2. Step 5/outputs/step5_1_policy_comparison.csv
3. Step 5/outputs/step5_1_sensitivity_analysis.csv
"""

import os
import sys
import json
import pickle
import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score, average_precision_score

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
sys.path.append(os.path.join(SCRIPT_DIR, "preflight"))

from train_detector import ConvAE_v2
from economic_decision import (
    make_economic_decision,
    make_fixed_threshold_decision,
    DecisionAction
)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def compute_ece(probs, labels, n_bins=10):
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(probs)
    for i in range(n_bins):
        b_min = bin_boundaries[i]
        b_max = bin_boundaries[i + 1]
        mask = (probs >= b_min) & (probs < b_max) if i < n_bins - 1 else (probs >= b_min) & (probs <= b_max)
        n_b = np.sum(mask)
        if n_b > 0:
            acc = np.mean(labels[mask])
            conf = np.mean(probs[mask])
            ece += (n_b / n) * np.abs(acc - conf)
    return ece

def main():
    print(f"Loading preflight cache and model checkpoint on device {DEVICE}...")
    cache = torch.load("Step 5/preflight/cache_299.pt", map_location="cpu")
    X = cache["X"] # [299, 1096, 2, 48]
    y_int = cache["y_interval"].numpy() # [299, 1096, 48]
    phase_day = cache["phase_day"].numpy() # [299, 1096]
    n_cust, n_days, n_ch, n_slots = X.shape

    # Partitions
    CALIB_START, CALIB_END = 365, 424 # 60 days
    TEST_START, TEST_END = 425, 1095  # 671 days

    # Load ConvAE_v2
    model = ConvAE_v2().to(DEVICE)
    model.load_state_dict(torch.load("Step 5/preflight/detector_checkpoint.pt", map_location=DEVICE))
    model.eval()

    # Load existing balanced interval calibrator
    with open("Step 5/preflight/interval_calibrator.pkl", "rb") as f:
        calib_dict = pickle.load(f)
    w_bal = calib_dict["weight_w"]
    b_bal = calib_dict["bias_b"]
    print(f"Loaded existing Balanced Platt Calibrator: w={w_bal:.6f}, b={b_bal:.6f}")

    # Compute errors on Calibration partition
    print("\nComputing reconstruction errors on Calibration Partition (Days 365-424)...")
    calib_X = X[:, CALIB_START:CALIB_END + 1].reshape(-1, n_ch, n_slots)
    calib_errs = []
    with torch.no_grad():
        for i in range(0, len(calib_X), 128):
            bx = calib_X[i:i + 128].to(DEVICE)
            recon = model(bx)
            diff2 = (bx - recon) ** 2
            calib_errs.append(diff2.mean(dim=1).cpu().numpy())
    calib_errs = np.concatenate(calib_errs, axis=0).flatten()
    calib_y = y_int[:, CALIB_START:CALIB_END + 1].flatten()

    # Compute errors on Test partition
    print("Computing reconstruction errors on Test Partition (Days 425-1095)...")
    test_X = X[:, TEST_START:TEST_END + 1].reshape(-1, n_ch, n_slots)
    test_errs = []
    with torch.no_grad():
        for i in range(0, len(test_X), 128):
            bx = test_X[i:i + 128].to(DEVICE)
            recon = model(bx)
            diff2 = (bx - recon) ** 2
            test_errs.append(diff2.mean(dim=1).cpu().numpy())
    test_errs = np.concatenate(test_errs, axis=0).flatten()
    test_y = y_int[:, TEST_START:TEST_END + 1].flatten()

    # Feature transformation
    calib_feat = np.log(calib_errs + 1e-12).reshape(-1, 1)
    test_feat = np.log(test_errs + 1e-12).reshape(-1, 1)

    # Fit standard unweighted Platt calibrator on Calibration partition
    print("\nFitting Standard Unweighted Platt Calibrator (without class_weight='balanced')...")
    lr_unweighted = LogisticRegression(solver='lbfgs', max_iter=1000)
    lr_unweighted.fit(calib_feat, calib_y)
    w_unw = float(lr_unweighted.coef_[0][0])
    b_unw = float(lr_unweighted.intercept_[0])
    print(f"Fitted Unweighted Platt Calibrator: w={w_unw:.6f}, b={b_unw:.6f}")

    # Generate probabilities
    # 1. Balanced Platt (existing Step 5)
    p_calib_bal = 1.0 / (1.0 + np.exp(-(w_bal * calib_feat.ravel() + b_bal)))
    p_test_bal = 1.0 / (1.0 + np.exp(-(w_bal * test_feat.ravel() + b_bal)))

    # 2. Standard Unweighted Platt
    p_calib_unw = 1.0 / (1.0 + np.exp(-(w_unw * calib_feat.ravel() + b_unw)))
    p_test_unw = 1.0 / (1.0 + np.exp(-(w_unw * test_feat.ravel() + b_unw)))

    # Min-max normalized raw score for reference
    raw_calib_norm = (calib_errs - calib_errs.min()) / (calib_errs.max() - calib_errs.min())
    raw_test_norm = (test_errs - test_errs.min()) / (test_errs.max() - test_errs.min())

    # =========================================================================
    # 1. DELIVERABLE: Calibration Audit CSV
    # =========================================================================
    print("\nGenerating Step 5/outputs/step5_1_calibration_audit.csv...")
    calib_rows = []

    def get_metrics(name, partition, p_arr, y_arr, w_val, b_val):
        brier = brier_score_loss(y_arr, p_arr)
        ll = log_loss(y_arr, p_arr)
        auroc = roc_auc_score(y_arr, p_arr)
        auprc = average_precision_score(y_arr, p_arr)
        ece = compute_ece(p_arr, y_arr, n_bins=10)
        prev = np.mean(y_arr) * 100.0
        return {
            "Calibrator": name,
            "Partition": partition,
            "N_Intervals": len(y_arr),
            "Attack_Prevalence_%": prev,
            "Param_w": w_val,
            "Param_b": b_val,
            "Prob_Min": float(np.min(p_arr)),
            "Prob_Max": float(np.max(p_arr)),
            "Prob_Mean": float(np.mean(p_arr)),
            "Prob_Std": float(np.std(p_arr)),
            "Brier_Score": float(brier),
            "Log_Loss": float(ll),
            "AUROC": float(auroc),
            "AUPRC": float(auprc),
            "ECE": float(ece)
        }

    calib_rows.append(get_metrics("Balanced Platt (Existing Step 5)", "Calibration (Days 365-424)", p_calib_bal, calib_y, w_bal, b_bal))
    calib_rows.append(get_metrics("Balanced Platt (Existing Step 5)", "Test (Days 425-1095)", p_test_bal, test_y, w_bal, b_bal))
    calib_rows.append(get_metrics("Standard Unweighted Platt (Proposed)", "Calibration (Days 365-424)", p_calib_unw, calib_y, w_unw, b_unw))
    calib_rows.append(get_metrics("Standard Unweighted Platt (Proposed)", "Test (Days 425-1095)", p_test_unw, test_y, w_unw, b_unw))
    calib_rows.append(get_metrics("Normalized Raw Score (Uncalibrated)", "Test (Days 425-1095)", raw_test_norm, test_y, None, None))

    df_calib_audit = pd.DataFrame(calib_rows)
    df_calib_audit.to_csv("Step 5/outputs/step5_1_calibration_audit.csv", index=False)
    print("Saved: Step 5/outputs/step5_1_calibration_audit.csv")

    # =========================================================================
    # 2. DELIVERABLE: Policy Comparison CSV
    # =========================================================================
    print("\nEvaluating all 6 Policy Baselines under Baseline Cost Structure ($C_{FN}=0.50, C_{FP}=0.10, C_{M}=0.01$)...")
    c_fn = 0.50
    c_fp = 0.10
    c_m = 0.01
    total_test = len(test_y)

    # Decisions for the 6 policies using p_test_bal (frozen Step 5 probabilities)
    # 1. Policy A (0.50)
    dec_50 = np.where(p_test_bal >= 0.50, DecisionAction.MITIGATE, DecisionAction.ALLOW)
    # 2. Policy A (0.30)
    dec_30 = np.where(p_test_bal >= 0.30, DecisionAction.MITIGATE, DecisionAction.ALLOW)
    # 3. Policy A (0.70)
    dec_70 = np.where(p_test_bal >= 0.70, DecisionAction.MITIGATE, DecisionAction.ALLOW)
    # 4. Policy B (Baseline Economic)
    econ_res = make_economic_decision(p_test_bal, c_fn, c_fp, c_m)
    dec_econ = econ_res["decision"]
    # 5. Always Mitigate
    dec_always = np.full(total_test, DecisionAction.MITIGATE)
    # 6. Never Mitigate
    dec_never = np.full(total_test, DecisionAction.ALLOW)

    # Precompute expected loss components per interval:
    exp_loss_allow = p_test_bal * c_fn
    exp_loss_mitigate = (1.0 - p_test_bal) * c_fp + c_m

    # Precompute realized loss components per interval:
    # If ALLOW: y * C_FN
    # If MITIGATE: (1 - y) * C_FP + C_M
    real_loss_allow = test_y * c_fn
    real_loss_mitigate = (1.0 - test_y) * c_fp + c_m

    def evaluate_policy(name, thresh_str, dec_arr):
        is_mit = (dec_arr == DecisionAction.MITIGATE)
        n_mit = int(np.sum(is_mit))
        n_allow = total_test - n_mit
        mit_rate = (n_mit / total_test) * 100.0

        tp = int(np.sum(is_mit & (test_y == 1)))
        fp = int(np.sum(is_mit & (test_y == 0)))
        tn = int(np.sum((~is_mit) & (test_y == 0)))
        fn = int(np.sum((~is_mit) & (test_y == 1)))

        recall = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
        precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        # Losses
        exp_loss = float(np.sum(np.where(is_mit, exp_loss_mitigate, exp_loss_allow)))
        real_loss = float(np.sum(np.where(is_mit, real_loss_mitigate, real_loss_allow)))

        # Disagreement with Policy B
        disagree = int(np.sum(dec_arr != dec_econ))
        disagree_pct = (disagree / total_test) * 100.0

        return {
            "Policy": name,
            "Threshold": thresh_str,
            "Total_Intervals": total_test,
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
            "Expected_Modeled_Loss_AUD": exp_loss,
            "Realized_PostHoc_Loss_AUD": real_loss,
            "Expected_Loss_Per_Interval_AUD": exp_loss / total_test,
            "Realized_Loss_Per_Interval_AUD": real_loss / total_test,
            "Disagreement_With_Policy_B_%": disagree_pct
        }

    policy_rows = [
        evaluate_policy("Policy B: Economic Expected-Cost Rule (Baseline 5:1)", "Dynamic (p* = 0.1833)", dec_econ),
        evaluate_policy("Policy A: Fixed Threshold (tau = 0.50)", "Fixed (tau = 0.50)", dec_50),
        evaluate_policy("Policy A: Fixed Threshold (tau = 0.30)", "Fixed (tau = 0.30)", dec_30),
        evaluate_policy("Policy A: Fixed Threshold (tau = 0.70)", "Fixed (tau = 0.70)", dec_70),
        evaluate_policy("Baseline: ALWAYS_MITIGATE", "None (Mitigate 100%)", dec_always),
        evaluate_policy("Baseline: NEVER_MITIGATE", "None (Allow 100%)", dec_never),
    ]

    df_policy_audit = pd.DataFrame(policy_rows)
    df_policy_audit.to_csv("Step 5/outputs/step5_1_policy_comparison.csv", index=False)
    print("Saved: Step 5/outputs/step5_1_policy_comparison.csv")

    # =========================================================================
    # 3. DELIVERABLE: Sensitivity Analysis CSV
    # =========================================================================
    print("\nEvaluating all 5 Sensitivity Scenarios with complete expected and realized loss accounting...")
    scenarios = [
        {"id": "SC-1", "name": "Scenario 1: Baseline Asymmetric Risk (5:1)", "C_FN": 0.50, "C_FP": 0.10, "C_M": 0.01},
        {"id": "SC-2", "name": "Scenario 2: Aggressive Defense (10:1)", "C_FN": 1.00, "C_FP": 0.10, "C_M": 0.01},
        {"id": "SC-3", "name": "Scenario 3: Conservative Defense (2:1)", "C_FN": 0.20, "C_FP": 0.10, "C_M": 0.01},
        {"id": "SC-4", "name": "Scenario 4: Zero Mitigation Overhead (C_M = 0)", "C_FN": 0.50, "C_FP": 0.10, "C_M": 0.00},
        {"id": "SC-5", "name": "Scenario 5: High Operational Friction (C_M = 0.05)", "C_FN": 0.50, "C_FP": 0.10, "C_M": 0.05},
    ]

    sens_rows = []
    for sc in scenarios:
        s_fn = sc["C_FN"]
        s_fp = sc["C_FP"]
        s_m = sc["C_M"]
        p_star = (s_fp + s_m) / (s_fn + s_fp)

        # Decision
        s_res = make_economic_decision(p_test_bal, s_fn, s_fp, s_m)
        s_dec = s_res["decision"]
        is_mit = (s_dec == DecisionAction.MITIGATE)
        n_mit = int(np.sum(is_mit))
        n_allow = total_test - n_mit
        mit_rate = (n_mit / total_test) * 100.0

        tp = int(np.sum(is_mit & (test_y == 1)))
        fp = int(np.sum(is_mit & (test_y == 0)))
        tn = int(np.sum((~is_mit) & (test_y == 0)))
        fn = int(np.sum((~is_mit) & (test_y == 1)))

        recall = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
        precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        # Expected loss
        s_exp_allow = p_test_bal * s_fn
        s_exp_mit = (1.0 - p_test_bal) * s_fp + s_m
        s_exp_loss = float(np.sum(np.where(is_mit, s_exp_mit, s_exp_allow)))

        # Realized loss
        s_real_allow = test_y * s_fn
        s_real_mit = (1.0 - test_y) * s_fp + s_m
        s_real_loss = float(np.sum(np.where(is_mit, s_real_mit, s_real_allow)))

        # Disagreement with baseline Policy B
        disagree = int(np.sum(s_dec != dec_econ))
        disagree_pct = (disagree / total_test) * 100.0

        sens_rows.append({
            "Scenario_ID": sc["id"],
            "Scenario_Name": sc["name"],
            "C_FN_AUD": s_fn,
            "C_FP_AUD": s_fp,
            "C_M_AUD": s_m,
            "Cost_Ratio_FN_to_FP": s_fn / s_fp if s_fp > 0 else float("inf"),
            "Breakeven_Probability_p*": p_star,
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
            "Expected_Modeled_Loss_AUD": s_exp_loss,
            "Realized_PostHoc_Loss_AUD": s_real_loss,
            "Disagreement_With_Baseline_B_%": disagree_pct
        })

    df_sens_audit = pd.DataFrame(sens_rows)
    df_sens_audit.to_csv("Step 5/outputs/step5_1_sensitivity_analysis.csv", index=False)
    print("Saved: Step 5/outputs/step5_1_sensitivity_analysis.csv")

    # Also compute breakdown by attack phase for test set
    print("\nComputing Phase Breakdown on Test Set...")
    # phase_day: [299, 1096]
    test_phase_day = phase_day[:, TEST_START:TEST_END + 1] # [299, 671]
    # repeat for 48 slots: [299, 671, 48]
    test_phase_int = np.repeat(test_phase_day[:, :, np.newaxis], 48, axis=2).flatten()
    phases = np.unique(test_phase_int)
    phase_stats = []
    for ph in phases:
        ph_mask = (test_phase_int == ph)
        ph_y = test_y[ph_mask]
        ph_p_bal = p_test_bal[ph_mask]
        ph_p_unw = p_test_unw[ph_mask]
        phase_stats.append({
            "Phase": int(ph),
            "N_Intervals": int(np.sum(ph_mask)),
            "Attacked_Intervals": int(np.sum(ph_y)),
            "Prevalence_%": float(np.mean(ph_y) * 100.0),
            "Bal_Prob_Mean": float(np.mean(ph_p_bal)),
            "Bal_Prob_Min": float(np.min(ph_p_bal)),
            "Bal_Prob_Max": float(np.max(ph_p_bal)),
            "Unw_Prob_Mean": float(np.mean(ph_p_unw)),
            "Unw_Prob_Min": float(np.min(ph_p_unw)),
            "Unw_Prob_Max": float(np.max(ph_p_unw))
        })
    print(pd.DataFrame(phase_stats).to_string(index=False))

    print("\n>>> AUDIT DATA GENERATION COMPLETE <<<")

if __name__ == "__main__":
    main()
