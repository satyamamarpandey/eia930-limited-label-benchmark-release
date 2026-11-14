"""Integration on the real EIA files: split boundaries, no train/test overlap,
leakage controls, deterministic cells, provenance and reproducibility of saved outputs."""
import json

import numpy as np
import pandas as pd
import pytest
from conftest import missing

from gridbench import io
from gridbench.experiment import injected, make_context, run_cell


@pytest.fixture(scope="module")
def ctx(real_df, cfg):
    return make_context(real_df, "NYIS", 2, cfg)


def test_split_boundaries_disjoint_ordered(ctx, cfg):
    so = ctx.split_of
    pos = {k: np.flatnonzero(so == k) for k in ("train", "val", "test")}
    assert pos["train"].max() < pos["val"].min() and pos["val"].max() < pos["test"].min()
    assert sum(len(v) for v in pos.values()) == len(so)
    assert ctx.index[pos["train"].max()] == pd.Timestamp(cfg["splits"]["train"][1])
    assert ctx.index[pos["val"].min()] == pd.Timestamp(cfg["splits"]["val"][0])
    assert ctx.index[pos["test"].min()] == pd.Timestamp(cfg["splits"]["test"][0])
    assert ctx.index[pos["val"].max()] == pd.Timestamp(cfg["splits"]["val"][1])


def test_events_respect_splits(ctx, cfg):
    events, x_inj, label, owner = injected(ctx, 11, cfg, 6)
    for e in events:
        w = np.arange(e.start, e.start + e.length)
        assert set(ctx.split_of[w]) == {e.split}
    assert np.array_equal(x_inj[~label & ~np.isnan(ctx.x)], ctx.x[~label & ~np.isnan(ctx.x)])
    epf = cfg["injection"]["events_per_family"]
    assert len(events) == 5 * (epf["train"] + epf["val"] + epf["test"])


def test_cell_deterministic_and_test_isolated(ctx, cfg):
    variant = {"name": "t", "methods": ["stat", "iforest", "pu"], "budgets": [8]}
    cond = cfg["missingness"]["conditions"][2]
    r1, e1, _, _ = run_cell(ctx, 23, 2, cond, cfg, variant, "test")
    r2, e2, _, _ = run_cell(ctx, 23, 2, cond, cfg, variant, "test")
    a, b = pd.DataFrame(r1).drop(columns=["fit_seconds", "eval_seconds"]), pd.DataFrame(r2).drop(
        columns=["fit_seconds", "eval_seconds"])
    pd.testing.assert_frame_equal(a, b)
    for row in r1:
        if row["method"] == "pu":
            assert row["n_verified_labels"] == 8 and row["label_pos_correct"] and row["label_neg_correct"]


def test_model_unaffected_by_test_period_values(ctx, cfg):
    """Scores on train+val hours must not change when test-period demand is altered."""
    from dataclasses import replace
    variant = {"name": "t", "methods": ["stat", "iforest"], "keep_scores": True}
    cond = cfg["missingness"]["conditions"][0]
    _, _, _, b1 = run_cell(ctx, 11, 0, cond, cfg, variant, "test", keep_scores=True)
    x2 = ctx.x.copy()
    t = ctx.split_of == "test"
    x2[t] = x2[t] * 1.7
    ctx2 = replace(ctx, x=x2)
    _, _, _, b2 = run_cell(ctx2, 11, 0, cond, cfg, variant, "test", keep_scores=True)
    pre = ctx.split_of != "test"
    for k in ("stat", "iforest"):
        assert np.allclose(b1["scores"][k][pre], b2["scores"][k][pre])


def _results(paths, name):
    d = paths["results"] / name
    if not (d / "run_manifest.json").exists():
        missing(f"{name} results not present")
    return d


def test_final_run_provenance(paths, cfg):
    d = _results(paths, "final")
    m = json.loads((d / "run_manifest.json").read_text())
    assert m["eval_split"] == "test" and not m["errors"]
    for f, p in zip(m["inputs"], paths["inputs"]):
        assert f["sha256"] == io.sha256_file(p)
    from gridbench.config import config_hash
    assert m["protocol_config_sha256"] == config_hash()
    runs = pd.read_csv(d / "raw" / "runs_primary.csv")
    n_cells = len(cfg["data"]["authorities"]) * len(cfg["seeds"]) * len(cfg["missingness"]["conditions"])
    per_cell = 2 + len(cfg["methods"]["label_budgets"]) * cfg["label_draws_per_seed"]
    assert len(runs) == n_cells * per_cell


