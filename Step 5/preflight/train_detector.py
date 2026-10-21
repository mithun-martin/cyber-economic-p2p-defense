"""
Step 5 Preflight: Reproducible Detector Training and Recovery
Trains the primary defense model ConvAE_v2 (23,258 parameters) using Federated Averaging (FedAvg)
across all 299 prosumers on Phase 1 clean baseline (Days 0-304), evaluated on validation (Days 305-364).

Outputs:
  - Step 5/preflight/detector_checkpoint.pt
  - Step 5/preflight/training_history.csv
  - Step 5/preflight/normalization_bounds.json
"""

import copy
import json
import os
import sys
import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

# Set seeds
SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[Training] Using device: {DEVICE} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

# Model Architecture: ConvAE_v2
class ConvAE_v2(nn.Module):
    """
    1-D Convolutional Autoencoder with 24-dimensional bottleneck (23,258 parameters).
    Input: [B, 2, 48] (Channel 0: GC_attacked, Channel 1: GG_attacked)
    Output: [B, 2, 48] (Reconstructed telemetry)
    """
    def __init__(self, in_channels: int = 2, latent_dim: int = 24):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv1d(in_channels, 16, kernel_size=4, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 32, kernel_size=4, stride=2, padding=1),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(32 * 12, latent_dim)
        )
        self.decoder_fc = nn.Sequential(
            nn.Linear(latent_dim, 32 * 12),
            nn.ReLU()
        )
        self.decoder = nn.Sequential(
            nn.ConvTranspose1d(32, 16, kernel_size=4, stride=2, padding=1),
            nn.ReLU(),
            nn.ConvTranspose1d(16, in_channels, kernel_size=4, stride=2, padding=1)
        )

    def forward(self, x):
        z = self.encoder(x)
        h = self.decoder_fc(z).view(-1, 32, 12)
        return self.decoder(h)


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def train_fedavg(cache_path: str, rounds: int = 30, lr: float = 1e-3, batch_size: int = 16):
    print(f"[Training] Loading cache: {cache_path}")
    cache = torch.load(cache_path, map_location="cpu")
    X = cache["X"]           # [299, 1096, 2, 48]
    ids = cache["ids"].numpy()
    mins = cache["mins"].numpy()
    maxs = cache["maxs"].numpy()
    n_cust = X.shape[0]

    # Save normalization bounds as standalone JSON
    bounds_dict = {}
    for i, cid in enumerate(ids):
        bounds_dict[int(cid)] = {
            "min_GC": float(mins[i, 0]),
            "max_GC": float(maxs[i, 0]),
            "min_GG": float(mins[i, 1]),
            "max_GG": float(maxs[i, 1])
        }
    bounds_json_path = "Step 5/preflight/normalization_bounds.json"
    with open(bounds_json_path, "w") as f:
        json.dump(bounds_dict, f, indent=2)
    print(f"[Training] Saved standalone normalization bounds for {n_cust} customers to {bounds_json_path}")

    # Training and validation slices
    TRAIN_DAYS = 305  # Days 0 to 304
    VAL_DAYS = 60     # Days 305 to 364
    
    # Global model initialization
    global_model = ConvAE_v2().to(DEVICE)
    param_count = count_parameters(global_model)
    print(f"[Training] Initialized ConvAE_v2 with {param_count:,} parameters (Seed {SEED})")

    criterion = nn.MSELoss()
    history = []
    t0 = time.time()

    print(f"\n{'='*70}")
    print(f" FEDERATED TRAINING (FedAvg) OVER {n_cust} CLIENTS | {rounds} ROUNDS")
    print(f"{'='*70}")

    for rnd in range(1, rounds + 1):
        r_start = time.time()
        client_state_dicts = []

        # Local training on each client
        for c in range(n_cust):
            local_model = copy.deepcopy(global_model)
            local_model.train()
            optimizer = torch.optim.Adam(local_model.parameters(), lr=lr)

            # Client's clean Phase 1 training data: [305, 2, 48]
            xc_train = X[c, :TRAIN_DAYS].to(DEVICE)
            ds = TensorDataset(xc_train)
            loader = DataLoader(ds, batch_size=batch_size, shuffle=True)

            for (bx,) in loader:
                optimizer.zero_grad()
                recon = local_model(bx)
                loss = criterion(recon, bx)
                loss.backward()
                optimizer.step()

            client_state_dicts.append(local_model.state_dict())

        # FedAvg Aggregation: Average weights across all 299 clients
        global_dict = copy.deepcopy(client_state_dicts[0])
        for key in global_dict.keys():
            global_dict[key] = torch.stack([client_state_dicts[i][key] for i in range(n_cust)], dim=0).mean(dim=0)
        global_model.load_state_dict(global_dict)

        # Evaluate global model on clean validation partition (Days 305-364) across all clients
        global_model.eval()
        with torch.no_grad():
            val_losses = []
            for c in range(n_cust):
                xc_val = X[c, TRAIN_DAYS:TRAIN_DAYS + VAL_DAYS].to(DEVICE)
                recon_val = global_model(xc_val)
                v_loss = criterion(recon_val, xc_val).item()
                val_losses.append(v_loss)
            mean_val_mse = float(np.mean(val_losses))

        r_time = time.time() - r_start
        history.append({"round": rnd, "val_mse": mean_val_mse, "round_time_sec": r_time})
        print(f"Round [{rnd:>2}/{rounds}]  Global Validation MSE: {mean_val_mse:.6f}  ({r_time:.1f}s, elapsed: {(time.time()-t0)/60:.1f}m)")

    # Save final model checkpoint
    ckpt_path = "Step 5/preflight/detector_checkpoint.pt"
    torch.save(global_model.state_dict(), ckpt_path)
    print(f"\n[Training] Saved recovered detector checkpoint: {ckpt_path}")

    # Save history CSV
    df_hist = pd.DataFrame(history)
    df_hist.to_csv("Step 5/preflight/training_history.csv", index=False)
    print(f"[Training] Saved training history: Step 5/preflight/training_history.csv")
    print(f"[Training] Total training time: {(time.time()-t0)/60:.2f} minutes")

    return global_model


if __name__ == "__main__":
    cache_file = "Step 5/preflight/cache_299.pt"
    train_fedavg(cache_file, rounds=30, lr=1e-3, batch_size=16)
