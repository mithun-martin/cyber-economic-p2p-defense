"""
Step 5 Preflight: Probability Calibration Module
Fits Platt Scaling (Logistic Regression) and Isotonic Regression on a dedicated,
temporally-separated calibration set containing both normal and attacked days.
Evaluates calibration metrics (Brier score, Log Loss, AUROC, ECE, reliability curves)
on both calibration and out-of-time final test set (Days 425-1095).

Outputs:
  - Step 5/preflight/probability_calibrator.pkl
  - Step 5/preflight/calibration_config.json
  - Step 5/preflight/calibration_report.csv
"""

import json
import os
import pickle
import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score, average_precision_score

from train_detector import ConvAE_v2, count_parameters

# Set seeds
SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def compute_reconstruction_scores(model, X, batch_size=64):
    """
    Computes daily reconstruction errors for all windows in X: [N, 2, 48].
    Returns:
      - max_scores: [N] max interval error of the day
      - mean_scores: [N] mean error of the day
      - interval_errors: [N, 48] 2-channel MSE per interval
    """
    model.eval()
    n = X.shape[0]
    max_scores = []
    mean_scores = []
    interval_errs = []

    with torch.no_grad():
        for i in range(0, n, batch_size):
            bx = X[i:i + batch_size].to(DEVICE)
            recon = model(bx)
            # MSE per interval across 2 channels: [B, 48]
            diff2 = (bx - recon) ** 2
            int_mse = diff2.mean(dim=1)  # average over 2 channels
            
            int_np = int_mse.cpu().numpy()
            interval_errs.append(int_np)
            max_scores.append(int_np.max(axis=1))
            mean_scores.append(int_np.mean(axis=1))

    return (np.concatenate(max_scores, axis=0),
            np.concatenate(mean_scores, axis=0),
            np.concatenate(interval_errs, axis=0))