def test_final_raw_outputs_match_recorded_checksums(paths):
    """Every raw output of the final run (result rows, event records, injection ledger, score files)
    and its manifest still match the SHA-256 values recorded when the run was completed (2026-10-22)."""
    d = _results(paths, "final")
    rec = paths["audit"] / "history" / "output_checksums_SHA256_2026-10-22_original_layout.txt"
    n = 0
    for line in rec.read_text().splitlines():
        h, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        if name.startswith("04_RESULTS/final/raw/") or name == "04_RESULTS/final/run_manifest.json":
            assert io.sha256_file(d / name.removeprefix("04_RESULTS/final/")) == h, name
            n += 1
    assert n == 25 + 125 + 1  # 25 CSV files, 125 score files, run manifest


@pytest.mark.parametrize("ba,seed,cond_name", [("NYIS", 23, "mcar15"), ("SWPP", 53, "block5")])
def test_recomputed_cells_match_final(paths, cfg, real_df, ba, seed, cond_name):
    """Re-execute primary cells from the raw EIA files and compare them with the saved final run:
    result rows must be identical (timing columns excluded) and score arrays bitwise identical.
    (The complete 625-cell comparison is scripts/verify_full_reproduction.py.)"""
    import importlib.util
    d = _results(paths, "final")
    spec = importlib.util.spec_from_file_location("run_experiment", paths["code"] / "scripts" / "run_experiment.py")
    rx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rx)
    variant = next(v for v in rx.variants(cfg) if v["name"] == "primary")
    names = [c["name"] for c in cfg["missingness"]["conditions"]]
    ci = names.index(cond_name)
    ctx_ = make_context(real_df, ba, cfg["data"]["authorities"].index(ba), cfg)
    rows, _, _, blob = run_cell(ctx_, seed, ci, cfg["missingness"]["conditions"][ci], cfg, variant, "test",
                                keep_scores=True)
    timing = ["fit_seconds", "eval_seconds"]
    new = pd.DataFrame(rows)
    import io as _io
    buf = _io.StringIO()
    new.to_csv(buf, index=False, float_format="%.10g")  # same serialization as the runner
    new = pd.read_csv(_io.StringIO(buf.getvalue())).drop(columns=timing)
    old = pd.read_csv(d / "raw" / "runs_primary.csv")
    old = old[(old.ba == ba) & (old.seed == seed) & (old.condition == cond_name)].drop(columns=timing)
    assert len(old) == len(new) == 2 + len(cfg["methods"]["label_budgets"]) * cfg["label_draws_per_seed"]
    pd.testing.assert_frame_equal(old.reset_index(drop=True), new.reset_index(drop=True), check_exact=True)
    z = np.load(d / "raw" / "scores" / f"{ba}_s{seed}_{cond_name}.npz", allow_pickle=True)
    assert blob["scores"]
    for k, v in blob["scores"].items():
        assert np.array_equal(z[f"score__{k}"], v, equal_nan=True), k


def test_missingness_independent_of_labels(ctx, cfg):
    """Regression test for the v1.0 leak: with nuisance missingness, the probability
    that the previous hour is missing must not differ between injected and normal hours."""
    from gridbench.experiment import observed
    cond = cfg["missingness"]["conditions"][2]  # mcar15
    rates_pos, rates_neg = [], []
    for seed in cfg["seeds"]:
        events, x_inj, label, owner = injected(ctx, seed, cfg, 6)
        x_obs, miss = observed(ctx, x_inj, owner, seed, 2, cond, cfg)
        prev = np.r_[False, np.isnan(x_obs)[:-1]]
        ok = ~np.isnan(x_obs)
        rates_pos.append(prev[ok & label].mean())
        rates_neg.append(prev[ok & ~label].mean())
        assert (miss & label).any()  # injected hours can be masked (independence)
    assert abs(np.mean(rates_pos) - np.mean(rates_neg)) < 0.05
    assert np.mean(rates_pos) > 0.08


def test_saved_utc_index_matches_source(paths, cfg, real_df):
    d = paths["results"] / "final" / "raw" / "scores"
    f = d / "NYIS_s11_none.npz"
    if not f.exists():
        missing("final scores not present")
    z = np.load(f, allow_pickle=True)
    s = io.build_series(real_df, "NYIS")
    assert np.array_equal(pd.to_datetime(z["utc_index"], unit="s"), s.index)
    np.testing.assert_array_equal(z["x_orig"], s["demand"].to_numpy())
