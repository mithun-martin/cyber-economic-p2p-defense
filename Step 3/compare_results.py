# 5. compare_results.py: the results
# Tests all 3 kinds of model on every house's attack days.
# Prints the final table:

# =====================================================================
# FINAL COMPARISON: LOCAL (299) vs FEDERATED vs CENTRALIZED
# =====================================================================
# Every trained configuration found in checkpoints/ is evaluated with the
# SAME per-customer rule (threshold = 95th pct of benign validation scores).
#
# Grid: protocol {A, B} x model {conv1, conv2, fcae} x method {Local, Fed, Cen}
#       x score {mean, max}   (missing checkpoints are skipped with a warning)
#
# Experiment 1: Federated vs Local      (does collaboration help?)
# Experiment 2: Federated vs Centralized (what does privacy cost?)
#
# Outputs (outputs/):
#   step3_per_customer_metrics.csv   one row per customer per configuration
#   step3_summary.csv                mean/std across customers + pooled metrics
#   step3_stats.csv                  paired Wilcoxon tests (per customer)
#   step3_phase_detection.csv        detection rate per attack phase
#   step3_eval_store.pkl             pooled scores for the figure script
#
# Run:  python "Step 3\compare_results.py"
# =====================================================================

import os
import pickle
import warnings

import numpy as np
import pandas as pd
import torch
from scipy.stats import wilcoxon
from sklearn.metrics import roc_auc_score, average_precision_score

from common import (load_cache, build_model, evaluate_customer, detection_metrics, make_splits,
                    ckpt_path, OUT_DIR, METHODS, MODELS, PROTOCOLS, SCORES, METRIC_KEYS,
                    PRIMARY_MODEL, PRIMARY_SCORE, MODEL_LABELS, PROTOCOL_LABELS, ATTACK_PHASE_LABELS)

warnings.filterwarnings("ignore", category=RuntimeWarning)


def available(model, protocol):
    return all(os.path.exists(ckpt_path(m, model, protocol)) for m in METHODS)


def load_global(method, model, protocol):
    net = build_model(model)
    net.load_state_dict(torch.load(ckpt_path(method, model, protocol)))
    return net


def pct(x):
    return "  n/a " if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:6.2f}"


