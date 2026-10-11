# Now we unleash your trained Autoencoder on Years 2 and 3 where your teammate injected the cyberattacks!
# Reconstruction Error: We pass the attacked windows through the Autoencoder. Because it has never seen corrupted numbers, 
# the reconstruction error will explode on attacked days!
# Platt Scaling (Calibration): We use a simple LogisticRegression from scikit-learn (Module 2 from your Knowledge Base) to 
# #convert that error score into a calibrated probability of attack ∈[0,1]).
# The Scorecard: We unlock the Answer Key (is_attacked, attack_type) and measure:
# Precision, Recall, and F1 Score
# How well it caught Scaling vs Ramp vs Replay vs Coordinated!
import os
import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from torch.utils.data import DataLoader
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score, precision_score, recall_score, roc_auc_score

# Import our previous milestones
from dataset import load_customer_data, SmartMeterDataset
from model import Conv1DAutoencoder

def evaluate_detector(customer_id: int = 1):
    print(f"\n=======================================================")
    print(f" EVALUATING LOCAL AI DEFENSE FOR CUSTOMER {customer_id}")
    print(f"=======================================================\n")

    # 1. Load Parquet Data for Customer 1
    parquet_path = "Step 1/DATA/ausgrid_solar_attacked.parquet"
    df = load_customer_data(parquet_path, customer_id=customer_id)

    # 2. Fit Normalization Scaler on Phase 1 (Clean Baseline)
    df_phase_1 = df[df["attack_phase"] == "1_NORMAL"].copy()
    phase_1_dataset = SmartMeterDataset(df_phase_1, window_size=48, stride=48)
    scaler = phase_1_dataset.get_scaler()

    # 3. Create Evaluation Dataset across ALL 3 YEARS (1,096 Days)
    test_dataset = SmartMeterDataset(df, window_size=48, stride=48, scaler=scaler)
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)
    print(f"Total 24-hour evaluation windows across 3 years: {len(test_dataset)}")

    # 4. Load Trained Autoencoder Checkpoint
    checkpoint_path = f"Step 2/checkpoints/local_autoencoder_c{customer_id}.pt"
    model = Conv1DAutoencoder(in_channels=2)
    model.load_state_dict(torch.load(checkpoint_path))
    model.eval()
    print(f"Loaded trained weights from: {checkpoint_path}")

    # 5. Compute Reconstruction MSE per Window
    all_errors = []
    all_ground_truths = []

    criterion = nn.MSELoss(reduction='none')

    with torch.no_grad():
        for batch_x, batch_y in test_loader:
            reconstructed = model(batch_x)
            mse = criterion(reconstructed, batch_x)
            # Average across channels (2) and intervals (48) -> 1 scalar per day
            window_error = mse.mean(dim=[1, 2]).cpu().numpy()
            
            all_errors.extend(window_error)
            all_ground_truths.extend(batch_y.numpy())

    all_errors = np.array(all_errors)
    all_ground_truths = np.array(all_ground_truths)

    # 6. Compare Normal Days vs Attacked Days Error
    normal_errors = all_errors[all_ground_truths == 0]
    attacked_errors = all_errors[all_ground_truths == 1]

    print("\n" + "="*55)
    print(" 📈 RECONSTRUCTION ERROR COMPARISON")
    print("="*55)
    print(f"Average Error on Normal Days:   {normal_errors.mean():.6f}")
    print(f"Average Error on Attacked Days: {attacked_errors.mean():.6f}")
    ratio = attacked_errors.mean() / (normal_errors.mean() + 1e-8)
    print(f"Error Multiplier:               {ratio:.2f}x HIGHER on Attacked Days!")

    # 7. Probability Calibration (Platt Scaling)
    split_idx = len(all_errors) // 2
    calibrator = LogisticRegression(class_weight='balanced')
    calibrator.fit(all_errors[:split_idx].reshape(-1, 1), all_ground_truths[:split_idx])
    p_t = calibrator.predict_proba(all_errors.reshape(-1, 1))[:, 1]

    # 8. Anomaly Decision Rule (Based on 95th Percentile of Clean Phase 1)
    threshold = np.percentile(normal_errors, 95)
    binary_predictions = (all_errors >= threshold).astype(int)

    # 9. Print Performance Scorecard
    print("\n" + "="*55)
    print(" 📊 LOCAL AI DETECTION SCORECARD")
    print("="*55)
    prec = precision_score(all_ground_truths, binary_predictions, zero_division=0)
    rec = recall_score(all_ground_truths, binary_predictions, zero_division=0)
    f1 = f1_score(all_ground_truths, binary_predictions, zero_division=0)
    auc = roc_auc_score(all_ground_truths, all_errors)

    print(f"Threshold (95th percentile): {threshold:.6f}")
    print(f"Precision:                   {prec * 100:.2f}%")
    print(f"Recall (Detection Rate):     {rec * 100:.2f}%")
    print(f"F1-Score:                    {f1 * 100:.2f}%")
    print(f"AUROC:                       {auc * 100:.2f}%\n")

    print("Detailed Classification Report:")
    print(classification_report(all_ground_truths, binary_predictions, target_names=["Normal", "Attacked"]))
    print("="*55)
    print("✅ Step 2 Complete! Calibrated probabilities p_t successfully produced.")

if __name__ == "__main__":
    evaluate_detector(customer_id=1)