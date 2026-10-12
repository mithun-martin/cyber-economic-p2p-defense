# =====================================================================
# STEP 3 — IEEE FIGURE GENERATOR
# =====================================================================
# Produces all paper figures (PNG 300 dpi + vector PDF) in outputs/figures/.
# Sized for IEEE columns: single = 3.5 in, double = 7.16 in. Serif 8 pt.
#
#   F01 system architecture            F09 per-customer F1 violins
#   F02 evaluation protocols A vs B    F10 Local vs Federated F1 scatter (299 pts)
#   F03 Conv-AE v2 architecture        F11 detection-rate heatmap per attack phase
#   F04 FedAvg round workflow          F12 anomaly-score distributions
#   F05 FL convergence                 F13 example normal vs attacked day
#   F06 ROC curves                     F14 Protocol A vs B comparison
#   F07 precision-recall curves        F15 confusion matrices
#   F08 metric bar chart               F16 model ablation (v1 / v2 / FC-AE)
#
# Needs: compare_results.py run first (reads its CSVs + eval store).
# Run:   python "Step 3\make_figures.py"
# =====================================================================

import json
import os
import pickle

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_curve, precision_recall_curve, roc_auc_score, average_precision_score

from common import (load_cache, build_model, make_splits, ckpt_path, interval_errors, day_scores,
                    OUT_DIR, FIG_DIR, METHODS, MODELS, PROTOCOLS, PRIMARY_MODEL, PRIMARY_SCORE,
                    MODEL_LABELS, ATTACK_PHASE_LABELS, TRAIN_DAYS, PHASE1_DAYS, N_DAYS, THRESHOLD_PERCENTILE)

plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "legend.fontsize": 6.5, "xtick.labelsize": 7, "ytick.labelsize": 7, "lines.linewidth": 1.1,
    "savefig.dpi": 300, "savefig.bbox": "tight", "axes.spines.top": False, "axes.spines.right": False})
COL, DCOL = 3.5, 7.16
C = {"Local": "#4C72B0", "Federated": "#DD8452", "Centralized": "#55A868"}
PL = {"A": "Protocol A (realistic)", "B": "Protocol B (benchmark-matched)"}


def save(fig, name):
    fig.savefig(os.path.join(FIG_DIR, name + ".png"))
    fig.savefig(os.path.join(FIG_DIR, name + ".pdf"))
    plt.close(fig)
    print(f"  saved {name}")


def box(ax, x, y, w, h, text, fc="#E8F0FE", ec="#1A3E72", fs=6.5, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=0.8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal")


def arrow(ax, p1, p2, text=None, color="#333333", fs=5.5, off=(0, 0.08), style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=7, lw=0.8, color=color, linestyle=ls))
    if text:
        ax.text((p1[0] + p2[0]) / 2 + off[0], (p1[1] + p2[1]) / 2 + off[1], text, fontsize=fs,
                ha="center", va="bottom", color=color)


def canvas(w, h, xmax, ymax):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    return fig, ax


