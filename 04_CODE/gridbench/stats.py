"""Aggregation and uncertainty for clustered benchmark results.

The replication unit is the authority (5 clusters). Seeds (and label draws) are
nested replicates that share the same underlying series."""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

KEYS = ["experiment", "ba", "seed", "condition"]


def method_label(df: pd.DataFrame) -> pd.Series:
    b = df["budget"] if "budget" in df else pd.Series(np.nan, index=df.index)
    return np.where(b.isna(), df["method"], df["method"] + "_B" + b.fillna(0).astype(int).astype(str))


def cell_means(runs: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    """Average label draws within each (cell, method) -> one value per cell and method."""
    r = runs.copy()
    r["mlabel"] = method_label(r)
    return r.groupby(KEYS + ["mlabel"], as_index=False)[metrics].mean()


def hier_bootstrap(values: pd.DataFrame, col: str, reps: int, seed: int) -> tuple[float, float, float]:
    """Two-stage percentile bootstrap of the grand mean: resample authorities with
    replacement, then seeds within each sampled authority. `values` has columns
    ba, seed, col (one row per ba-seed, already averaged over other factors)."""
    v = values.dropna(subset=[col])
    groups = [g[col].to_numpy() for _, g in v.groupby("ba")]
    point = float(np.mean([g.mean() for g in groups]))
    rng = np.random.default_rng(seed)
    G = len(groups)
    est = np.empty(reps)
    for i in range(reps):
        pick = rng.integers(0, G, size=G)
        est[i] = np.mean([groups[j][rng.integers(0, len(groups[j]), size=len(groups[j]))].mean() for j in pick])
    lo, hi = np.percentile(est, [2.5, 97.5])
    return point, float(lo), float(hi)


def sign_flip_p(ba_means: np.ndarray) -> float:
    """Exact two-sided sign-flip test of mean(ba_means) = 0 over all 2^G sign patterns."""
    x = np.asarray(ba_means, float)
    obs = abs(x.mean())
    stats = [abs((x * np.array(s)).mean()) for s in itertools.product([-1, 1], repeat=len(x))]
    return float(np.mean([s >= obs - 1e-12 for s in stats]))


def paired_difference(cm: pd.DataFrame, a: str, b: str, metric: str, reps: int, seed: int,
                      conditions: list[str] | None = None) -> dict:
    """Paired difference a - b of `metric` on matched cells; averaged over the selected
    conditions within (ba, seed) before bootstrapping."""
    d = cm if conditions is None else cm[cm["condition"].isin(conditions)]
    wide = d.pivot_table(index=["ba", "seed", "condition"], columns="mlabel", values=metric)
    diff = (wide[a] - wide[b]).rename("diff").reset_index()
    per_bs = diff.groupby(["ba", "seed"], as_index=False)["diff"].mean()
    point, lo, hi = hier_bootstrap(per_bs, "diff", reps, seed)
    ba_means = per_bs.groupby("ba")["diff"].mean()
    return {"a": a, "b": b, "metric": metric, "conditions": "all" if conditions is None else "+".join(conditions),
            "mean_diff": point, "ci_lo": lo, "ci_hi": hi,
            "n_ba_positive": int((ba_means > 0).sum()), "n_ba": int(len(ba_means)),
            "sign_flip_p": sign_flip_p(ba_means.to_numpy()),
            "n_cells": int(len(diff)), **{f"ba_{k}": float(v) for k, v in ba_means.items()}}
