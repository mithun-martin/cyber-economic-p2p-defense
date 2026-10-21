"""
Step 5.2: Master Calibration Provenance, Scenario Restoration, and Deliverables Generator.

Generates:
  1. Step 5/preflight/interval_calibrator_unweighted.pkl (Serialized unweighted calibrator artifact)
  2. Step 5/outputs/step5_2_calibration_metrics.csv (Comprehensive calibration scorecard with reference baselines)
  3. Step 5/outputs/step5_2_original_five_scenarios.csv (Exact 5 original sensitivity scenarios from step5_config.yaml)
  4. Step 5/outputs/step5_2_policy_comparison.csv (Head-to-head 6+ policy baselines under identical frozen test data)
  5. Step 5/outputs/step5_2_supplementary_scenarios.csv (Step 5.1 exploratory cost variants for completeness)
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
from economic_decision import make_economic_decision, DecisionAction

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEED = 42

def compute_ece(probs, labels, n_bins=10):
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(probs)
    for i in range(n_bins):
        mask = (probs >= bins[i]) & (probs < bins[i+1]) if i < n_bins - 1 else (probs >= bins[i]) & (probs <= bins[i+1])
        nb = mask.sum()
        if nb > 0:
            ece += (nb / n) * abs(labels[mask].mean() - probs[mask].mean())
    return float(ece)

def main():
    print(f"\n{'='*80}")
    print(">>> STEP 5.2: INDEPENDENT PROVENANCE, SCENARIO & POLICY GENERATOR <<<")
    print(f"{'='*80}")

    # 1. Load Preflight Cache & Checkpoint
    cache_path = os.path.join(SCRIPT_DIR, "preflight", "cache_299.pt")
    ckpt_path = os.path.join(SCRIPT_DIR, "preflight", "detector_checkpoint.pt")
    
    print(f"[Loading] Cache: {cache_path}")
    cache = torch.load(cache_path, map_location="cpu")
    X = cache["X"] # [299, 1096, 2, 48]
    y_interval = cache["y_interval"].numpy() # [299, 1096, 48]
    n_cust, n_days, n_ch, n_slots = X.shape

    print(f"[Loading] Checkpoint: {ckpt_path}")
    model = ConvAE_v2().to(DEVICE)
    model.load_state_dict(torch.load(ckpt_path, map_location=DEVICE))
    model.eval()

    # Partitions:
    # Calibration Partition: Days 305 to 424 inclusive (Python slice(305, 425), 120 days)
    # Test Partition:        Days 425 to 1095 inclusive (Python slice(425, 1096), 671 days)
    CALIB_START, CALIB_END = 305, 424
    TEST_START, TEST_END = 425, 1095

    print(f"\n[Partitions]")
    print(f"  Calibration Partition: Days {CALIB_START} to {CALIB_END} ({CALIB_END - CALIB_START + 1} days, [305:425])")
    print(f"  Test Partition:        Days {TEST_START} to {TEST_END} ({TEST_END - TEST_START + 1} days, [425:1096])")

    # 2. Compute Reconstruction Errors
    print("\n[Inference] Computing 2-channel MSE across Calibration and Test sets...")
    def run_inference(days_slice):
        sub_X = X[:, days_slice].reshape(-1, n_ch, n_slots)
        n = len(sub_X)
        batch_size = 128
        errs = []
        with torch.no_grad():
            for i in range(0, n, batch_size):
                bx = sub_X[i:i + batch_size].to(DEVICE)
                recon = model(bx)
                err = ((bx - recon) ** 2).mean(dim=1)
                errs.append(err.cpu().numpy())
        return np.concatenate(errs, axis=0).flatten()

    calib_errs = run_inference(slice(CALIB_START, CALIB_END + 1))
    test_errs = run_inference(slice(TEST_START, TEST_END + 1))

    calib_y = y_interval[:, CALIB_START:CALIB_END + 1].flatten()
    test_y = y_interval[:, TEST_START:TEST_END + 1].flatten()

    n_calib = len(calib_y)
    n_test = len(test_y)
    prev_calib = float(calib_y.mean())
    prev_test = float(test_y.mean())

    print(f"  Calibration Intervals: {n_calib:,} | Attacked: {calib_y.sum():,} ({prev_calib*100:.3f}%)")
    print(f"  Test Intervals:        {n_test:,} | Attacked: {test_y.sum():,} ({prev_test*100:.3f}%)")

    # 3. Fit & Verify Calibrators
    # Exact provenance: compare_temporal_resolution.py used RNG seed 42 to sample 200,000 intervals from Days 305-424
    rng = np.random.default_rng(SEED)
    idx_sample = rng.choice(n_calib, size=min(200000, n_calib), replace=False)
    feat_sample = np.log(calib_errs[idx_sample] + 1e-12).reshape(-1, 1)
    y_sample = calib_y[idx_sample]

    # Model A: Balanced Platt (Existing Artifact)
    bal_pkl_path = os.path.join(SCRIPT_DIR, "preflight", "interval_calibrator.pkl")
    with open(bal_pkl_path, "rb") as f:
        calib_bal = pickle.load(f)
    w_bal = float(calib_bal["weight_w"])
    b_bal = float(calib_bal["bias_b"])
    print(f"\n[Calibrator A: Existing Balanced Platt]")
    print(f"  Loaded: w={w_bal:.6f}, b={b_bal:.6f} from {bal_pkl_path}")

    # Model B: Verified Unweighted Platt (200k Sample)
    lr_unw_200k = LogisticRegression(class_weight=None, random_state=SEED, max_iter=1000)
    lr_unw_200k.fit(feat_sample, y_sample)
    w_unw_200k = float(lr_unw_200k.coef_[0, 0])
    b_unw_200k = float(lr_unw_200k.intercept_[0])
    print(f"[Calibrator B: Verified Unweighted Platt (200k Subsample)]")
    print(f"  Fitted: w={w_unw_200k:.6f}, b={b_unw_200k:.6f}")

    # Model C: Verified Unweighted Platt (Full 1.72M)
    feat_all = np.log(calib_errs + 1e-12).reshape(-1, 1)
    lr_unw_all = LogisticRegression(class_weight=None, random_state=SEED, max_iter=1000)
    lr_unw_all.fit(feat_all, calib_y)
    w_unw_all = float(lr_unw_all.coef_[0, 0])
    b_unw_all = float(lr_unw_all.intercept_[0])
    print(f"[Calibrator C: Verified Unweighted Platt (Full 1.72M Calibration Intervals)]")
    print(f"  Fitted: w={w_unw_all:.6f}, b={b_unw_all:.6f}")

    # Serialize Verified Unweighted Calibrator Artifact (without overwriting balanced artifact)
    unw_pkl_path = os.path.join(SCRIPT_DIR, "preflight", "interval_calibrator_unweighted.pkl")
    unw_artifact = {
        "calibrator_type": "PlattScaling_Unweighted_LogisticRegression",
        "model": lr_unw_200k,
        "feature_transform": "ln(interval_mse + 1e-12)",
        "weight_w": w_unw_200k,
        "bias_b": b_unw_200k,
        "calibration_period": "Days 305 to 424 inclusive (120 days)",
        "training_subsample_size": 200000,
        "random_seed": SEED,
        "base_rate_calibration": prev_calib,
        "weight_w_full": w_unw_all,
        "bias_b_full": b_unw_all
    }
    with open(unw_pkl_path, "wb") as f:
        pickle.dump(unw_artifact, f)
    print(f"  -> Saved verified unweighted calibrator artifact: {unw_pkl_path}")

    # Compute Test Set Probabilities
    test_feat = np.log(test_errs + 1e-12)
    p_test_bal = 1.0 / (1.0 + np.exp(-(w_bal * test_feat + b_bal)))
    p_test_unw_200k = 1.0 / (1.0 + np.exp(-(w_unw_200k * test_feat + b_unw_200k)))
    p_test_unw_all = 1.0 / (1.0 + np.exp(-(w_unw_all * test_feat + b_unw_all)))

    # Baselines
    p_ref_calib = np.full(n_test, prev_calib, dtype=np.float64)
    p_ref_test = np.full(n_test, prev_test, dtype=np.float64)
    s_min, s_max = float(test_errs.min()), float(test_errs.max())
    p_raw_norm = (test_errs - s_min) / (s_max - s_min + 1e-12)

    # =========================================================================
    # DELIVERABLE 1: Step 5/outputs/step5_2_calibration_metrics.csv
    # =========================================================================
    print("\n[Exporting] Step 5/outputs/step5_2_calibration_metrics.csv...")
    calib_models = [
        ("Existing Balanced Platt Calibrator", "Days 305-424 (200k Subsample, Balanced)", 200000, b_bal, w_bal, p_test_bal),
        ("Verified Unweighted Platt Calibrator (200k)", "Days 305-424 (200k Subsample, Unweighted)", 200000, b_unw_200k, w_unw_200k, p_test_unw_200k),
        ("Verified Unweighted Platt Calibrator (Full 1.72M)", "Days 305-424 (Full 1.72M, Unweighted)", n_calib, b_unw_all, w_unw_all, p_test_unw_all),
        ("Prevalence-Only Baseline (Calibration Prior)", "Days 305-424 (Constant p = 0.02453)", n_calib, None, None, p_ref_calib),
        ("Prevalence-Only Baseline (Test Prior)", "Days 425-1095 (Constant p = 0.04199)", n_test, None, None, p_ref_test),
        ("Normalized Raw Reconstruction Error", "None (Min-Max Scaled Test MSE)", None, None, None, p_raw_norm),
    ]

    metric_rows = []
    for name, part, n_tr, b_v, w_v, p in calib_models:
        brier = float(brier_score_loss(test_y, p))
        ll = float(log_loss(test_y, np.clip(p, 1e-12, 1.0 - 1e-12)))
        ece = compute_ece(p, test_y)
        if len(np.unique(p)) > 1:
            auroc = float(roc_auc_score(test_y, p))
            auprc = float(average_precision_score(test_y, p))
        else:
            auroc = 0.500000
            auprc = prev_test
        metric_rows.append({
            "Model": name,
            "Partition_Description": part,
            "N_Train_Intervals": n_tr,
            "Param_b": b_v,
            "Param_w": w_v,
            "Prob_Min": float(p.min()),
            "Prob_Max": float(p.max()),
            "Prob_Mean": float(p.mean()),
            "Prob_Std": float(p.std()),
            "Brier_Score": brier,
            "Log_Loss": ll,
            "ECE": ece,
            "AUROC": auroc,
            "AUPRC": auprc
        })

    df_metrics = pd.DataFrame(metric_rows)
    metrics_csv_path = os.path.join(SCRIPT_DIR, "outputs", "step5_2_calibration_metrics.csv")
    df_metrics.to_csv(metrics_csv_path, index=False)
    print(f"  -> Saved: {metrics_csv_path}")

    # =========================================================================
    # DELIVERABLE 2: Step 5/outputs/step5_2_original_five_scenarios.csv
    # =========================================================================
    print("\n[Exporting] Step 5/outputs/step5_2_original_five_scenarios.csv...")
    # Exact original scenarios from step5_config.yaml
    original_scenarios = [
        {"id": "scenario_1_baseline", "name": "Scenario 1: Baseline Asymmetric Risk (5:1)", "C_FN": 0.50, "C_FP": 0.10, "C_M": 0.01},
        {"id": "scenario_2_high_penalty", "name": "Scenario 2: High Attack Consequence (10:1)", "C_FN": 1.00, "C_FP": 0.10, "C_M": 0.01},
        {"id": "scenario_3_balanced", "name": "Scenario 3: Symmetric / Balanced Risk (1:1)", "C_FN": 0.20, "C_FP": 0.20, "C_M": 0.01},
        {"id": "scenario_4_cautious_mitigation", "name": "Scenario 4: High False Alarm Penalty (1:5)", "C_FN": 0.10, "C_FP": 0.50, "C_M": 0.01},
        {"id": "scenario_5_high_overhead", "name": "Scenario 5: High Administrative Overhead", "C_FN": 0.50, "C_FP": 0.10, "C_M": 0.15},
    ]

    def evaluate_scenario_grid(p_arr, calibrator_tag):
        rows = []
        for sc in original_scenarios:
            c_fn = sc["C_FN"]
            c_fp = sc["C_FP"]
            c_m = sc["C_M"]
            p_star = (c_fp + c_m) / (c_fn + c_fp)

            # Economic rule: MITIGATE if p > p*, break tie to ALLOW
            is_mit = (p_arr > p_star)
            n_mit = int(is_mit.sum())
            n_allow = n_test - n_mit
            mit_rate = (n_mit / n_test) * 100.0

            tp = int((is_mit & (test_y == 1)).sum())
            fp = int((is_mit & (test_y == 0)).sum())
            tn = int(((~is_mit) & (test_y == 0)).sum())
            fn = int(((~is_mit) & (test_y == 1)).sum())

            rec = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
            prec = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
            f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

            exp_loss = float(np.where(is_mit, (1.0 - p_arr) * c_fp + c_m, p_arr * c_fn).sum())
            real_loss = float(fn * c_fn + fp * c_fp + n_mit * c_m)

            rows.append({
                "Calibrator_Used": calibrator_tag,
                "Scenario_ID": sc["id"],
                "Scenario_Name": sc["name"],
                "C_FN_AUD": c_fn,
                "C_FP_AUD": c_fp,
                "C_M_AUD": c_m,
                "Cost_Ratio_FN_to_FP": c_fn / c_fp,
                "Breakeven_Probability_p*": p_star,
                "Mitigation_Rate_%": mit_rate,
                "ALLOW_Count": n_allow,
                "MITIGATE_Count": n_mit,
                "True_Positives": tp,
                "False_Positives": fp,
                "True_Negatives": tn,
                "False_Negatives": fn,
                "Recall_DR_%": rec,
                "Precision_%": prec,
                "F1_Score_%": f1,
                "Expected_Modeled_Loss_AUD": exp_loss,
                "Realized_PostHoc_Loss_AUD": real_loss,
                "Expected_Loss_Per_Interval_AUD": exp_loss / n_test,
                "Realized_Loss_Per_Interval_AUD": real_loss / n_test
            })
        return rows

    orig_rows = evaluate_scenario_grid(p_test_bal, "Balanced Platt (Existing Artifact)")
    orig_rows += evaluate_scenario_grid(p_test_unw_200k, "Verified Unweighted Platt (Proposed)")

    df_orig_sc = pd.DataFrame(orig_rows)
    orig_csv_path = os.path.join(SCRIPT_DIR, "outputs", "step5_2_original_five_scenarios.csv")
    df_orig_sc.to_csv(orig_csv_path, index=False)
    print(f"  -> Saved: {orig_csv_path}")

    # =========================================================================
    # DELIVERABLE 3: Step 5/outputs/step5_2_policy_comparison.csv
    # =========================================================================
    print("\n[Exporting] Step 5/outputs/step5_2_policy_comparison.csv...")
    base_fn, base_fp, base_m = 0.50, 0.10, 0.01
    base_p_star = (base_fp + base_m) / (base_fn + base_fp) # 0.183333

    policy_candidates = [
        ("Policy B: Economic Rule (Balanced Platt Calibrator)", "Dynamic (p* = 0.1833)", p_test_bal > base_p_star, p_test_bal),
        ("Policy B: Economic Rule (Verified Unweighted Platt)", "Dynamic (p* = 0.1833)", p_test_unw_200k > base_p_star, p_test_unw_200k),
        ("Policy A: Fixed Threshold (tau = 0.50, Balanced)", "Fixed (tau = 0.50)", p_test_bal >= 0.50, p_test_bal),
        ("Policy A: Fixed Threshold (tau = 0.30, Balanced)", "Fixed (tau = 0.30)", p_test_bal >= 0.30, p_test_bal),
        ("Policy A: Fixed Threshold (tau = 0.70, Balanced)", "Fixed (tau = 0.70)", p_test_bal >= 0.70, p_test_bal),
        ("Baseline: ALWAYS_MITIGATE", "None (Mitigate 100%)", np.ones(n_test, dtype=bool), p_test_bal),
        ("Baseline: NEVER_MITIGATE", "None (Allow 100%)", np.zeros(n_test, dtype=bool), p_test_bal),
    ]

    pol_rows = []
    # Reference decisions: Policy B Balanced
    ref_dec = p_test_bal > base_p_star

    for pname, tname, is_mit, p_eval in policy_candidates:
        n_mit = int(is_mit.sum())
        n_allow = n_test - n_mit
        mit_rate = (n_mit / n_test) * 100.0

        tp = int((is_mit & (test_y == 1)).sum())
        fp = int((is_mit & (test_y == 0)).sum())
        tn = int(((~is_mit) & (test_y == 0)).sum())
        fn = int(((~is_mit) & (test_y == 1)).sum())

        rec = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
        prec = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        exp_loss = float(np.where(is_mit, (1.0 - p_eval) * base_fp + base_m, p_eval * base_fn).sum())
        real_loss = float(fn * base_fn + fp * base_fp + n_mit * base_m)

        disagree = int((is_mit != ref_dec).sum())
        disagree_pct = (disagree / n_test) * 100.0

        pol_rows.append({
            "Policy": pname,
            "Threshold": tname,
            "Total_Intervals": n_test,
            "Mitigation_Rate_%": mit_rate,
            "ALLOW_Count": n_allow,
            "MITIGATE_Count": n_mit,
            "True_Positives": tp,
            "False_Positives": fp,
            "True_Negatives": tn,
            "False_Negatives": fn,
            "Recall_DR_%": rec,
            "Precision_%": prec,
            "F1_Score_%": f1,
            "Expected_Modeled_Loss_AUD": exp_loss,
            "Realized_PostHoc_Loss_AUD": real_loss,
            "Expected_Loss_Per_Interval_AUD": exp_loss / n_test,
            "Realized_Loss_Per_Interval_AUD": real_loss / n_test,
            "Disagreement_With_Policy_B_Balanced_%": disagree_pct
        })

    df_pol = pd.DataFrame(pol_rows)
    pol_csv_path = os.path.join(SCRIPT_DIR, "outputs", "step5_2_policy_comparison.csv")
    df_pol.to_csv(pol_csv_path, index=False)
    print(f"  -> Saved: {pol_csv_path}")

    # =========================================================================
    # DELIVERABLE 4: Step 5/outputs/step5_2_supplementary_scenarios.csv
    # =========================================================================
    print("\n[Exporting] Step 5/outputs/step5_2_supplementary_scenarios.csv...")
    supp_scenarios = [
        {"id": "supp_1_baseline", "name": "Supplementary 1: Baseline 5:1", "C_FN": 0.50, "C_FP": 0.10, "C_M": 0.01},
        {"id": "supp_2_aggressive_10to1", "name": "Supplementary 2: Aggressive 10:1", "C_FN": 1.00, "C_FP": 0.10, "C_M": 0.01},
        {"id": "supp_3_conservative_2to1", "name": "Supplementary 3: Conservative 2:1", "C_FN": 0.20, "C_FP": 0.10, "C_M": 0.01},
        {"id": "supp_4_zero_overhead", "name": "Supplementary 4: Zero Overhead (C_M = 0)", "C_FN": 0.50, "C_FP": 0.10, "C_M": 0.00},
        {"id": "supp_5_friction_005", "name": "Supplementary 5: Moderate Overhead (C_M = 0.05)", "C_FN": 0.50, "C_FP": 0.10, "C_M": 0.05},
    ]

    supp_rows = []
    for sc in supp_scenarios:
        c_fn = sc["C_FN"]
        c_fp = sc["C_FP"]
        c_m = sc["C_M"]
        p_star = (c_fp + c_m) / (c_fn + c_fp)

        is_mit = (p_test_bal > p_star)
        n_mit = int(is_mit.sum())
        n_allow = n_test - n_mit
        mit_rate = (n_mit / n_test) * 100.0

        tp = int((is_mit & (test_y == 1)).sum())
        fp = int((is_mit & (test_y == 0)).sum())
        tn = int(((~is_mit) & (test_y == 0)).sum())
        fn = int(((~is_mit) & (test_y == 1)).sum())

        rec = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
        prec = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        exp_loss = float(np.where(is_mit, (1.0 - p_test_bal) * c_fp + c_m, p_test_bal * c_fn).sum())
        real_loss = float(fn * c_fn + fp * c_fp + n_mit * c_m)

        supp_rows.append({
            "Scenario_ID": sc["id"],
            "Scenario_Name": sc["name"],
            "C_FN_AUD": c_fn,
            "C_FP_AUD": c_fp,
            "C_M_AUD": c_m,
            "Breakeven_Probability_p*": p_star,
            "Mitigation_Rate_%": mit_rate,
            "ALLOW_Count": n_allow,
            "MITIGATE_Count": n_mit,
            "True_Positives": tp,
            "False_Positives": fp,
            "True_Negatives": tn,
            "False_Negatives": fn,
            "Recall_DR_%": rec,
            "Precision_%": prec,
            "F1_Score_%": f1,
            "Expected_Modeled_Loss_AUD": exp_loss,
            "Realized_PostHoc_Loss_AUD": real_loss
        })

    df_supp = pd.DataFrame(supp_rows)
    supp_csv_path = os.path.join(SCRIPT_DIR, "outputs", "step5_2_supplementary_scenarios.csv")
    df_supp.to_csv(supp_csv_path, index=False)
    print(f"  -> Saved: {supp_csv_path}")

    print("\n>>> STEP 5.2 DATA GENERATION COMPLETE <<<")

if __name__ == "__main__":
    main()