def compute_ece(y_true, y_prob, n_bins=10):
    """Computes Expected Calibration Error (ECE) across n_bins equal-width bins."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    ece = 0.0
    bin_data = []
    for b in range(n_bins):
        mask = (bin_indices == b)
        count = mask.sum()
        if count > 0:
            avg_prob = y_prob[mask].mean()
            emp_acc = y_true[mask].mean()
            abs_diff = abs(emp_acc - avg_prob)
            ece += (count / len(y_true)) * abs_diff
            bin_data.append({
                "bin": b, "bin_min": float(bins[b]), "bin_max": float(bins[b+1]),
                "count": int(count), "mean_predicted_prob": float(avg_prob),
                "empirical_positive_rate": float(emp_acc), "abs_calibration_gap": float(abs_diff)
            })
        else:
            bin_data.append({
                "bin": b, "bin_min": float(bins[b]), "bin_max": float(bins[b+1]),
                "count": 0, "mean_predicted_prob": float((bins[b] + bins[b+1])/2),
                "empirical_positive_rate": 0.0, "abs_calibration_gap": 0.0
            })
    return float(ece), bin_data


def run_calibration(
    cache_path: str = "Step 5/preflight/cache_299.pt",
    ckpt_path: str = "Step 5/preflight/detector_checkpoint.pt"
):
    print(f"\n{'='*75}")
    print(">>> STEP 5: PROBABILITY CALIBRATION PROTOCOL <<<")
    print(f"{'='*75}")

    # 1. Load trained detector checkpoint
    print(f"[Calibration] Loading model checkpoint: {ckpt_path}")
    model = ConvAE_v2().to(DEVICE)
    model.load_state_dict(torch.load(ckpt_path, map_location=DEVICE))
    model.eval()

    # 2. Load dataset cache
    print(f"[Calibration] Loading dataset cache: {cache_path}")
    cache = torch.load(cache_path, map_location="cpu")
    X = cache["X"]                     # [299, 1096, 2, 48]
    y_day = cache["y_day"].numpy()       # [299, 1096]
    phase_day = cache["phase_day"].numpy()
    n_cust, n_days, n_ch, n_steps = X.shape

    # 3. Define Temporal Partitions
    # Autoencoder training: Days 0-304
    # Calibration set: Days 305-424 (60 days clean validation + 60 days early Phase 2 Scaling)
    # Test set: Days 425-1095 (671 out-of-time days: late Phase 2, Phase 3 Ramp, Phase 4A Replay, Phase 4B Coordinated)
    CALIB_START = 305
    CALIB_END = 424   # 120 days total: Days 305 to 424 inclusive
    TEST_START = 425
    TEST_END = 1095   # 671 days total: Days 425 to 1095 inclusive

    print(f"[Partitioning] Calibration Partition: Days {CALIB_START} to {CALIB_END} ({CALIB_END - CALIB_START + 1} days)")
    print(f"[Partitioning] Final Test Partition:  Days {TEST_START} to {TEST_END} ({TEST_END - TEST_START + 1} days)")

    # 4. Extract Calibration and Test Tensors
    calib_X = X[:, CALIB_START:CALIB_END + 1].reshape(-1, n_ch, n_steps)
    calib_y = y_day[:, CALIB_START:CALIB_END + 1].flatten()
    calib_phase = phase_day[:, CALIB_START:CALIB_END + 1].flatten()

    test_X = X[:, TEST_START:TEST_END + 1].reshape(-1, n_ch, n_steps)
    test_y = y_day[:, TEST_START:TEST_END + 1].flatten()
    test_phase = phase_day[:, TEST_START:TEST_END + 1].flatten()

    n_calib_total = len(calib_y)
    n_calib_pos = int(calib_y.sum())
    n_calib_neg = n_calib_total - n_calib_pos

    n_test_total = len(test_y)
    n_test_pos = int(test_y.sum())
    n_test_neg = n_test_total - n_test_pos

    print(f"\n[Data Distribution]")
    print(f"Calibration Set: {n_calib_total:,} customer-days | Normal: {n_calib_neg:,} ({n_calib_neg/n_calib_total*100:.1f}%), Attacked: {n_calib_pos:,} ({n_calib_pos/n_calib_total*100:.1f}%)")
    print(f"Final Test Set:  {n_test_total:,} customer-days | Normal: {n_test_neg:,} ({n_test_neg/n_test_total*100:.1f}%), Attacked: {n_test_pos:,} ({n_test_pos/n_test_total*100:.1f}%)")

    # 5. Compute Reconstruction Errors
    print("\n[Inference] Computing model reconstruction errors on Calibration Set...")
    calib_max_scores, calib_mean_scores, _ = compute_reconstruction_scores(model, calib_X)

    print("[Inference] Computing model reconstruction errors on Final Test Set...")
    test_max_scores, test_mean_scores, _ = compute_reconstruction_scores(model, test_X)

    # 6. Fit Platt Calibrator (Logistic Regression) on Calibration Set
    # Feature: log(max_reconstruction_error + 1e-12) to handle positive-skewed errors gracefully
    # Logistic model: logit(p) = w * log(error) + b
    print("\n[Fitting] Training Platt Scaler (Logistic Regression with balanced class weights)...")
    X_calib_feat = np.log(calib_max_scores + 1e-12).reshape(-1, 1)
    X_test_feat = np.log(test_max_scores + 1e-12).reshape(-1, 1)

    platt_calibrator = LogisticRegression(class_weight="balanced", random_state=SEED, max_iter=1000)
    platt_calibrator.fit(X_calib_feat, calib_y)

    w = float(platt_calibrator.coef_[0, 0])
    b = float(platt_calibrator.intercept_[0])
    print(f"  -> Fitted Platt parameters: Weight w = {w:.6f}, Bias b = {b:.6f}")
    print(f"  -> Logit formula: logit(p_attack) = {w:.6f} * ln(error) + {b:.6f}")

    # Predict calibrated probabilities
    calib_p_platt = platt_calibrator.predict_proba(X_calib_feat)[:, 1]
    test_p_platt = platt_calibrator.predict_proba(X_test_feat)[:, 1]

    # Also fit Isotonic Regression as alternative
    print("[Fitting] Training Isotonic Regression Calibrator...")
    iso_calibrator = IsotonicRegression(out_of_bounds="clip")
    iso_calibrator.fit(calib_max_scores, calib_y)
    calib_p_iso = iso_calibrator.predict(calib_max_scores)
    test_p_iso = iso_calibrator.predict(test_max_scores)

    # 7. Evaluate Calibration Metrics
    # Uncalibrated baseline normalized to [0, 1] by min-max on calib scores
    s_min, s_max = calib_max_scores.min(), calib_max_scores.max()
    uncalib_calib = np.clip((calib_max_scores - s_min) / (s_max - s_min + 1e-9), 0.0, 1.0)
    uncalib_test = np.clip((test_max_scores - s_min) / (s_max - s_min + 1e-9), 0.0, 1.0)

    # Compute ECE
    ece_calib_uncalib, _ = compute_ece(calib_y, uncalib_calib)
    ece_test_uncalib, _ = compute_ece(test_y, uncalib_test)

    ece_calib_platt, bins_calib_platt = compute_ece(calib_y, calib_p_platt)
    ece_test_platt, bins_test_platt = compute_ece(test_y, test_p_platt)

    ece_calib_iso, _ = compute_ece(calib_y, calib_p_iso)
    ece_test_iso, _ = compute_ece(test_y, test_p_iso)

    # Summary Metrics Table
    results = [
        {
            "Split": "Calibration Set (Days 305-424)",
            "Method": "Uncalibrated Error (Normalized)",
            "Brier_Score": float(brier_score_loss(calib_y, uncalib_calib)),
            "Log_Loss": float(log_loss(calib_y, np.clip(uncalib_calib, 1e-6, 1 - 1e-6))),
            "ECE": ece_calib_uncalib,
            "AUROC": float(roc_auc_score(calib_y, calib_max_scores)),
            "AUC_PR": float(average_precision_score(calib_y, calib_max_scores))
        },
        {
            "Split": "Calibration Set (Days 305-424)",
            "Method": "Platt Scaling (Logistic Regression)",
            "Brier_Score": float(brier_score_loss(calib_y, calib_p_platt)),
            "Log_Loss": float(log_loss(calib_y, np.clip(calib_p_platt, 1e-6, 1 - 1e-6))),
            "ECE": ece_calib_platt,
            "AUROC": float(roc_auc_score(calib_y, calib_p_platt)),
            "AUC_PR": float(average_precision_score(calib_y, calib_p_platt))
        },
        {
            "Split": "Calibration Set (Days 305-424)",
            "Method": "Isotonic Regression",
            "Brier_Score": float(brier_score_loss(calib_y, calib_p_iso)),
            "Log_Loss": float(log_loss(calib_y, np.clip(calib_p_iso, 1e-6, 1 - 1e-6))),
            "ECE": ece_calib_iso,
            "AUROC": float(roc_auc_score(calib_y, calib_p_iso)),
            "AUC_PR": float(average_precision_score(calib_y, calib_p_iso))
        },
        {
            "Split": "Final Test Set (Days 425-1095, Out-of-Time)",
            "Method": "Uncalibrated Error (Normalized)",
            "Brier_Score": float(brier_score_loss(test_y, uncalib_test)),
            "Log_Loss": float(log_loss(test_y, np.clip(uncalib_test, 1e-6, 1 - 1e-6))),
            "ECE": ece_test_uncalib,
            "AUROC": float(roc_auc_score(test_y, test_max_scores)),
            "AUC_PR": float(average_precision_score(test_y, test_max_scores))
        },
        {
            "Split": "Final Test Set (Days 425-1095, Out-of-Time)",
            "Method": "Platt Scaling (Logistic Regression)",
            "Brier_Score": float(brier_score_loss(test_y, test_p_platt)),
            "Log_Loss": float(log_loss(test_y, np.clip(test_p_platt, 1e-6, 1 - 1e-6))),
            "ECE": ece_test_platt,
            "AUROC": float(roc_auc_score(test_y, test_p_platt)),
            "AUC_PR": float(average_precision_score(test_y, test_p_platt))
        },
        {
            "Split": "Final Test Set (Days 425-1095, Out-of-Time)",
            "Method": "Isotonic Regression",
            "Brier_Score": float(brier_score_loss(test_y, test_p_iso)),
            "Log_Loss": float(log_loss(test_y, np.clip(test_p_iso, 1e-6, 1 - 1e-6))),
            "ECE": ece_test_iso,
            "AUROC": float(roc_auc_score(test_y, test_p_iso)),
            "AUC_PR": float(average_precision_score(test_y, test_p_iso))
        }
    ]
    df_results = pd.DataFrame(results)

    print("\n" + "=" * 90)
    print(" 📊 PROBABILITY CALIBRATION PERFORMANCE SCORECARD")
    print("=" * 90)
    print(df_results.to_string(index=False))

    # Phase-by-phase breakdown on Final Test Set under Platt Calibrator
    phase_labels = {1: "Phase 2 (Late Scaling)", 2: "Phase 3 (Ramp)", 3: "Phase 4A (Replay)", 4: "Phase 4B (Coordinated)"}
    phase_metrics = []
    for code, pname in phase_labels.items():
        mask = (test_phase == code)
        if mask.any():
            py = test_y[mask]
            pp = test_p_platt[mask]
            ps = test_max_scores[mask]
            if len(np.unique(py)) > 1:
                p_brier = float(brier_score_loss(py, pp))
                p_loss = float(log_loss(py, np.clip(pp, 1e-6, 1 - 1e-6)))
                p_auc = float(roc_auc_score(py, pp))
                p_ece, _ = compute_ece(py, pp)
            else:
                p_brier, p_loss, p_auc, p_ece = float("nan"), float("nan"), float("nan"), float("nan")
            phase_metrics.append({
                "Phase": pname, "Days": int(mask.sum() / n_cust), "Total_Windows": int(mask.sum()),
                "Attack_Prevalence_%": float(py.mean() * 100),
                "Mean_Predicted_Prob": float(pp.mean()),
                "Brier_Score": p_brier, "Log_Loss": p_loss, "AUROC": p_auc, "ECE": p_ece
            })
    df_phase = pd.DataFrame(phase_metrics)
    print("\n" + "=" * 90)
    print(" 🔍 PHASE-BY-PHASE TEST SET DRIFT ANALYSIS (Platt Scaler)")
    print("=" * 90)
    print(df_phase.to_string(index=False))

    # 8. Save Artifacts
    # Save Calibrator object
    calibrator_artifact = {
        "calibrator_type": "PlattScaling_LogisticRegression",
        "model": platt_calibrator,
        "feature_transform": "log_e_plus_1e-12",
        "weight_w": w,
        "bias_b": b,
        "input_feature": "max_daily_reconstruction_error",
        "calibration_period": f"Days {CALIB_START} to {CALIB_END}",
        "isotonic_alternative": iso_calibrator
    }
    calib_pkl_path = "Step 5/preflight/probability_calibrator.pkl"
    with open(calib_pkl_path, "wb") as f:
        pickle.dump(calibrator_artifact, f)
    print(f"\n[Saved] Calibrator artifact: {calib_pkl_path}")

    # Save Config JSON
    config_artifact = {
        "calibrator_type": "PlattScaling",
        "model_architecture": "ConvAE_v2",
        "parameter_count": 23258,
        "feature_order": ["Channel 0: GC_attacked (kWh)", "Channel 1: GG_attacked (kWh)"],
        "input_tensor_shape": [1, 2, 48],
        "normalization": "MinMax per-customer fitted on Phase 1 (Days 0-364)",
        "reconstruction_error_formula": "max_{t in 1..48} (0.5 * [(GC - GC_hat)^2 + (GG - GG_hat)^2])",
        "feature_transformation": "ln(error + 1e-12)",
        "platt_coefficients": {
            "weight_w": w,
            "bias_b": b,
            "sigmoid_formula": "1.0 / (1.0 + exp(-(w * ln(error + 1e-12) + b)))"
        },
        "temporal_partitions": {
            "autoencoder_training": "Days 0 to 304 (305 clean baseline days)",
            "clean_validation": "Days 305 to 364 (60 clean baseline days)",
            "calibration_set": f"Days {CALIB_START} to {CALIB_END} (120 days: 60 clean + 60 early scaling attacks)",
            "final_test_set": f"Days {TEST_START} to {TEST_END} (671 out-of-time days: late scaling, ramp, replay, coordinated)"
        },
        "performance_metrics": {
            "calib_brier_score": float(df_results.loc[1, "Brier_Score"]),
            "calib_log_loss": float(df_results.loc[1, "Log_Loss"]),
            "calib_ece": float(df_results.loc[1, "ECE"]),
            "calib_auroc": float(df_results.loc[1, "AUROC"]),
            "test_brier_score": float(df_results.loc[4, "Brier_Score"]),
            "test_log_loss": float(df_results.loc[4, "Log_Loss"]),
            "test_ece": float(df_results.loc[4, "ECE"]),
            "test_auroc": float(df_results.loc[4, "AUROC"])
        },
        "reliability_bins_test": bins_test_platt
    }
    config_json_path = "Step 5/preflight/calibration_config.json"
    with open(config_json_path, "w") as f:
        json.dump(config_artifact, f, indent=2)
    print(f"[Saved] Calibration configuration: {config_json_path}")

    # Save CSV Report
    df_results.to_csv("Step 5/preflight/calibration_report.csv", index=False)
    print(f"[Saved] Calibration scorecard: Step 5/preflight/calibration_report.csv")


if __name__ == "__main__":
    run_calibration()
