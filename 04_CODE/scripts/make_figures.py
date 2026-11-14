"""Publication figures. Every plotted number is read from saved outputs in
05_RESULTS/final (tables or raw score files); the data behind each figure is also
written next to it as CSV (05_RESULTS/figures/*_data.csv) for auditing.

Usage: python scripts/make_figures.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
from gridbench import inject  # noqa: E402
from gridbench.config import load_config, project_paths  # noqa: E402

METHODS = ["stat", "iforest", "pu_B8", "pu_B32", "pu_B128"]
LABEL = {"stat": "Robust seasonal", "iforest": "Isolation Forest", "pu_B8": "PU-LR B=8",
         "pu_B32": "PU-LR B=32", "pu_B128": "PU-LR B=128"}
# validated categorical slots (orange, aqua) + one-hue blue ramp for the ordered label budget
COLOR = {"stat": "#eb6834", "iforest": "#1baf7a", "pu_B8": "#9ec5f0", "pu_B32": "#2a78d6", "pu_B128": "#0d3f7f"}
MARKER = {"stat": "s", "iforest": "^", "pu_B8": "o", "pu_B32": "o", "pu_B128": "o"}
COND = ["none", "mcar5", "mcar15", "block5", "block15"]
COND_LABEL = {"none": "0%", "mcar5": "MCAR 5%", "mcar15": "MCAR 15%", "block5": "Block 5%", "block15": "Block 15%"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"], "font.size": 8,
    "axes.titlesize": 8, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.4,
    "savefig.dpi": 300, "pdf.fonttype": 42, "ps.fonttype": 42})
COL1, COL2 = 3.45, 7.0


def save(fig, out, name, data: pd.DataFrame):
    fig.savefig(out / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02,
                metadata={"CreationDate": None})  # no timestamp: identical bytes on every rebuild
    fig.savefig(out / f"{name}.png", bbox_inches="tight", pad_inches=0.02, dpi=200)
    data.to_csv(out / f"{name}_data.csv", index=False)
    plt.close(fig)


def fig_per_ba(T, out):
    d = pd.read_csv(T / "table_per_ba_none.csv")
    d = d[d.mlabel.isin(METHODS)]
    bas = sorted(d.ba.unique())
    fig, ax = plt.subplots(figsize=(COL1, 2.1))
    off = np.linspace(-0.28, 0.28, len(METHODS))
    for k, m in enumerate(METHODS):
        y = d[d.mlabel == m].set_index("ba").loc[bas, "ap"]
        ax.scatter(np.arange(len(bas)) + off[k], y, s=22, marker=MARKER[m], color=COLOR[m], label=LABEL[m],
                   edgecolor="white", linewidth=0.6, zorder=3)
    prev = d[d.mlabel == "stat"].set_index("ba").loc[bas, "prevalence"]
    ax.scatter(np.arange(len(bas)), prev, marker="_", s=120, color=MUTED, label="Prevalence (random AP)", zorder=2)
    ax.set_xticks(np.arange(len(bas)), bas)
    ax.set_ylabel("Test average precision")
    ax.set_ylim(0, None)
    ax.legend(ncol=2, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.33), handletextpad=0.3,
              columnspacing=0.8)
    save(fig, out, "fig_ap_per_authority", d)


def fig_missingness(T, out):
    d = pd.read_csv(T / "table_by_condition.csv")
    fig, ax = plt.subplots(figsize=(COL1, 2.0))
    x = np.arange(len(COND))
    off = np.linspace(-0.2, 0.2, len(METHODS))
    for k, m in enumerate(METHODS):
        r = d[d.method == m].set_index("condition").loc[COND]
        ax.errorbar(x + off[k], r.ap, yerr=[r.ap - r.ap_lo, r.ap_hi - r.ap], fmt=MARKER[m] + "-", color=COLOR[m],
                    ms=4, lw=1.0, elinewidth=0.8, capsize=0, label=LABEL[m], mec="white", mew=0.5)
    ax.set_xticks(x, [COND_LABEL[c] for c in COND])
    ax.set_ylabel("Test AP (95% cluster CI)")
    ax.set_xlabel("Background missingness added")
    ax.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.3), handletextpad=0.3,
              columnspacing=0.8)
    save(fig, out, "fig_ap_missingness", d)


def fig_family_tier(T, out):
    d = pd.read_csv(T / "table_event_family_tier_none.csv")
    d = d[d.mlabel.isin(METHODS)]
    fig, axes = plt.subplots(1, 5, figsize=(COL2, 1.75), sharey=True)
    for ax, fam in zip(axes, inject.FAMILIES):
        for m in METHODS:
            r = d[(d.mlabel == m) & (d.family == fam)].set_index("tier").loc[inject.TIERS]
            ax.plot(np.arange(3), r.detected, marker=MARKER[m], color=COLOR[m], ms=4, lw=1.1, mec="white", mew=0.5,
                    label=LABEL[m])
        ax.set_title(fam.replace("_", " "), color=INK)
        ax.set_xticks(np.arange(3), ["low", "med", "high"])
        ax.set_ylim(-0.03, 1.03)
    axes[0].set_ylabel("Event detection rate")
    axes[2].set_xlabel("Severity tier")
    axes[0].legend(ncol=5, frameon=False, loc="upper left", bbox_to_anchor=(0.0, 1.42), handletextpad=0.3,
                   columnspacing=1.2)
    save(fig, out, "fig_event_detection_family_tier", d)


def fig_alert_burden(raw, cfg, out):
    """Recall vs. false alerts per authority-week on test hours (condition none),
    from saved scores; thresholds swept on test scores (ranking view, not tuned)."""
    grid = np.array([0.25, 0.5, 1, 2, 3, 5, 8, 12, 20, 30, 50])
    rows = []
    for ba in cfg["data"]["authorities"]:
        for seed in cfg["seeds"]:
            z = np.load(raw / "scores" / f"{ba}_s{seed}_none.npz", allow_pickle=True)
            ev = (z["split_of"] == "test") & z["scored"]
            y = z["label"][ev]
            weeks = ev.sum() / 168.0
            for k in [k for k in z.files if k.startswith("score__")]:
                key = k.replace("score__", "")
                ml = key.rsplit("_d", 1)[0] if key.startswith("pu_") else key
                s = z[k].astype(float)[ev]
                neg = np.sort(s[~y])[::-1]
                for g in grid:
                    nfp = int(np.floor(g * weeks))
                    thr = neg[nfp] if nfp < len(neg) else -np.inf  # alerts strictly above thr -> <= nfp FPs
                    rows.append({"ba": ba, "seed": seed, "method": ml, "fa_week": g,
                                 "recall": float((s[y] > thr).mean())})
    d = pd.DataFrame(rows).groupby(["method", "ba", "seed", "fa_week"], as_index=False)["recall"].mean()
    agg = d.groupby(["method", "ba", "fa_week"], as_index=False)["recall"].mean().groupby(
        ["method", "fa_week"], as_index=False)["recall"].mean()
    fig, ax = plt.subplots(figsize=(COL1, 2.0))
    for m in METHODS:
        r = agg[agg.method == m]
        ax.plot(r.fa_week, r.recall, marker=MARKER[m], color=COLOR[m], ms=3.5, label=LABEL[m], mec="white", mew=0.4)
    ax.set_xscale("log")
    ax.set_xticks([0.25, 1, 3, 10, 30], ["0.25", "1", "3", "10", "30"])
    ax.set_xlabel("False alerts per authority-week (test)")
    ax.set_ylabel("Hour-level recall")
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, loc="upper left", ncol=1)
    save(fig, out, "fig_alert_burden", agg)


def fig_example(raw, cfg, out, ba="PJM", seed=11, days=("2024-10-01", "2024-10-29")):
    z = np.load(raw / "scores" / f"{ba}_s{seed}_mcar5.npz", allow_pickle=True)
    man = json.loads((project_paths(cfg)["data"] / "dataset_manifest.json").read_text())
    utc = pd.date_range(man["integrity"][ba]["utc_end_first"], periods=len(z["label"]), freq="h")
    m = (utc >= pd.Timestamp(days[0])) & (utc < pd.Timestamp(days[1]))
    val = (z["split_of"] == "val") & z["scored"]
    inj = pd.read_csv(raw / "injection_ground_truth.csv")
    inj = inj[(inj.ba == ba) & (inj.seed == seed) & (inj.n_train_events_per_family == 6)]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(COL2, 3.0), sharex=True, gridspec_kw={"height_ratios": [1.2, 1]})
    a1.plot(utc[m], z["x_orig"][m] / 1000, color=MUTED, lw=0.8, label="Reported demand")
    xo = z["x_obs"].copy()
    a1.plot(utc[m], xo[m] / 1000, color=INK, lw=0.9, label="Benchmark input (injected + 5% MCAR missing)")
    lo_, hi_ = np.nanmin(z["x_orig"][m]) / 1000, np.nanmax(xo[m]) / 1000
    a1.set_ylim(lo_ - 2, hi_ + 0.18 * (hi_ - lo_))
    shown = []
    for _, e in inj.iterrows():
        s0, s1 = pd.Timestamp(e.start_utc_end), pd.Timestamp(e.end_utc_end)
        if s1 >= pd.Timestamp(days[0]) and s0 < pd.Timestamp(days[1]):
            for a in (a1, a2):
                a.axvspan(s0 - pd.Timedelta(minutes=30), s1 + pd.Timedelta(minutes=30), color="#f3d9c9", lw=0, zorder=0)
            a1.annotate(e.family.replace("_", " ") + "\n(" + e.tier + ")", (s0, a1.get_ylim()[1]), fontsize=6.5,
                        color=INK, rotation=0, va="top", ha="center", xytext=(0, -1), textcoords="offset points")
            shown.append(e.to_dict())
    a1.set_ylabel("Demand (GW)")
    a1.legend(frameon=False, loc="lower left", ncol=2, bbox_to_anchor=(0.0, 1.0), borderaxespad=0.1)
    rows = []
    for key, ml in (("stat", "stat"), ("iforest", "iforest"), ("pu_B32_d0", "pu_B32")):
        s = z["score__" + key].astype(float)
        thr = np.quantile(s[val], 1 - cfg["thresholds"]["primary_alert_rate"], method="higher")
        q50 = np.quantile(s[val], 0.5)
        rel = (s - q50) / (thr - q50)  # 0 = validation median, 1 = alert threshold
        a2.plot(utc[m], rel[m], color=COLOR[ml], lw=0.9, label=LABEL[ml] + (" (draw 1)" if ml.startswith("pu") else ""))
        rows += [{"utc_end": str(t), "method": ml, "relative_score": float(v)} for t, v in zip(utc[m], rel[m])]
    a2.axhline(1, color=INK, lw=0.7, ls="--")
    a2.text(utc[m][-1], 1.05, "alert threshold", fontsize=6.5, ha="right", va="bottom", color=INK)
    a2.set_ylabel("Score (threshold = 1)")
    a2.set_ylim(-2, 4)
    a2.text(1.0, -0.32, "scores rescaled per detector: 0 = validation median, 1 = alert threshold; clipped to [-2, 4]",
            transform=a2.transAxes, fontsize=6.5, ha="right", color=MUTED)
    a2.legend(frameon=False, loc="lower left", ncol=3, bbox_to_anchor=(0.0, 1.0), borderaxespad=0.1)
    fig.align_ylabels()
    a1.set_ylim(a1.get_ylim())
    save(fig, out, "fig_example_timeseries", pd.DataFrame(rows))
    pd.DataFrame(shown).to_csv(out / "fig_example_timeseries_events.csv", index=False)


PAPER_FIGURES = ["fig_ap_per_authority", "fig_event_detection_family_tier", "fig_alert_burden", "fig_example_timeseries"]


def main():
    cfg = load_config()
    paths = project_paths(cfg)
    R = paths["results"] / "final"
    T, raw = R / "tables", R / "raw"
    out = paths["figures"]
    out.mkdir(exist_ok=True)
    fig_per_ba(T, out)
    fig_missingness(T, out)
    fig_family_tier(T, out)
    fig_alert_burden(raw, cfg, out)
    fig_example(raw, cfg, out)
    # the four figures used in the paper are also needed next to main.tex (02_MANUSCRIPT_SOURCE/figures)
    for name in PAPER_FIGURES:
        shutil.copyfile(out / f"{name}.pdf", paths["manuscript"] / "figures" / f"{name}.pdf")
    print("figures written to", out)


if __name__ == "__main__":
    main()
