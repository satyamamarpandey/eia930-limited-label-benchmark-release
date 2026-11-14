"""Metric calculations, undefined-metric behaviour, validation-only thresholds."""
import numpy as np
import pytest

from gridbench import metrics
from gridbench.experiment import evaluate_scores
from gridbench.inject import Event


def test_ap_hand_computed():
    y = np.array([1, 0, 1, 0, 0], bool)
    s = np.array([0.9, 0.8, 0.7, 0.2, 0.1])
    # precision at recall steps: 1/1, 2/3 -> AP = 0.5*1 + 0.5*2/3
    r = metrics.ranking_metrics(s, y, 0.01)
    assert r["ap"] == pytest.approx(0.5 + 1 / 3)
    assert r["auroc"] == pytest.approx(5 / 6)
    assert r["prevalence"] == pytest.approx(0.4)


def test_tpr_at_fpr():
    y = np.array([1] * 10 + [0] * 100, bool)
    s = np.concatenate([np.linspace(5, 6, 10), np.linspace(0, 1, 100)])
    s[0] = 0.5  # one positive below most negatives
    r = metrics.ranking_metrics(s, y, 0.01)
    assert r["tpr_at_fpr"] == pytest.approx(0.9)


def test_undefined_metrics_are_nan():
    r = metrics.ranking_metrics(np.array([0.1, 0.2]), np.array([False, False]), 0.01)
    assert np.isnan(r["ap"]) and np.isnan(r["auroc"])
    om = metrics.operating_metrics(np.array([0.1, 0.2]), np.array([True, False]), thr=1.0, hours=168)
    assert np.isnan(om["precision"]) and om["recall"] == 0 and om["f1"] == 0
    om2 = metrics.operating_metrics(np.array([0.1, 0.2]), np.array([False, False]), thr=0.15, hours=168)
    assert np.isnan(om2["recall"]) and np.isnan(om2["f1"]) and om2["false_alerts_per_week"] == 1.0


def test_operating_counts():
    y = np.array([1, 1, 0, 0, 0, 0], bool)
    s = np.array([5, 1, 4, 0, 0, 0], float)
    om = metrics.operating_metrics(s, y, thr=3, hours=336)
    assert (om["tp"], om["fp"], om["fn"]) == (1, 1, 1)
    assert om["precision"] == 0.5 and om["recall"] == 0.5 and om["f1"] == 0.5
    assert om["false_alerts_per_week"] == pytest.approx(0.5)


def test_label_free_threshold_quantile():
    v = np.arange(1, 101, dtype=float)
    assert metrics.label_free_threshold(v, 0.02) == 99.0


def test_event_metrics_delay():
    s = np.zeros(50)
    lab = np.zeros(50, bool)
    lab[10:15] = True
    s[12] = 9
    ev = [Event(0, "test", "level_shift", "low", 0.03, 1, 10, 5)]
    r = metrics.event_metrics(s, lab, np.ones(50, bool), ev, thr=5)[0]
    assert r["detected"] == 1.0 and r["delay_h"] == 2.0


def test_threshold_uses_validation_scores_only(cfg):
    n = 400
    split = np.array(["train"] * 100 + ["val"] * 150 + ["test"] * 150, dtype=object)
    r = np.random.default_rng(0)
    s = r.normal(size=n)
    label = np.zeros(n, bool)
    label[300:310] = True
    fam = np.where(label, "spike", "").astype(object)
    tier = np.where(label, "low", "").astype(object)
    ev = [Event(0, "test", "spike", "low", 0.05, 1, 300, 10)]
    a = evaluate_scores(s, label, np.ones(n, bool), split, ev, fam, tier, cfg, "test")
    s2 = s.copy()
    s2[250:] = r.normal(size=150) * 10  # change test scores
    b = evaluate_scores(s2, label, np.ones(n, bool), split, ev, fam, tier, cfg, "test")
    assert a["threshold"] == b["threshold"]
    s3 = s.copy()
    s3[100:250] += 5  # change validation scores
    c = evaluate_scores(s3, label, np.ones(n, bool), split, ev, fam, tier, cfg, "test")
    assert c["threshold"] != a["threshold"]
