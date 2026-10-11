# Imagine you have a 3-year video of a house's electricity meter. PyTorch cannot watch a 3-year video all at once.

# dataset.py does 3 simple jobs:

# Pulls 1 Customer: Out of 15.7 million rows, it grabs only 1 single Customer data at one time.
# Squashes the numbers (Min-Max): Raw numbers like # 14.2 kWh get squashed between  0.0 and  1.0
# The Slicer (24-Hour Windows): It takes the continuous stream and chops it into 365 separate daily flashcards (each card is 48 half-hour numbers). It packages them into batches of 16 so PyTorch can train on them.

# That's it! It is just the conveyor belt feeding clean daily windows into the AI.


#It takes one customer at a time!
#it take all intervals in a day ie 48
#it take all days available for the first year (Phase 1 Normal) Total intervals in Year 1:  365×48=17,520 intervals 365×48=17,520 intervals.

import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

# =====================================================================
# PYTORCH DATASET: 24-HOUR SLIDING WINDOWS (48 INTERVALS)
# =====================================================================
class SmartMeterDataset(Dataset):
    """
    Slices a prosumer's time-series into 24-hour temporal windows (48 half-hour points).
    Shape per window: [Channels, 48] where Channels = [GC, GG] (Consumption & Generation)
    """
    def __init__(self, df: pd.DataFrame, window_size: int = 48, stride: int = 48, scaler=None):
        self.window_size = window_size
        self.stride = stride
        
        # Telemetry features for the Autoencoder: [GC_attacked, GG_attacked]
        telemetry = df[["GC_attacked", "GG_attacked"]].values.astype(np.float32)
        
        # Ground-truth labels for evaluation (HIDDEN from the model during training)
        labels = df["is_attacked"].values.astype(np.int64)
        
        # Normalization (Min-Max Scaling based on Phase 1 normal bounds)
        if scaler is None:
            # Fit scaler on this data (should be Phase 1 clean baseline)
            self.min_val = telemetry.min(axis=0)
            self.max_val = telemetry.max(axis=0) + 1e-6  # avoid division by zero
        else:
            self.min_val, self.max_val = scaler

        normalized_telemetry = (telemetry - self.min_val) / (self.max_val - self.min_val)

        # Slice into windows
        self.windows = []
        self.window_labels = []

        num_points = len(df)
        for start in range(0, num_points - window_size + 1, stride):
            end = start + window_size
            
            # Extract window: shape [48, 2] -> transpose to [2, 48] for PyTorch Conv1D
            w = normalized_telemetry[start:end].T
            self.windows.append(w)
            
            # A window is considered attacked if AT LEAST ONE interval in the 24h was attacked
            w_label = 1 if labels[start:end].sum() > 0 else 0
            self.window_labels.append(w_label)

        # Convert to PyTorch tensors
        self.windows = torch.tensor(np.array(self.windows), dtype=torch.float32)
        self.window_labels = torch.tensor(np.array(self.window_labels), dtype=torch.long)

    def get_scaler(self):
        """Returns the normalization bounds so test sets can use the identical scaler."""
        return (self.min_val, self.max_val)

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx):
        return self.windows[idx], self.window_labels[idx]


# =====================================================================
# DATA LOADER BUILDER FOR SPECIFIC PHASES
# =====================================================================
def load_customer_data(parquet_path: str, customer_id: int = 1):
    """
    Loads one customer's 3-year data from the frozen Parquet benchmark.
    Only loads the required columns so it takes ~1 second.
    """
    columns = [
        "customer_id", "time_index", "date", 
        "GC_attacked", "GG_attacked", 
        "is_attacked", "attack_phase", "attack_type"
    ]
    print(f"Loading data for Customer {customer_id} from {parquet_path}...")
    df = pd.read_parquet(
        parquet_path, 
        columns=columns, 
        filters=[("customer_id", "==", customer_id)]
    )
    return df


# =====================================================================
# VERIFICATION TEST (Runs when you execute this file directly)
# =====================================================================
if __name__ == "__main__":
    PARQUET_FILE = "Step 1/DATA/ausgrid_solar_attacked.parquet"

    # 1. Load Customer 1's records
    df_c1 = load_customer_data(PARQUET_FILE, customer_id=1)
    print(f"Loaded {len(df_c1):,} total observations for Customer 1.")

    # 2. Filter Phase 1 (Year 1 Clean Training Baseline: Days 0 to 364)
    df_phase_1 = df_c1[df_c1["attack_phase"] == "1_NORMAL"].copy()
    print(f"Phase 1 (Clean baseline) observations: {len(df_phase_1):,} intervals.")

    # 3. Create Dataset with 24-hour windows (48 intervals)
    train_dataset = SmartMeterDataset(df_phase_1, window_size=48, stride=48)
    print(f"Generated {len(train_dataset)} clean 24-hour windows for training.")

    # 4. Wrap in a PyTorch DataLoader
    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    sample_batch, sample_labels = next(iter(train_loader))

    print(f"\n--- TENSOR SHAPE VERIFICATION ---")
    print(f"Sample Batch Shape:   {sample_batch.shape}  -> [Batch: 16, Channels: 2, Intervals: 48]")
    print(f"Sample Labels Shape:  {sample_labels.shape}  -> [Batch: 16]")
    print(f"Min value: {sample_batch.min():.4f}, Max value: {sample_batch.max():.4f} (Properly normalized [0, 1])")

    assert sample_batch.shape == (16, 2, 48), "Error: Shape mismatch!"
    print("\n✅ Checkpoint Passed! The data pipeline works and produces the exact PyTorch tensor shape.")