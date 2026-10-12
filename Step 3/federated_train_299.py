
# 3. federated_train_299.py: makes the Federated model
# This repeats 30 times (30 "rounds"):
# Every house gets the current shared model.
# Every house trains it a little on its own data.
# Every house sends back only the model's numbers (weights), never the raw meter data.
# The server averages those numbers into a new shared model.
# It saves 1 global model.

#FEDERATED LEARNING (FedAvg) OVER ALL 299 CLIENTS
# =====================================================================
# Analogy: 299 students study their OWN notebook at home, then send ONLY
# their "brain update" (model weights) to a teacher. The teacher averages
# all brains into one smarter brain and sends it back. Repeat.
# Raw meter readings NEVER leave a house — only model weights.
#
# One round:  broadcast w -> each client trains locally -> upload (w_k, n_k)
#             -> server FedAvg: w = sum_k (n_k / N) * w_k -> clients report val MSE
#
# Flower note: the client class exposes Flower's NumPyClient interface
# (get_parameters / fit / evaluate) and the server uses Flower's FedAvg
# formula. It runs in one process because Flower's simulation engine needs
# Ray, which is unreliable on Windows + Python 3.13. Same algorithm.
#
# Usage:  python "Step 3\federated_train_299.py" --model conv2 --protocol A
# Output: checkpoints/federated_<model>_<protocol>.pt
#         outputs/federated_history_<model>_<protocol>.csv
#         outputs/federated_meta_<model>_<protocol>.json
# =====================================================================

import argparse
import time

import pandas as pd
import torch

from common import (load_cache, build_model, get_weights, set_weights, train_model, mean_mse,
                    make_splits, ckpt_path, save_json, count_params, OUT_DIR,
                    FED_ROUNDS, FED_LOCAL_EPOCHS, SEED, MODELS, PROTOCOLS)
import os


class SmartMeterClient:
    """One household. Its data never leaves this object."""
    def __init__(self, cid, X_customer, split, model_name):
        self.cid = cid
        self.X_train = X_customer[split["train"]]
        self.X_val = X_customer[split["val"]]
        self.model = build_model(model_name)

    def get_parameters(self):
        return get_weights(self.model)

    def fit(self, global_weights, local_epochs, seed):
        set_weights(self.model, global_weights)
        train_model(self.model, self.X_train, epochs=local_epochs, seed=seed)
        return self.get_parameters(), len(self.X_train)

    def evaluate(self, global_weights):
        set_weights(self.model, global_weights)
        return mean_mse(self.model, self.X_val), len(self.X_val)


def fedavg(results):
    """Weighted average of client weights (weights = number of local samples)."""
    total = sum(n for _, n in results)
    return [sum(w[i] * (n / total) for w, n in results) for i in range(len(results[0][0]))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="conv2", choices=MODELS)
    ap.add_argument("--protocol", default="A", choices=PROTOCOLS)
    ap.add_argument("--rounds", type=int, default=FED_ROUNDS)
    ap.add_argument("--local-epochs", type=int, default=FED_LOCAL_EPOCHS)
    args = ap.parse_args()

    cache = load_cache()
    X, ids = cache["X"], cache["ids"]
    splits = make_splits(cache, args.protocol)
    clients = [SmartMeterClient(int(ids[k]), X[k], splits[k], args.model) for k in range(len(ids))]

    global_weights = get_weights(build_model(args.model))   # same start as Local / Centralized
    n_params = sum(w.numel() for w in global_weights)
    print(f"\n=== FEDAVG | model={args.model} ({n_params:,} params) | protocol={args.protocol} | "
          f"{len(clients)} clients | {args.rounds} rounds x {args.local_epochs} local epoch ===", flush=True)

    history = []
    t0 = time.time()
    for rnd in range(1, args.rounds + 1):
        tr = time.time()
        results = [c.fit(global_weights, args.local_epochs, seed=SEED + rnd * 1000 + k)
                   for k, c in enumerate(clients)]
        global_weights = fedavg(results)
        evals = [c.evaluate(global_weights) for c in clients]
        val = sum(l * n for l, n in evals) / sum(n for _, n in evals)
        history.append({"round": rnd, "val_mse": val})
        print(f"  round {rnd:>3}/{args.rounds}  global val MSE={val:.6f}  "
              f"({time.time() - tr:.1f}s, total {(time.time() - t0) / 60:.1f}m)", flush=True)

    final = build_model(args.model)
    set_weights(final, global_weights)
    out = ckpt_path("Federated", args.model, args.protocol)
    torch.save(final.state_dict(), out)

    tag = f"{args.model}_{args.protocol}"
    pd.DataFrame(history).to_csv(os.path.join(OUT_DIR, f"federated_history_{tag}.csv"), index=False)
    traffic_mb = n_params * 4 * 2 * len(clients) * args.rounds / 1e6
    save_json({"model": args.model, "protocol": args.protocol, "params": n_params,
               "clients": len(clients), "rounds": args.rounds, "local_epochs": args.local_epochs,
               "traffic_MB_total": traffic_mb, "traffic_KB_per_client_per_round": n_params * 4 * 2 / 1e3,
               "final_val_mse": history[-1]["val_mse"], "minutes": (time.time() - t0) / 60,
               "raw_bytes_shared": 0}, f"federated_meta_{tag}.json")
    print(f"Saved {out} | traffic {traffic_mb:.1f} MB total, raw data shared: 0 bytes | "
          f"{(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