# ---------------------------------------------------------------------
# SCHEMATICS
# ---------------------------------------------------------------------
def f01_architecture():
    fig, ax = canvas(DCOL, 3.0, 14, 6)
    # prosumers
    for i, (lbl, y) in enumerate([("Prosumer 1", 4.6), ("Prosumer 2", 3.3), ("Prosumer 299", 1.2)]):
        box(ax, 0.2, y, 2.6, 0.95, f"{lbl}\nSmart meter (GC, GG)\nLocal AE detector", fs=5.8)
        arrow(ax, (2.8, y + 0.62), (5.0, 3.35), color="#1A3E72")
        arrow(ax, (5.0, 3.05), (2.8, y + 0.32), color="#C0504D")
    ax.text(1.5, 2.55, "...", ha="center", fontsize=10)
    ax.text(3.9, 4.75, r"upload $w_k, n_k$", fontsize=5.5, color="#1A3E72")
    ax.text(3.9, 1.35, r"broadcast $w^{t+1}$", fontsize=5.5, color="#C0504D")
    box(ax, 5.0, 2.5, 2.6, 1.4, "FL aggregation server\nFedAvg\n" + r"$w^{t+1}=\sum_k \frac{n_k}{N} w_k$",
        fc="#FFF2CC", ec="#B8860B", fs=6)
    ax.text(6.3, 2.2, "no raw data received", fontsize=5.5, ha="center", style="italic")
    # attacker
    box(ax, 0.2, 0.05, 2.6, 0.7, "FDIA attacker\n(scaling, ramp, replay, coordinated)", fc="#FDE2E1", ec="#C0504D", fs=5.5)
    arrow(ax, (1.5, 0.75), (1.5, 1.2), color="#C0504D")
    # downstream pipeline
    box(ax, 8.4, 4.4, 2.5, 1.0, "Continual learning\n(Step 4)", fc="#E2F0D9", ec="#548235")
    box(ax, 8.4, 2.7, 2.5, 1.0, r"Attack probability $p_t$" + "\nper prosumer", fc="#E2F0D9", ec="#548235")
    box(ax, 11.3, 2.7, 2.5, 1.0, "Economic mitigation\n" + r"$p_t C_{FN} > (1-p_t)C_{FP}+C_{mit}$" + "\n(Step 5)",
        fc="#EDE7F6", ec="#5E35B1", fs=5.5)
    box(ax, 11.3, 0.9, 2.5, 1.0, "P2P CDA market\nclearing & surplus\n(Step 6)", fc="#EDE7F6", ec="#5E35B1")
    arrow(ax, (7.6, 3.2), (8.4, 3.2))
    arrow(ax, (9.65, 3.7), (9.65, 4.4))
    arrow(ax, (10.9, 3.2), (11.3, 3.2))
    arrow(ax, (12.55, 2.7), (12.55, 1.9))
    ax.text(7.0, 5.75, "Layer 1: privacy-preserving cyber defense (Steps 2-4)", fontsize=6.5, ha="center", fontweight="bold")
    ax.text(12.55, 5.75, "Layer 2: economic resilience", fontsize=6.5, ha="center", fontweight="bold")
    save(fig, "F01_system_architecture")


def f02_protocols():
    fig, ax = canvas(DCOL, 2.4, 14, 5)
    ax.text(0, 4.6, "(a) Protocol A - realistic temporal split (ours)", fontsize=7, fontweight="bold")
    sc = 12.5 / N_DAYS
    x0 = 1.0
    segs = [(0, TRAIN_DAYS, "Train (clean)\nd 0-304", "#9DC3E6"),
            (TRAIN_DAYS, PHASE1_DAYS, "Thr.\nval", "#FFD966"),
            (PHASE1_DAYS, 601, "Test: Scaling", "#F4B183"), (601, 851, "Test: Ramp", "#F8CBAD"),
            (851, 973, "Replay", "#E5A0A0"), (973, N_DAYS, "Coord.", "#D88080")]
    for a, b, lbl, col in segs:
        ax.add_patch(plt.Rectangle((x0 + a * sc, 3.3), (b - a) * sc, 0.8, fc=col, ec="k", lw=0.5))
        ax.text(x0 + (a + b) / 2 * sc, 3.7, lbl, ha="center", va="center", fontsize=5.3)
    ax.text(x0, 3.05, "Year 1 (no attacks)", fontsize=5.5)
    ax.text(x0 + PHASE1_DAYS * sc, 3.05, "Years 2-3: ~10% attacked days, never seen in training", fontsize=5.5)
    ax.text(0, 2.2, "(b) Protocol B - benchmark-matched (B1: shuffled 2:1 split, balanced test)", fontsize=7, fontweight="bold")
    box(ax, 1.0, 0.4, 2.6, 1.2, "All benign days\n(3 years)\nrandomly shuffled", fc="#DDEBF7", fs=6)
    box(ax, 4.6, 1.0, 2.6, 0.8, "2/3 train\n(10% -> threshold)", fc="#9DC3E6", fs=6)
    box(ax, 4.6, 0.0, 2.6, 0.8, "1/3 benign test", fc="#C9C9C9", fs=6)
    box(ax, 8.2, 0.0, 2.6, 0.8, "Attacked days\n(equal count)", fc="#F4B183", fs=6)
    box(ax, 11.4, 0.4, 2.4, 1.0, "Balanced test\n50% / 50%", fc="#FFF2CC", ec="#B8860B", fs=6)
    arrow(ax, (3.6, 1.0), (4.6, 1.4))
    arrow(ax, (3.6, 1.0), (4.6, 0.4))
    arrow(ax, (7.2, 0.4), (11.4, 0.8))
    arrow(ax, (10.8, 0.4), (11.4, 0.7))
    save(fig, "F02_evaluation_protocols")