def main():
    cache = load_cache()
    X, ids = cache["X"], cache["ids"]
    y, phase = cache["y"].numpy(), cache["phase"].numpy()

    rows, summary, stats, phase_rows = [], [], [], []
    store = {}

    for protocol in PROTOCOLS:
        splits = make_splits(cache, protocol)
        for model in MODELS:
            if not available(model, protocol):
                print(f"[skip] {model} / Protocol {protocol}: checkpoints not found")
                continue
            print(f"[eval] {MODEL_LABELS[model]} | Protocol {protocol}", flush=True)
            local_states = torch.load(ckpt_path("Local", model, protocol))
            nets = {"Federated": load_global("Federated", model, protocol),
                    "Centralized": load_global("Centralized", model, protocol)}
            local_net = build_model(model)
            pooled = {(m, s): {"norm_score": [], "y": [], "phase": [], "pred": []}
                      for m in METHODS for s in SCORES}

            for k in range(len(ids)):
                cid = int(ids[k])
                local_net.load_state_dict(local_states[cid])
                for method in METHODS:
                    net = local_net if method == "Local" else nets[method]
                    res = evaluate_customer(net, X[k], y[k], phase[k], splits[k])
                    for s in SCORES:
                        r = res[s]
                        rows.append({"protocol": protocol, "model": model, "method": method, "score": s,
                                     "customer_id": cid, **r["metrics"]})
                        for key in ("norm_score", "y", "phase", "pred"):
                            pooled[(method, s)][key].append(r[key])

            # ---- pooled metrics (all customers' decisions together, B1 style)
            for (method, s), p in pooled.items():
                arr = {key: np.concatenate(v) for key, v in p.items()}
                store[(protocol, model, method, s)] = arr
                pm = detection_metrics(arr["y"], arr["pred"], arr["norm_score"])
                d = pd.DataFrame([r for r in rows if r["protocol"] == protocol and r["model"] == model
                                  and r["method"] == method and r["score"] == s])
                row = {"protocol": protocol, "model": model, "method": method, "score": s}
                for mk in METRIC_KEYS:
                    row[f"{mk}_mean"] = np.nanmean(d[mk])
                    row[f"{mk}_std"] = np.nanstd(d[mk])
                    row[f"{mk}_pooled"] = pm[mk]
                for c in ("TP", "FP", "TN", "FN"):
                    row[c] = pm[c]
                summary.append(row)

                # detection rate per attack phase
                prow = {"protocol": protocol, "model": model, "method": method, "score": s}
                for code, name in ATTACK_PHASE_LABELS.items():
                    mask = (arr["phase"] == code) & (arr["y"] == 1)
                    prow[name] = arr["pred"][mask].mean() if mask.any() else np.nan
                phase_rows.append(prow)

    df = pd.DataFrame(rows)
    summ = pd.DataFrame(summary)
    df.to_csv(os.path.join(OUT_DIR, "step3_per_customer_metrics.csv"), index=False)
    summ.to_csv(os.path.join(OUT_DIR, "step3_summary.csv"), index=False)
    pd.DataFrame(phase_rows).to_csv(os.path.join(OUT_DIR, "step3_phase_detection.csv"), index=False)
    with open(os.path.join(OUT_DIR, "step3_eval_store.pkl"), "wb") as f:
        pickle.dump(store, f)

    # ---- paired statistics (same customer, two methods)
    for (protocol, model, s), g in df.groupby(["protocol", "model", "score"]):
        for metric in ("F1", "AUC_ROC"):
            piv = g.pivot(index="customer_id", columns="method", values=metric).dropna()
            for a, b, exp in [("Federated", "Local", "Exp1"), ("Federated", "Centralized", "Exp2")]:
                diff = piv[a] - piv[b]
                try:
                    pval = float(wilcoxon(piv[a], piv[b]).pvalue)
                except Exception:
                    pval = float("nan")
                stats.append({"protocol": protocol, "model": model, "score": s, "metric": metric,
                              "experiment": exp, "comparison": f"{a} vs {b}",
                              "mean_diff": diff.mean(), "median_diff": diff.median(),
                              "a_better": int((diff > 0).sum()), "b_better": int((diff < 0).sum()),
                              "n": len(diff), "wilcoxon_p": pval})
    st = pd.DataFrame(stats)
    st.to_csv(os.path.join(OUT_DIR, "step3_stats.csv"), index=False)

    # =================================================================
    # PRINTED REPORT
    # =================================================================
    cols = ["ACC", "PR", "DR", "FA", "HD", "F1", "AUC_ROC", "AUC_PR"]
    for protocol in PROTOCOLS:
        sub = summ[(summ["protocol"] == protocol) & (summ["score"] == PRIMARY_SCORE)]
        if sub.empty:
            continue
        print(f"\n{'=' * 100}\n{PROTOCOL_LABELS[protocol]} | score={PRIMARY_SCORE} | "
              f"mean over customers (%)\n{'=' * 100}")
        print(f"{'Model':<8}{'Method':<13}" + "".join(f"{c:>9}" for c in cols) + f"{'F1 std':>9}{'pooledF1':>10}")
        for _, r in sub.iterrows():
            print(f"{r['model']:<8}{r['method']:<13}" + "".join(f"{pct(r[c + '_mean']):>9}" for c in cols)
                  + f"{pct(r['F1_std']):>9}{pct(r['F1_pooled']):>10}")

    # B1-style pooled table (B1 pools all consumers into one test set)
    sub = summ[(summ["protocol"] == "B") & (summ["score"] == PRIMARY_SCORE)]
    if not sub.empty:
        print(f"\n{'=' * 100}\nPROTOCOL B, POOLED over all customers (same layout as B1 Table 3) (%)\n{'=' * 100}")
        b1cols = ["ACC", "PR", "DR", "FA", "HD", "FNR", "F1", "AUC_ROC", "AUC_PR"]
        print(f"{'Model':<8}{'Method':<13}" + "".join(f"{c:>9}" for c in b1cols))
        for _, r in sub.iterrows():
            print(f"{r['model']:<8}{r['method']:<13}" + "".join(f"{pct(r[c + '_pooled']):>9}" for c in b1cols))

    print(f"\n{'=' * 100}\nPAIRED TESTS (per customer) | score={PRIMARY_SCORE}\n{'=' * 100}")
    for _, r in st[st["score"] == PRIMARY_SCORE].iterrows():
        print(f"  P{r['protocol']} {r['model']:<6} {r['experiment']} {r['comparison']:<26} {r['metric']:<8} "
              f"mean diff={r['mean_diff'] * 100:+6.2f} pts | {r['comparison'].split()[0]} better on "
              f"{r['a_better']}/{r['n']} | p={r['wilcoxon_p']:.2e}")

    ph = pd.DataFrame(phase_rows)
    ph = ph[ph["score"] == PRIMARY_SCORE]
    if not ph.empty:
        print(f"\n{'=' * 100}\nDETECTION RATE PER ATTACK PHASE (pooled, %) | score={PRIMARY_SCORE}\n{'=' * 100}")
        names = list(ATTACK_PHASE_LABELS.values())
        print(f"{'Prot':<6}{'Model':<8}{'Method':<13}" + "".join(f"{n:>13}" for n in names))
        for _, r in ph.iterrows():
            print(f"{r['protocol']:<6}{r['model']:<8}{r['method']:<13}" + "".join(f"{pct(r[n]):>13}" for n in names))

    # Score ablation (mean vs max) for the primary model
    print(f"\n{'=' * 100}\nSCORE ABLATION (mean F1 / AUC-ROC over customers, %) | model={PRIMARY_MODEL}\n{'=' * 100}")
    for _, r in summ[summ["model"] == PRIMARY_MODEL].iterrows():
        print(f"  P{r['protocol']} {r['method']:<13} score={r['score']:<5} F1={pct(r['F1_mean'])}  "
              f"AUC-ROC={pct(r['AUC_ROC_mean'])}")

    print(f"\nSaved CSVs + eval store to {OUT_DIR}")


if __name__ == "__main__":
    main()
