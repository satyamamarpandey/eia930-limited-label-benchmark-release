"""Deterministic injection, fault-label correctness, non-overlap, missingness separation."""
import numpy as np
import pytest

from gridbench import inject


def _split_pos(n):
    a, b = n // 2, 3 * n // 4
    return {"train": (0, a - 1), "val": (a, b - 1), "test": (b, n - 1)}


def _place(cfg, x, seed, epf=None):
    rng = inject.make_rng(seed, 0, inject.STREAM_EVENTS)
    return inject.place_events(~np.isnan(x), _split_pos(len(x)), cfg["injection"],
                               epf or {"train": 2, "val": 1, "test": 1}, rng)


@pytest.fixture
def long_series():
    t = np.arange(24 * 240)
    return 1000 * (1 + 0.2 * np.sin(2 * np.pi * t / 24)) + t * 0.01


def test_injection_deterministic(cfg, long_series):
    e1 = _place(cfg, long_series, 11)
    e2 = _place(cfg, long_series, 11)
    e3 = _place(cfg, long_series, 23)
    assert [(e.start, e.family, e.severity, e.sign) for e in e1] == [(e.start, e.family, e.severity, e.sign) for e in e2]
    assert [e.start for e in e1] != [e.start for e in e3]
    x1, l1, _ = inject.apply_events(long_series, e1)
    x2, l2, _ = inject.apply_events(long_series, e2)
    assert np.array_equal(x1, x2) and np.array_equal(l1, l2)


def test_events_within_split_nonoverlapping_with_gap(cfg, long_series):
    ev = _place(cfg, long_series, 37)
    sp = _split_pos(len(long_series))
    gap = cfg["injection"]["min_gap_hours"]
    buf = cfg["injection"]["boundary_buffer_hours"]
    for e in ev:
        lo, hi = sp[e.split]
        assert lo + buf <= e.start and e.start + e.length - 1 <= hi - buf
    ev = sorted(ev, key=lambda e: e.start)
    for a, b in zip(ev, ev[1:]):
        assert b.start - (a.start + a.length) >= gap


def test_family_and_tier_counts(cfg, long_series):
    ev = _place(cfg, long_series, 41, {"train": 3, "val": 1, "test": 3})
    for split, n in {"train": 3, "val": 1, "test": 3}.items():
        for fam in inject.FAMILIES:
            sub = [e for e in ev if e.split == split and e.family == fam]
            assert len(sub) == n
            if n == 3:
                assert sorted(e.tier for e in sub) == sorted(inject.TIERS)


def test_fault_mechanics_and_labels(long_series):
    x = long_series
    E = inject.Event
    evs = [E(0, "test", "spike", "high", 0.2, 1, 100, 1),
           E(1, "test", "level_shift", "low", 0.03, -1, 200, 6),
           E(2, "test", "drift", "medium", 0.1, 1, 300, 10),
           E(3, "test", "flatline", "low", 4.0, 1, 400, 4),
           E(4, "test", "timing", "medium", 2.0, 1, 500, 6),
           E(5, "test", "timing", "low", 1.0, -1, 600, 6)]
    xi, lab, own = inject.apply_events(x, evs)
    assert np.isclose(xi[100], x[100] * 1.2)
    assert np.allclose(xi[200:206], x[200:206] * 0.97)
    assert np.isclose(xi[309], x[309] * 1.1) and np.isclose(xi[300], x[300] * (1 + 0.1 / 10))
    assert np.all(xi[400:404] == x[399])
    assert np.array_equal(xi[500:506], x[498:504])
    assert np.array_equal(xi[600:606], x[601:607])
    assert np.array_equal(lab, xi != x)            # label iff altered
    assert set(np.unique(own[lab])) == {0, 1, 2, 3, 4, 5}
    assert (own[~np.isin(np.arange(len(x)), np.concatenate([np.arange(e.start, e.start + e.length) for e in evs]))] == -1).all()
    untouched = np.ones(len(x), bool)
    for e in evs:
        untouched[e.start:e.start + e.length] = False
    assert np.array_equal(xi[untouched], x[untouched])


def test_injection_never_on_invalid_hours(cfg, long_series):
    x = long_series.copy()
    x[np.arange(0, len(x), 97)] = np.nan
    ev = _place(cfg, x, 53)
    for e in ev:
        assert not np.isnan(x[e.start:e.start + e.length]).any()


@pytest.mark.parametrize("mech", ["mcar", "block"])
def test_missingness_rate_and_separation(mech):
    n = 5000
    valid = np.ones(n, bool)
    valid[:10] = False
    prot = np.zeros(n, bool)
    prot[1000:1100] = True
    m = inject.background_missingness(valid, prot, 0.15, mech, (3, 12), inject.make_rng(1, 2, 3))
    elig = valid & ~prot
    assert m.sum() == round(0.15 * elig.sum())
    assert not (m & prot).any() and not (m & ~valid).any()
    m2 = inject.background_missingness(valid, prot, 0.15, mech, (3, 12), inject.make_rng(1, 2, 3))
    assert np.array_equal(m, m2)


def test_no_missingness_condition():
    m = inject.background_missingness(np.ones(100, bool), np.zeros(100, bool), 0.0, "none", (3, 12),
                                      inject.make_rng(0))
    assert not m.any()