def f03_conv_ae():
    fig, ax = canvas(DCOL, 1.9, 14, 3.6)
    layers = [("Input\n2x48", 1.6), ("Conv1d k4 s2\n16x24", 1.3), ("Conv1d k4 s2\n32x12", 1.0),
              ("Flatten\n384", 0.9), ("Linear\nz: 24", 0.45), ("Linear\n384", 0.9),
              ("ConvT k4 s2\n16x24", 1.3), ("ConvT k4 s2\nOutput 2x48", 1.6)]
    xs = np.linspace(0.3, 12.4, len(layers))
    for i, ((lbl, h), x) in enumerate(zip(layers, xs)):
        fc = "#FFD966" if "z:" in lbl else ("#9DC3E6" if i < 4 else "#C5E0B4")
        hh = h * 1.5
        box(ax, x, 1.8 - hh / 2, 1.3, hh, lbl, fc=fc, fs=5.6)
        if i < len(layers) - 1:
            arrow(ax, (x + 1.3, 1.8), (xs[i + 1], 1.8))
    ax.text(3.3, 3.4, "Encoder", fontsize=7, ha="center", fontweight="bold")
    ax.text(10.3, 3.4, "Decoder", fontsize=7, ha="center", fontweight="bold")
    ax.text(7.0, 0.05, "Anomaly score = max over 48 half-hours of the squared reconstruction error; "
            "alarm if score > 95th pct of benign validation scores", fontsize=5.8, ha="center")
    save(fig, "F03_conv_ae_v2_architecture")


def f04_fedavg():
    fig, ax = canvas(COL, 2.6, 10, 7.4)
    box(ax, 3.0, 5.6, 4.0, 1.3, "Server\nglobal model $w^t$", fc="#FFF2CC", ec="#B8860B")
    box(ax, 0.1, 2.6, 3.6, 1.6, "(2) Local training\nE epochs on private\nmeter data", fc="#DDEBF7")
    box(ax, 6.3, 2.6, 3.6, 1.6, "(4) FedAvg\n" + r"$w^{t+1}=\sum_k \frac{n_k}{N} w_k$", fc="#FFF2CC", ec="#B8860B")
    box(ax, 3.0, 0.1, 4.0, 1.3, "Clients k = 1..299\n(raw data stays home)", fc="#E2F0D9", ec="#548235")
    arrow(ax, (3.0, 6.2), (1.9, 4.2), "(1) broadcast $w^t$", off=(-0.9, 0.1))
    arrow(ax, (1.9, 2.6), (3.0, 1.0))
    arrow(ax, (7.0, 1.0), (8.1, 2.6), "(3) upload $w_k, n_k$", off=(0.9, -0.3))
    arrow(ax, (8.1, 4.2), (7.0, 6.2), "repeat R rounds", off=(0.9, 0.1))
    save(fig, "F04_fedavg_workflow")


# ---------------------------------------------------------------------
# RESULT FIGURES
# ---------------------------------------------------------------------
def f05_convergence():
    fig, axes = plt.subplots(1, 2, figsize=(DCOL, 2.2))
    for ax, protocol in zip(axes, PROTOCOLS):
        for model, ls in [("conv2", "-"), ("fcae", "--"), ("conv1", ":")]:
            hp = os.path.join(OUT_DIR, f"federated_history_{model}_{protocol}.csv")
            if not os.path.exists(hp):
                continue
            h = pd.read_csv(hp)
            line, = ax.plot(h["round"], h["val_mse"], ls, label=f"FedAvg {model}")
            mp = os.path.join(OUT_DIR, f"centralized_meta_{model}_{protocol}.json")
            if os.path.exists(mp):
                ax.axhline(json.load(open(mp))["final_val_mse"], color=line.get_color(), lw=0.7, alpha=0.6,
                           ls="-.", label=f"Centralized {model}")
        ax.set_yscale("log")
        ax.set_xlabel("Federated round")
        ax.set_ylabel("Weighted validation MSE")
        ax.set_title(PL[protocol])
        ax.legend(ncol=2)
        ax.grid(alpha=0.3)
    save(fig, "F05_fl_convergence")


