# 2.Local Baseline
# makes the Local models
# It loops over all 299 houses and trains one model per house on that house's own data only.
# It saves the 299 models.


# Train (days 0–304). The model only sees clean year-1 days and learns what a normal day looks like for that house.
# Set alarm (days 305–364). These are the last 60 clean days of year 1, which the model did not train on. We measure how much error it makes on normal days and set the alarm line at the 95th percentile. Anything above that line gets flagged as an attack.
# Test (days 365–1095). This is years 2–3, about 2 years of days. It has both normal days and attacked days (Scaling, Ramp, Replay, Coordinated). We check whether the model raises the alarm on attacked days and stays quiet on normal days. Precision, recall, F1 and AUROC all come from this part.

# =====================================================================
# LOCAL BASELINE: 299 INDEPENDENT LOCAL MODELS
# =====================================================================
# Analogy: 299 students each study ONLY their own notebook, alone.
# Every customer trains its own AE (same initial weights, 15 epochs) on its
# own training days of the chosen protocol. Nobody shares anything.
#
# Usage:
#   python "Step 3\local_baseline_299.py" --model conv2 --protocol A
#   --model    conv1 | conv2 | fcae      --protocol  A | B
# Output: checkpoints/local_<model>_<protocol>.pt  (all 299 state_dicts)
# =====================================================================

import argparse
import time

import numpy as np
import torch

from common import (load_cache, build_model, train_model, evaluate_customer, make_splits,
                    ckpt_path, count_params, LOCAL_EPOCHS, SEED, PRIMARY_SCORE, MODELS, PROTOCOLS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="conv2", choices=MODELS)
    ap.add_argument("--protocol", default="A", choices=PROTOCOLS)
    args = ap.parse_args()

    cache = load_cache()
    X, ids = cache["X"], cache["ids"]
    y, phase = cache["y"].numpy(), cache["phase"].numpy()
    splits = make_splits(cache, args.protocol)
    n_cust = len(ids)

    print(f"\n=== LOCAL | model={args.model} ({count_params(build_model(args.model)):,} params) | "
          f"protocol={args.protocol} | {n_cust} customers x {LOCAL_EPOCHS} epochs ===", flush=True)

    states, f1s = {}, []
    t0 = time.time()
    for k in range(n_cust):
        cid = int(ids[k])
        sp = splits[k]
        model = build_model(args.model)
        loss = train_model(model, X[k][sp["train"]], epochs=LOCAL_EPOCHS, seed=SEED)
        states[cid] = {n: t.clone() for n, t in model.state_dict().items()}
        f1s.append(evaluate_customer(model, X[k], y[k], phase[k], sp)[PRIMARY_SCORE]["metrics"]["F1"])

        if (k + 1) % 25 == 0 or k == n_cust - 1:
            el = time.time() - t0
            print(f"  [{k + 1:>3}/{n_cust}] cust {cid:>3} loss={loss:.5f} "
                  f"running mean F1={np.nanmean(f1s) * 100:.2f}%  elapsed={el / 60:.1f}m  "
                  f"ETA={el / (k + 1) * (n_cust - k - 1) / 60:.1f}m", flush=True)

    out = ckpt_path("Local", args.model, args.protocol)
    torch.save(states, out)
    print(f"Saved {out}  ({(time.time() - t0) / 60:.1f} min)")


if __name__ == "__main__":
    main()
