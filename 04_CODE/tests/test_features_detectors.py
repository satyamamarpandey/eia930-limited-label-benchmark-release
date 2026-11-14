"""Leakage prevention (causal features, train-only fitting), model fit behaviour, label budget accounting."""
import numpy as np
import pandas as pd
import pytest

from gridbench import features as feat
from gridbench import inject
from gridbench.detectors import (IForestDetector, PULogisticDetector, RobustSeasonalDetector,
                                 sample_label_budget)


def _cal(n):
    h = np.arange(n) % 24
    d = (np.arange(n) // 24) % 7
    return h, d


def test_features_are_causal(cfg, synth_series):
    x = synth_series.copy()
    h, d = _cal(len(x))
    F1 = feat.compute_features(x, h, d, cfg["features"])
    t = 900
    x2 = x.copy()
    x2[t + 1:] = x2[t + 1:] * 3.0 + 17.0
    x2[t + 5:t + 9] = np.nan
    F2 = feat.compute_features(x2, h, d, cfg["features"])
    pd.testing.assert_frame_equal(F1.iloc[:t + 1], F2.iloc[:t + 1])


def test_features_nan_handling(cfg, synth_series):
    x = synth_series.copy()
    x[500] = np.nan
    h, d = _cal(len(x))
    F = feat.compute_features(x, h, d, cfg["features"])
    assert np.isnan(F.loc[500, "rs"]) and F.loc[501, "miss_lag1"] == 1.0
    assert F.loc[600, "miss_lag1"] == 0.0
    assert set(F.columns) == set(feat.ALL_FEATURES)


def test_stale_run_feature():
    x = np.array([1, 2, 2, 2, 3, np.nan, 3, 3], dtype=float)
    assert feat.stale_run(x, 24).tolist() == [0, 0, 1, 2, 0, 0, 0, 1]


def _frame(n=3000, seed=0):
    r = np.random.default_rng(seed)
    return pd.DataFrame(r.normal(size=(n, len(feat.ALL_FEATURES))), columns=feat.ALL_FEATURES)


def test_stat_detector_robust_and_nan_safe():
    F = _frame()
    det = RobustSeasonalDetector(("seasonal", "diff")).fit(F)
    G = F.copy()
    G.loc[0, "rs"] = 50.0
    G.loc[1, ["rs", "d1res"]] = np.nan
    s = det.score(G)
    assert s[0] > 20 and s[1] == 0.0 and np.isfinite(s).all()


def test_detectors_use_only_training_rows():
    F = _frame()
    tr = F.iloc[:2000].reset_index(drop=True)
    for mk in (lambda: IForestDetector(feat.ALL_FEATURES, 50, 256, 1.0, random_state=0),
               lambda: RobustSeasonalDetector()):
        a = mk().fit(tr)
        F2 = F.copy()
        F2.iloc[2000:] = 99.0  # arbitrary future/test values
        b = mk().fit(F2.iloc[:2000].reset_index(drop=True))
        assert np.allclose(a.score(F.iloc[:2000]), b.score(F.iloc[:2000]))


def test_iforest_deterministic():
    F = _frame()
    s1 = IForestDetector(feat.ALL_FEATURES, 50, 256, 1.0, random_state=7).fit(F).score(F)
    s2 = IForestDetector(feat.ALL_FEATURES, 50, 256, 1.0, random_state=7).fit(F).score(F)
    assert np.array_equal(s1, s2)


def _labels(n=2000):
    label = np.zeros(n, bool)
    owner = np.full(n, -1)
    for k, st in enumerate(range(100, 1900, 150)):
        owner[st:st + 8] = k
        label[st:st + 8] = True
        label[st] = False  # an unaltered hour inside an event window
    return label, owner


@pytest.mark.parametrize("B", [8, 32, 128])
def test_label_budget_accounting(B):
    label, owner = _labels()
    train_rows = np.arange(0, 1500)
    pos, neg, unl = sample_label_budget(B, label, owner, train_rows, inject.make_rng(1, B))
    assert len(pos) + len(neg) == B and len(pos) == B // 2
    assert label[train_rows[pos]].all()
    assert (~label[train_rows[neg]]).all() and (owner[train_rows[neg]] == -1).all()
    assert len(set(pos) | set(neg) | set(unl)) == len(train_rows)
    assert not (set(pos) & set(unl)) and not (set(neg) & set(unl))
    assert train_rows[pos].max() < 1500   # never from val/test rows
    if B == 8:
        assert len(set(owner[train_rows[pos]])) == 4  # spread over distinct events


def test_label_budget_family_exclusion():
    label, owner = _labels()
    fam = {k: ("spike" if k % 2 else "drift") for k in range(20)}
    pos, _, _ = sample_label_budget(16, label, owner, np.arange(2000), inject.make_rng(3),
                                    exclude_families=["spike"], event_family=fam)
    assert all(fam[owner[p]] == "drift" for p in pos)


def test_pu_weights_and_scores_finite():
    F = _frame()
    label, owner = _labels(len(F))
    F.loc[label, "rs"] += 3.0
    pos, neg, unl = sample_label_budget(32, label, owner, np.arange(len(F)), inject.make_rng(0))
    det = PULogisticDetector(feat.ALL_FEATURES).fit(F, pos, neg, unl)
    s = det.score(F)
    assert np.isfinite(s).all()
    assert s[label].mean() > s[~label].mean()
    det0 = PULogisticDetector(feat.ALL_FEATURES, unlabeled_weight_share=0.0).fit(F, pos, neg, unl)
    assert np.isfinite(det0.score(F)).all()