def _curve_fig(store, kind, name):
    fig, axes = plt.subplots(1, 2, figsize=(DCOL, 2.6))
    for ax, protocol in zip(axes, PROTOCOLS):
        prev = None
        for m in METHODS:
            key = (protocol, PRIMARY_MODEL, m, PRIMARY_SCORE)
            if key not in store:
                continue
            d = store[key]
            if kind == "roc":
                fpr, tpr, _ = roc_curve(d["y"], d["norm_score"])
                ax.plot(fpr, tpr, color=C[m], label=f"{m} (AUC={roc_auc_score(d['y'], d['norm_score']):.3f})")
            else:
                p, r, _ = precision_recall_curve(d["y"], d["norm_score"])
                ax.plot(r, p, color=C[m], label=f"{m} (AP={average_precision_score(d['y'], d['norm_score']):.3f})")
                prev = d["y"].mean()
        if kind == "roc":
            ax.plot([0, 1], [0, 1], "k:", lw=0.7, label="Random")
            ax.set_xlabel("False alarm rate")
            ax.set_ylabel("Detection rate")
        else:
            if prev is not None:
                ax.axhline(prev, color="k", ls=":", lw=0.7, label=f"Random (prevalence={prev:.2f})")
            ax.set_xlabel("Recall (detection rate)")
            ax.set_ylabel("Precision")
        ax.set_title(f"{PL[protocol]} - {PRIMARY_MODEL}")
        ax.legend(loc="lower right" if kind == "roc" else "upper right")
        ax.grid(alpha=0.3)
    save(fig, name)


def f08_bars(summ):
    metrics = ["ACC", "PR", "DR", "F1", "AUC_ROC", "AUC_PR"]
    fig, axes = plt.subplots(1, 2, figsize=(DCOL, 2.4), sharey=True)
    for ax, protocol in zip(axes, PROTOCOLS):
        sub = summ[(summ.protocol == protocol) & (summ.model == PRIMARY_MODEL) & (summ.score == PRIMARY_SCORE)]
        xs = np.arange(len(metrics))
        for i, m in enumerate(METHODS):
            r = sub[sub.method == m]
            if r.empty:
                continue
            r = r.iloc[0]
            ax.bar(xs + (i - 1) * 0.27, [r[k + "_mean"] * 100 for k in metrics], 0.27, color=C[m],
                   yerr=[r[k + "_std"] * 100 for k in metrics], capsize=1.5, error_kw={"lw": 0.6}, label=m)
        ax.set_xticks(xs)
        ax.set_xticklabels(["ACC", "Prec.", "DR", "F1", "AUC-ROC", "AUC-PR"])
        ax.set_title(PL[protocol])
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("Mean over 299 customers (%)")
    axes[0].legend()
    save(fig, "F08_metric_bars")


def f09_violins(df):
    fig, axes = plt.subplots(1, 2, figsize=(DCOL, 2.2), sharey=True)
    for ax, protocol in zip(axes, PROTOCOLS):
        sub = df[(df.protocol == protocol) & (df.model == PRIMARY_MODEL) & (df.score == PRIMARY_SCORE)]
        data = [sub[sub.method == m]["F1"].dropna().values * 100 for m in METHODS]
        if any(len(d) == 0 for d in data):
            continue
        parts = ax.violinplot(data, showmedians=True)
        for b, m in zip(parts["bodies"], METHODS):
            b.set_facecolor(C[m])
            b.set_alpha(0.6)
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels(METHODS)
        ax.set_title(PL[protocol])
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("Per-customer F1 (%)")
    save(fig, "F09_f1_violins")


def f10_scatter(df):
    fig, axes = plt.subplots(1, 2, figsize=(DCOL, 2.9))
    for ax, protocol in zip(axes, PROTOCOLS):
        sub = df[(df.protocol == protocol) & (df.model == PRIMARY_MODEL) & (df.score == PRIMARY_SCORE)]
        piv = sub.pivot(index="customer_id", columns="method", values="F1").dropna() * 100
        if piv.empty:
            continue
        better = piv["Federated"] > piv["Local"]
        ax.scatter(piv["Local"][better], piv["Federated"][better], s=6, color=C["Federated"],
                   label=f"Federated better ({better.sum()})")
        ax.scatter(piv["Local"][~better], piv["Federated"][~better], s=6, color=C["Local"],
                   label=f"Local better/equal ({(~better).sum()})")
        lim = [0, max(piv.max().max(), 1) * 1.05]
        ax.plot(lim, lim, "k--", lw=0.7)
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        ax.set_xlabel("Local model F1 (%)")
        ax.set_ylabel("Federated model F1 (%)")
        ax.set_title(f"{PL[protocol]} ({len(piv)} customers)")
        ax.legend(loc="upper left")
        ax.grid(alpha=0.3)
    save(fig, "F10_local_vs_federated_scatter")


