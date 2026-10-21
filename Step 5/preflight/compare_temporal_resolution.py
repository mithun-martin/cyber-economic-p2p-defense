"""
Step 5 Preflight: Empirical Resolution Comparison (Option A vs. Option B)
Evaluates:
  - Option A: Daily probability p_day broadcast uniformly to all 48 half-hours of the day.
  - Option B: Interval-level reconstruction error e_{i,t} calibrated to interval probability p_{i,t}.

Both options are evaluated directly against the ground-truth interval-level attack labels
(is_attacked == 1) across all 48 intervals/day on the final out-of-time test set (Days 425-1095).

Outputs:
  - Step 5/preflight/temporal_resolution_comparison.csv
  - Step 5/preflight/interval_calibrator.pkl
"""

import json
import os
import pickle
import time
import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss, log_loss, roc_auc_score, average_precision_score,
    precision_recall_curve, f1_score, precision_score, recall_score
)

from train_detector import ConvAE_v2

SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def compare_resolutions(
    cache_path: str = "Step 5/preflight/cache_299.pt",
    ckpt_path: str = "Step 5/preflight/detector_checkpoint.pt"
):
    print(f"\n{'='*80}")
    print(">>> STEP 5: DAILY vs. HALF-HOURLY INTERFACE COMPARISON (OPTION A vs B) <<<")
    print(f"{'='*80}")

    # Load model
    print(f"[Loading] Checkpoint: {ckpt_path}")
    model = ConvAE_v2().to(DEVICE)
    model.load_state_dict(torch.load(ckpt_path, map_location=DEVICE))
    model.eval()

    # Load data
    print(f"[Loading] Cache: {cache_path}")
    cache = torch.load(cache_path, map_location="cpu")
    X = cache["X"]                         # [299, 1096, 2, 48]
    y_interval = cache["y_interval"].numpy() # [299, 1096, 48]
    n_cust, n_days, n_ch, n_steps = X.shape

    # Partitions:
    # Calibration: Days 305 to 424 (120 days)
    # Test: Days 425 to 1095 (671 days)
    CALIB_START, CALIB_END = 305, 424
    TEST_START, TEST_END = 425, 1095

    # 1. Compute per-interval reconstruction errors for Calibration and Test
    print("[Inference] Computing 48-interval reconstruction errors...")
    
    def get_errors(days_slice):
        sub_X = X[:, days_slice].reshape(-1, n_ch, n_steps)
        n = len(sub_X)
        batch_size = 64
        int_errs = []
        with torch.no_grad():
            for i in range(0, n, batch_size):
                bx = sub_X[i:i + batch_size].to(DEVICE)
                recon = model(bx)
                err = ((bx - recon) ** 2).mean(dim=1) # [B, 48]
                int_errs.append(err.cpu().numpy())
        return np.concatenate(int_errs, axis=0) # [N_days, 48]

    calib_int_errs = get_errors(slice(CALIB_START, CALIB_END + 1))  # [35,880, 48]
    test_int_errs = get_errors(slice(TEST_START, TEST_END + 1))    # [200,629, 48]

    # Ground truths at interval level
    calib_y_int = y_interval[:, CALIB_START:CALIB_END + 1].reshape(-1, 48)  # [35,880, 48]
    test_y_int = y_interval[:, TEST_START:TEST_END + 1].reshape(-1, 48)    # [200,629, 48]

    # Ground truths at daily level
    calib_y_day = calib_y_int.any(axis=1) # [35,880]
    test_y_day = test_y_int.any(axis=1)   # [200,629]

    # Flatten for interval-level evaluation
    flat_calib_y = calib_y_int.flatten() # [35,880 * 48 = 1,722,240]
    flat_test_y = test_y_int.flatten()   # [200,629 * 48 = 9,630,192]

    flat_calib_err = calib_int_errs.flatten()
    flat_test_err = test_int_errs.flatten()

    print(f"Total Test Intervals: {len(flat_test_y):,} (Attacked: {flat_test_y.sum():,}, {flat_test_y.mean()*100:.2f}%)")

    # =========================================================================
    # OPTION A: DAILY PROBABILITY BROADCAST ACROSS 48 INTERVALS
    # =========================================================================
    print("\n[Option A] Evaluating Daily Probability Broadcast...")
    # Daily score = max interval error of the day
    calib_day_scores = calib_int_errs.max(axis=1)
    test_day_scores = test_int_errs.max(axis=1)

    # Fit daily Platt calibrator
    platt_day = LogisticRegression(class_weight="balanced", random_state=SEED, max_iter=1000)
    platt_day.fit(np.log(calib_day_scores + 1e-12).reshape(-1, 1), calib_y_day)

    p_day_calib = platt_day.predict_proba(np.log(calib_day_scores + 1e-12).reshape(-1, 1))[:, 1]
    p_day_test = platt_day.predict_proba(np.log(test_day_scores + 1e-12).reshape(-1, 1))[:, 1]

    # Broadcast daily probability to all 48 intervals of that day
    opt_a_test_p = np.repeat(p_day_test, 48) # [9,630,192]

    # =========================================================================
    # OPTION B: INTERVAL-LEVEL CALIBRATION DIRECTLY
    # =========================================================================
    print("[Option B] Fitting Interval-Level Platt Calibrator directly...")
    # Subsample 200,000 calibration intervals to fit Platt efficiently
    rng = np.random.default_rng(SEED)
    idx_sample = rng.choice(len(flat_calib_y), size=min(200000, len(flat_calib_y)), replace=False)

    platt_interval = LogisticRegression(class_weight="balanced", random_state=SEED, max_iter=1000)
    feat_calib_int = np.log(flat_calib_err[idx_sample] + 1e-12).reshape(-1, 1)
    platt_interval.fit(feat_calib_int, flat_calib_y[idx_sample])

    w_int = float(platt_interval.coef_[0, 0])
    b_int = float(platt_interval.intercept_[0])
    print(f"  -> Option B Platt parameters: w = {w_int:.6f}, b = {b_int:.6f}")

    # Predict interval probabilities in chunks to manage memory
    chunk_size = 500000
    opt_b_test_p = np.zeros(len(flat_test_err), dtype=np.float32)
    for c_start in range(0, len(flat_test_err), chunk_size):
        c_end = min(c_start + chunk_size, len(flat_test_err))
        feat_chunk = np.log(flat_test_err[c_start:c_end] + 1e-12).reshape(-1, 1)
        opt_b_test_p[c_start:c_end] = platt_interval.predict_proba(feat_chunk)[:, 1]

    # Save Option B calibrator
    with open("Step 5/preflight/interval_calibrator.pkl", "wb") as f:
        pickle.dump({"model": platt_interval, "weight_w": w_int, "bias_b": b_int}, f)

    # =========================================================================
    # COMPARISON ON 9.63 MILLION TEST INTERVALS
    # =========================================================================
    print("\n[Comparison] Computing metrics on 9.63 Million Test Trading Intervals...")

    # Subsample 1M intervals for fast AUROC/metric computation
    eval_idx = rng.choice(len(flat_test_y), size=min(1000000, len(flat_test_y)), replace=False)
    sub_y = flat_test_y[eval_idx]
    sub_pa = opt_a_test_p[eval_idx]
    sub_pb = opt_b_test_p[eval_idx]

    brier_a = float(brier_score_loss(sub_y, sub_pa))
    brier_b = float(brier_score_loss(sub_y, sub_pb))

    logloss_a = float(log_loss(sub_y, np.clip(sub_pa, 1e-6, 1 - 1e-6)))
    logloss_b = float(log_loss(sub_y, np.clip(sub_pb, 1e-6, 1 - 1e-6)))

    auroc_a = float(roc_auc_score(sub_y, sub_pa))
    auroc_b = float(roc_auc_score(sub_y, sub_pb))

    auc_pr_a = float(average_precision_score(sub_y, sub_pa))
    auc_pr_b = float(average_precision_score(sub_y, sub_pb))

    # Binary decisions at threshold p >= 0.5
    pred_a = (sub_pa >= 0.5).astype(int)
    pred_b = (sub_pb >= 0.5).astype(int)

    dr_a = float(recall_score(sub_y, pred_a, zero_division=0) * 100)
    dr_b = float(recall_score(sub_y, pred_b, zero_division=0) * 100)

    pr_a = float(precision_score(sub_y, pred_a, zero_division=0) * 100)
    pr_b = float(precision_score(sub_y, pred_b, zero_division=0) * 100)

    f1_a = float(f1_score(sub_y, pred_a, zero_division=0) * 100)
    f1_b = float(f1_score(sub_y, pred_b, zero_division=0) * 100)

    comp_df = pd.DataFrame([
        {
            "Interface": "Option A: Daily Probability Broadcast (p_t = p_day)",
            "Resolution": "Daily mapped to 48 intervals",
            "Brier_Score": brier_a,
            "Log_Loss": logloss_a,
            "AUROC": auroc_a,
            "AUC_PR": auc_pr_a,
            "Recall_DR_%": dr_a,
            "Precision_%": pr_a,
            "F1_%": f1_a,
            "Market_Actionability": "Coarse (full-day penalty, over-mitigates clean hours)"
        },
        {
            "Interface": "Option B: Half-Hourly Calibrated Probability",
            "Resolution": "Direct 30-minute interval",
            "Brier_Score": brier_b,
            "Log_Loss": logloss_b,
            "AUROC": auroc_b,
            "AUC_PR": auc_pr_b,
            "Recall_DR_%": dr_b,
            "Precision_%": pr_b,
            "F1_%": f1_b,
            "Market_Actionability": "Precise (targets exact 30-min clearing periods)"
        }
    ])

    print("\n" + "=" * 100)
    print(" ⚖️ EMPIRICAL COMPARISON: OPTION A vs. OPTION B ON TEST SET INTERVALS")
    print("=" * 100)
    print(comp_df.to_string(index=False))

    comp_df.to_csv("Step 5/preflight/temporal_resolution_comparison.csv", index=False)
    print(f"\n[Saved] Resolution comparison table: Step 5/preflight/temporal_resolution_comparison.csv")
    return comp_df


if __name__ == "__main__":
    compare_resolutions()
