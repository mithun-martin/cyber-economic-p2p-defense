# 4. centralized_train.py: makes the Centralized model
# It puts the data from all 299 houses into one big pile and trains 1 model on it.
# It saves 1 model.


# =====================================================================
# CENTRALIZED AUTOENCODER (privacy-violating upper bound)
# =====================================================================
# Analogy: all 299 students hand their notebooks to ONE person who reads
# everything. Usually the most accurate — but zero privacy.
#
# Pools the training days of ALL customers (for the chosen protocol) and
# trains ONE model for 15 epochs (same model, lr, batch size, epochs as Local).
# Each customer's data keeps its own Phase-1 scaler, so the ONLY difference
# vs. Federated is "raw data shared" vs "weights shared".
#
# Usage:  python "Step 3\centralized_train.py" --model conv2 --protocol A
# Output: checkpoints/centralized_<model>_<protocol>.pt
#         outputs/centralized_meta_<model>_<protocol>.json
# =====================================================================

import argparse
import time

import torch

from common import (load_cache, build_model, train_model, mean_mse, make_splits, ckpt_path,
                    save_json, count_params, LOCAL_EPOCHS, SEED, MODELS, PROTOCOLS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="conv2", choices=MODELS)
    ap.add_argument("--protocol", default="A", choices=PROTOCOLS)
    args = ap.parse_args()

    cache = load_cache()
    X = cache["X"]
    splits = make_splits(cache, args.protocol)
    X_pool = torch.cat([X[k][splits[k]["train"]] for k in range(len(splits))]).contiguous()

    model = build_model(args.model)
    print(f"\n=== CENTRALIZED | model={args.model} ({count_params(model):,} params) | "
          f"protocol={args.protocol} | {len(X_pool):,} pooled windows ===", flush=True)

    t0 = time.time()
    train_model(model, X_pool, epochs=LOCAL_EPOCHS, seed=SEED, verbose=True)

    # Same monitoring number the federated server reports (weighted val MSE)
    vals = [(mean_mse(model, X[k][splits[k]["val"]]), len(splits[k]["val"])) for k in range(len(splits))]
    val = sum(v * n for v, n in vals) / sum(n for _, n in vals)

    out = ckpt_path("Centralized", args.model, args.protocol)
    torch.save(model.state_dict(), out)
    save_json({"model": args.model, "protocol": args.protocol, "pooled_windows": len(X_pool),
               "final_val_mse": val, "minutes": (time.time() - t0) / 60},
              f"centralized_meta_{args.model}_{args.protocol}.json")
    print(f"Saved {out} | val MSE={val:.6f} | {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