def f11_heatmap(ph):
    names = list(ATTACK_PHASE_LABELS.values())
    fig, axes = plt.subplots(1, 2, figsize=(DCOL, 1.8))
    for ax, protocol in zip(axes, PROTOCOLS):
        sub = ph[(ph.protocol == protocol) & (ph.model == PRIMARY_MODEL) & (ph.score == PRIMARY_SCORE)]
        if sub.empty:
            continue
        mat = np.array([sub[sub.method == m][names].values[0] * 100 for m in METHODS])
        im = ax.imshow(mat, cmap="YlOrRd", vmin=0, vmax=100, aspect="auto")
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                ax.text(j, i, f"{mat[i, j]:.1f}", ha="center", va="center", fontsize=6.5)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names)
        ax.set_yticks(range(len(METHODS)))
        ax.set_yticklabels(METHODS)
        ax.set_title(f"Detection rate (%) - {PL[protocol]}")
        fig.colorbar(im, ax=ax, fraction=0.04)
    save(fig, "F11_phase_detection_heatmap")


def f12_distributions(store):
    fig, axes = plt.subplots(1, 3, figsize=(DCOL, 2.0), sharey=True)
    for ax, m in zip(axes, METHODS):
        key = ("A", PRIMARY_MODEL, m, PRIMARY_SCORE)
        if key not in store:
            continue
        d = store[key]
        s = np.log10(np.clip(d["norm_score"], 1e-4, None))
        bins = np.linspace(np.percentile(s, 0.5), np.percentile(s, 99.5), 60)
        ax.hist(s[d["y"] == 0], bins=bins, density=True, alpha=0.55, color="#4C72B0", label="Normal days")
        ax.hist(s[d["y"] == 1], bins=bins, density=True, alpha=0.55, color="#C0504D", label="Attacked days")
        ax.axvline(0, color="k", ls="--", lw=0.8, label="Threshold")
        ax.set_xlabel(r"$\log_{10}$(score / threshold)")
        ax.set_title(f"{m} (Protocol A)")
    axes[0].set_ylabel("Density")
    axes[0].legend()
    save(fig, "F12_score_distributions")


def f13_example(cache):
    path = ckpt_path("Federated", PRIMARY_MODEL, "A")
    if not os.path.exists(path):
        return
    net = build_model(PRIMARY_MODEL)
    net.load_state_dict(torch.load(path))
    X, y = cache["X"], cache["y"].numpy()
    k = 0
    test = np.arange(PHASE1_DAYS, N_DAYS)
    att = test[y[k][test] == 1]
    nor = test[y[k][test] == 0]
    if len(att) == 0 or len(nor) == 0:
        return
    days = {"Normal day": nor[0], "Attacked day": att[0]}
    with torch.no_grad():
        net.eval()
        fig, axes = plt.subplots(2, 2, figsize=(DCOL, 3.0), sharex=True)
        hours = np.arange(48) / 2
        for i, (lbl, d) in enumerate(days.items()):
            x = X[k][d:d + 1]
            rec = net(x)[0].numpy()
            for j, ch in enumerate(["Consumption (GC)", "Generation (GG)"]):
                ax = axes[i, j]
                ax.plot(hours, x[0, j].numpy(), color="k", label="Observed")
                ax.plot(hours, rec[j], color=C["Federated"], ls="--", label="Reconstruction")
                ax.fill_between(hours, x[0, j].numpy(), rec[j], color="#C0504D", alpha=0.25, label="Error")
                ax.set_title(f"{lbl} (day {d}) - {ch}")
                ax.grid(alpha=0.3)
                if j == 0:
                    ax.set_ylabel("Scaled value")
                if i == 1:
                    ax.set_xlabel("Hour of day")
        axes[0, 0].legend()
    save(fig, "F13_example_reconstruction")


def f14_protocol_compare(summ):
    metrics = [("ACC", "Accuracy"), ("F1", "F1"), ("AUC_ROC", "AUC-ROC")]
    fig, axes = plt.subplots(1, 3, figsize=(DCOL, 2.0), sharey=True)
    for ax, (mk, lbl) in zip(axes, metrics):
        xs = np.arange(len(METHODS))
        for i, protocol in enumerate(PROTOCOLS):
            sub = summ[(summ.protocol == protocol) & (summ.model == PRIMARY_MODEL) & (summ.score == PRIMARY_SCORE)]
            vals = [sub[sub.method == m][mk + "_mean"].values[0] * 100 if (sub.method == m).any() else 0 for m in METHODS]
            ax.bar(xs + (i - 0.5) * 0.38, vals, 0.38, label=PL[protocol],
                   color=["#9DC3E6", "#F4B183"][i], edgecolor="k", lw=0.4)
        ax.set_xticks(xs)
        ax.set_xticklabels(METHODS, fontsize=6.5)
        ax.set_title(lbl)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("Mean over customers (%)")
    axes[0].legend(fontsize=6)
    save(fig, "F14_protocol_A_vs_B")


