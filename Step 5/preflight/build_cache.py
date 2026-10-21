import os
import time
import numpy as np
import pandas as pd
import torch

PARQUET_PATH = "data/processed/ausgrid_solar_attacked.parquet"
OUT_CACHE = "Step 5/preflight/cache_299.pt"

print(f"Reading {PARQUET_PATH}...")
t0 = time.time()
cols = ["customer_id", "time_index", "GC_attacked", "GG_attacked", "is_attacked", "attack_phase"]
df = pd.read_parquet(PARQUET_PATH, columns=cols)
print(f"Read parquet in {time.time() - t0:.2f}s, rows: {len(df):,}")

ids = df["customer_id"].unique()
n_cust = len(ids)
N_DAYS = 1096
INTERVALS_PER_DAY = 48
PHASE1_DAYS = 365

tele = np.nan_to_num(df[["GC_attacked", "GG_attacked"]].to_numpy(np.float32))
tele = tele.reshape(n_cust, N_DAYS, INTERVALS_PER_DAY, 2)

att = df["is_attacked"].to_numpy().astype(bool).reshape(n_cust, N_DAYS, INTERVALS_PER_DAY)
y_day = att.any(axis=2)

PHASES = ["1_NORMAL", "2_SCALING", "3_RAMP", "4A_REPLAY", "4B_COORDINATED"]
codes = pd.Categorical(df["attack_phase"].astype(str), categories=PHASES).codes
phase_day = codes.reshape(n_cust, N_DAYS, INTERVALS_PER_DAY)[:, :, 0].astype(np.int8)

p1 = tele[:, :PHASE1_DAYS]
mins, maxs = p1.min(axis=(1, 2)), p1.max(axis=(1, 2))
scaled = (tele - mins[:, None, None, :]) / (maxs - mins + 1e-6)[:, None, None, :]
X = torch.from_numpy(np.ascontiguousarray(scaled.transpose(0, 1, 3, 2))).float()

cache = {
    "ids": torch.tensor(ids.astype(np.int64)),
    "X": X,
    "y_day": torch.from_numpy(y_day.astype(np.uint8)),
    "y_interval": torch.from_numpy(att.astype(np.uint8)),
    "phase_day": torch.from_numpy(phase_day),
    "mins": torch.from_numpy(mins),
    "maxs": torch.from_numpy(maxs),
    "tele_raw": torch.from_numpy(tele)
}
torch.save(cache, OUT_CACHE)
print(f"Built and saved cache to {OUT_CACHE} in {time.time() - t0:.2f}s, X shape: {X.shape}")
