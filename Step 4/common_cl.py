# This file provides the shared architecture, data loaders (reusing Step 3/outputs/cache_299.pt), metrics, 
# and the ReplayBuffer class where you fill in the buffer logic.

# =====================================================================
# STEP 4: CONTINUAL FEDERATED LEARNING — COMMON UTILITIES
# =====================================================================
# Based on patterns established in ai_knowledge_base.md (Section 3).
# Reuses Step 3 cache for zero-latency loading across all 299 prosumers.
# =====================================================================

import os
import random
import sys
import time
from collections import deque
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score, average_precision_score

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------
# 1. PATHS & CACHE RE-USE
# ---------------------------------------------------------------------
STEP4_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(STEP4_DIR)
STEP3_OUT = os.path.join(ROOT_DIR, "Step 3", "outputs")
STEP3_CKPT = os.path.join(ROOT_DIR, "Step 3", "checkpoints")
CACHE_PATH = os.path.join(STEP3_OUT, "cache_299.pt")

CKPT_DIR = os.path.join(STEP4_DIR, "checkpoints")
OUT_DIR = os.path.join(STEP4_DIR, "outputs")
FIG_DIR = os.path.join(OUT_DIR, "figures")
for _d in (CKPT_DIR, OUT_DIR, FIG_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------
# 2. HYPERPARAMETERS
# ---------------------------------------------------------------------
INTERVALS_PER_DAY = 48
N_DAYS = 1096
PHASE1_DAYS = 365
VAL_DAYS = 60
TRAIN_DAYS = PHASE1_DAYS - VAL_DAYS

LR = 5e-4
BATCH_SIZE = 16
SEED = 42
BUFFER_CAPACITY = 50   # Max daily windows per prosumer memory buffer
REPLAY_BATCH_SIZE = 8  # Mini-batch size sampled from episodic memory

PHASES = ["1_NORMAL", "2_SCALING", "3_RAMP", "4A_REPLAY", "4B_COORDINATED"]
METRIC_KEYS = ["ACC", "PR", "DR", "FA", "HD", "FNR", "F1", "SPEC", "BACC", "AUC_ROC", "AUC_PR"]


# ---------------------------------------------------------------------
# 3. EPISODIC MEMORY BUFFER (From ai_knowledge_base.md Section 3)
# ---------------------------------------------------------------------
class ReplayBuffer:
    """
    Episodic Memory Buffer for Continual Learning.
    Each of the 299 prosumers maintains a local buffer to prevent
    catastrophic forgetting of Phase 1 clean baseline behavior.
    """
    def __init__(self, capacity: int = BUFFER_CAPACITY):
        # Uses collections.deque with maxlen to automatically evict old items
        self.buffer = deque(maxlen=capacity)

    def add(self, window: torch.Tensor):
        self.buffer.append(window.detach().cpu())


#1. What is window here?
# In smart-meter anomaly detection, window is one full day (24 hours) of smart-meter readings for a prosumer.

# Tensor Shape: [2, 48]
# Dimension 2 (Channels):
# Channel 0: General Consumption (# GC — electricity pulled from the grid).
# Channel 1: General Generation (GG — solar power generated on the roof).
# Dimension 48 (Time steps):
# 48 half-hour intervals in a 24-hour day (24 hours×2=48)
# Intuition: A window represents the "daily fingerprint" of a household's energy behavior. '
# Storing a window in memory means saving a clean day's diurnal curve to remember what authentic normal behavior looks like




    def sample(self, batch_size: int = REPLAY_BATCH_SIZE) -> torch.Tensor:
        """
        Sample a random batch of historical windows from memory.
        BASICALLY DEFINING THE OLD SAMPLE WE NEED TO KEEP IN MEMORY
        """
        k = min(len(self.buffer),batch_size)
        samples = random.sample(self.buffer,k)
        return torch.stack(samples)

    # 1. Determine a safe sample size 'k':
        #    If buffer has fewer items than 'batch_size' (e.g., only 3 days stored),
        #    'min' prevents Python from crashing by only asking for what is available.
     # 2. Randomly pick 'k' past daily windows from the buffer:
        #    'samples' is a Python list containing 'k' individual tensors, each shape [2, 48].
     # 3. Combine the list of individual [2, 48] tensors into one unified batch:
        #    'torch.stack' creates a single PyTorch tensor of shape [k, 2, 48],
        #    which can be directly fed into the neural network: model(replayed_batch).
    



    def __len__(self):
        return len(self.buffer)


# ---------------------------------------------------------------------
# 4. MODEL ARCHITECTURE (Proposed Conv-AE v2 with 24-d bottleneck)
# ---------------------------------------------------------------------
class ConvAE_v2(nn.Module):
    """
    Identical to Step 3 model: 1-D CNN with a 24-dimensional bottleneck.
    Input: [B, 2, 48] -> Conv1D -> Bottleneck [B, 24] -> Deconv1D -> [B, 2, 48]
    """
    def __init__(self, in_channels: int = 2, latent_dim: int = 24):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv1d(in_channels, 16, kernel_size=4, stride=2, padding=1), nn.ReLU(),
            nn.Conv1d(16, 32, kernel_size=4, stride=2, padding=1), nn.ReLU(),
            nn.Flatten(), nn.Linear(32 * 12, latent_dim))
        self.decoder_fc = nn.Sequential(nn.Linear(latent_dim, 32 * 12), nn.ReLU())
        self.decoder = nn.Sequential(
            nn.ConvTranspose1d(32, 16, kernel_size=4, stride=2, padding=1), nn.ReLU(),
            nn.ConvTranspose1d(16, in_channels, kernel_size=4, stride=2, padding=1))

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(self.decoder_fc(z).view(-1, 32, 12))