def f15_confusion(summ):
    fig, axes = plt.subplots(2, 3, figsize=(DCOL, 4.0))
    for i, protocol in enumerate(PROTOCOLS):
        sub = summ[(summ.protocol == protocol) & (summ.model == PRIMARY_MODEL) & (summ.score == PRIMARY_SCORE)]
        for j, m in enumerate(METHODS):
            ax = axes[i, j]
            r = sub[sub.method == m]
            if r.empty:
                ax.axis("off")
                continue
            r = r.iloc[0]
            cm = np.array([[r["TN"], r["FP"]], [r["FN"], r["TP"]]], dtype=float)
            norm = cm / cm.sum(axis=1, keepdims=True)
            ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
            for a in range(2):
                for b in range(2):
                    ax.text(b, a, f"{int(cm[a, b]):,}\n({norm[a, b] * 100:.1f}%)", ha="center", va="center",
                            fontsize=6.5, color="white" if norm[a, b] > 0.6 else "black")
            ax.set_xticks([0, 1])
            ax.set_xticklabels(["Pred. normal", "Pred. attack"])
            ax.set_yticks([0, 1])
            ax.set_yticklabels(["Normal", "Attack"])
            ax.set_title(f"{m} - Protocol {protocol}")
    save(fig, "F15_confusion_matrices")


def f16_model_ablation(summ):
    fig, axes = plt.subplots(1, 2, figsize=(DCOL, 2.2))
    for ax, mk in zip(axes, ["F1", "AUC_ROC"]):
        sub = summ[(summ.protocol == "A") & (summ.score == PRIMARY_SCORE)]
        models = [m for m in MODELS if (sub.model == m).any()]
        xs = np.arange(len(models))
        for i, meth in enumerate(METHODS):
            vals = [sub[(sub.model == mo) & (sub.method == meth)][mk + "_mean"].values[0] * 100 for mo in models]
            ax.bar(xs + (i - 1) * 0.27, vals, 0.27, color=C[meth], label=meth)
        ax.set_xticks(xs)
        ax.set_xticklabels([MODEL_LABELS[m].split(" (")[0] for m in models])
        ax.set_ylabel(f"Mean {mk.replace('_', '-')} (%)")
        ax.set_title(f"Model ablation, Protocol A - {mk.replace('_', '-')}")
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend()
    save(fig, "F16_model_ablation")


def main():
    print(f"Writing figures to {FIG_DIR}")
    for name, fn in [("F01", f01_architecture), ("F02", f02_protocols), ("F03", f03_conv_ae), ("F04", f04_fedavg)]:
        try:
            fn()
        except Exception as e:
            print(f"  [warn] {name} failed: {type(e).__name__}: {e}")

    summ = pd.read_csv(os.path.join(OUT_DIR, "step3_summary.csv"))
    df = pd.read_csv(os.path.join(OUT_DIR, "step3_per_customer_metrics.csv"))
    ph = pd.read_csv(os.path.join(OUT_DIR, "step3_phase_detection.csv"))
    with open(os.path.join(OUT_DIR, "step3_eval_store.pkl"), "rb") as f:
        store = pickle.load(f)

    steps = [("F05", f05_convergence, ()), ("F06", _curve_fig, (store, "roc", "F06_roc_curves")),
             ("F07", _curve_fig, (store, "pr", "F07_pr_curves")), ("F08", f08_bars, (summ,)),
             ("F09", f09_violins, (df,)), ("F10", f10_scatter, (df,)), ("F11", f11_heatmap, (ph,)),
             ("F12", f12_distributions, (store,)), ("F13", f13_example, (load_cache(),)),
             ("F14", f14_protocol_compare, (summ,)), ("F15", f15_confusion, (summ,)),
             ("F16", f16_model_ablation, (summ,))]
    for name, fn, args in steps:
        try:
            fn(*args)
        except Exception as e:                      # one broken figure must not stop the rest
            print(f"  [warn] {name} failed: {type(e).__name__}: {e}")
    print("Done.")


if __name__ == "__main__":
    main()
