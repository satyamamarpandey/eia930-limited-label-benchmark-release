"""POST-HOC EXPLORATORY analysis (not pre-registered).

Question: is PU-LR's flatline failure on SWPP associated with naturally repeated
values in SWPP's training background (used as weak negatives)?
Intervention: drop natural-suspect training hours from the weak-negative set
(budgeted labels and everything else unchanged), condition 0% added missingness.
Writes 05_RESULTS/final/exploratory/swpp_weak_negative_cleaning.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
from gridbench import features as feat, inject, io, metrics  # noqa: E402
from gridbench.config import load_config, project_paths  # noqa: E402
from gridbench.detectors import PULogisticDetector, sample_label_budget  # noqa: E402
from gridbench.experiment import FEATURE_SETS, injected, make_context, observed  # noqa: E402


def main():
    cfg = load_config()
    paths = project_paths(cfg)
    df = io.load_eia(paths["inputs"], cfg["data"]["authorities"])
    rows = []
    for ba_idx, ba in enumerate(cfg["data"]["authorities"]):
        ctx = make_context(df, ba, ba_idx, cfg)
        cond = cfg["missingness"]["conditions"][0]
        for seed in cfg["seeds"]:
            events, x_inj, label, owner = injected(ctx, seed, cfg, 6)
            x_obs, _ = observed(ctx, x_inj, owner, seed, 0, cond, cfg)
            F = feat.compute_features(x_obs, ctx.hour, ctx.dow, cfg["features"])
            scored = ~np.isnan(x_obs)
            tr = np.flatnonzero(scored & (ctx.split_of == "train") & ~ctx.warm)
            Ft = F.iloc[tr].reset_index(drop=True)
            fam_h = np.array([""] * len(owner), dtype=object)
            for e in events:
                fam_h[owner == e.event_id] = e.family
            ev = scored & (ctx.split_of == "test")
            fl = ev & (~label | (fam_h == "flatline"))
            for B in (32, 128):
                for d in range(cfg["label_draws_per_seed"]):
                    rng = inject.make_rng(seed, ba_idx, inject.STREAM_LABELS, B, d, 0)
                    pos, neg, unl = sample_label_budget(B, label, owner, tr, rng)
                    for variant, u in (("primary", unl), ("drop_natural_suspect", unl[~ctx.suspect[tr][unl]])):
                        det = PULogisticDetector(FEATURE_SETS["full"]).fit(Ft, pos, neg, u)
                        s = det.score(F)
                        rows.append({"ba": ba, "seed": seed, "budget": B, "draw": d, "variant": variant,
                                     "weak_negatives": len(u),
                                     "ap": metrics.ranking_metrics(s[ev], label[ev], 0.01)["ap"],
                                     "ap_flatline": metrics.ranking_metrics(s[fl], label[fl], 0.01)["ap"]})
    out = paths["results"] / "final" / "exploratory"
    out.mkdir(exist_ok=True)
    r = pd.DataFrame(rows)
    r.to_csv(out / "swpp_weak_negative_cleaning.csv", index=False)
    print(r.groupby(["ba", "budget", "variant"])[["weak_negatives", "ap", "ap_flatline"]].mean().round(3))


if __name__ == "__main__":
    main()