def build_model():
    torch.manual_seed(SEED)
    return ConvAE_v2()


def load_cache():
    if not os.path.exists(CACHE_PATH):
        raise FileNotFoundError(f"Step 3 cache not found at {CACHE_PATH}. Run Step 3 first.")
    print(f"[Step 4] Loading pre-processed cache: {CACHE_PATH}")
    return torch.load(CACHE_PATH)


# ---------------------------------------------------------------------
# 5. METRICS COMPUTATION (IEEE Benchmark Standards)
# ---------------------------------------------------------------------
def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray) -> Dict[str, float]:
    y_true = np.asarray(y_true, dtype=bool)
    y_pred = np.asarray(y_pred, dtype=bool)
    y_score = np.asarray(y_score, dtype=np.float64)

    tp = int((y_true & y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    tn = int((~y_true & ~y_pred).sum())

    p = tp + fn
    n = tn + fp
    dr = tp / p if p > 0 else 0.0
    pr = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    fa = fp / n if n > 0 else 0.0
    acc = (tp + tn) / (p + n) if (p + n) > 0 else 0.0
    f1 = 2 * pr * dr / (pr + dr) if (pr + dr) > 0 else 0.0
    spec = tn / n if n > 0 else 0.0
    bacc = 0.5 * (dr + spec)

    try:
        auc_roc = float(roc_auc_score(y_true, y_score)) if len(np.unique(y_true)) > 1 else 0.5
    except Exception:
        auc_roc = 0.5

    try:
        auc_pr = float(average_precision_score(y_true, y_score)) if len(np.unique(y_true)) > 1 else 0.0
    except Exception:
        auc_pr = 0.0

    return {
        "ACC": acc * 100.0, "PR": pr * 100.0, "DR": dr * 100.0, "FA": fa * 100.0,
        "HD": (1.0 - acc) * 100.0, "FNR": (1.0 - dr) * 100.0, "F1": f1 * 100.0,
        "SPEC": spec * 100.0, "BACC": bacc * 100.0, "AUC_ROC": auc_roc * 100.0, "AUC_PR": auc_pr * 100.0
    }