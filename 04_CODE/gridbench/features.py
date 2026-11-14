"""Causal (past-and-present only) features for hourly demand anomaly scoring.

Every feature at hour t is a function of x_{<=t} only; `tests/test_features.py`
verifies this by perturbing future values. Values are on the log scale so that
features are comparable across authorities of different size.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RESIDUAL_FEATURES = ["rs", "rw", "d1res"]
MISSING_FEATURES = ["miss_lag1", "miss_frac24", "miss_seas"]
BASE_FEATURES = ["d1", "vol24", "stale", "hour_sin", "hour_cos", "weekend"]
ALL_FEATURES = RESIDUAL_FEATURES + BASE_FEATURES + MISSING_FEATURES


def lag(a: np.ndarray, k: int) -> np.ndarray:
    out = np.full_like(a, np.nan, dtype=float)
    if k < len(a):
        out[k:] = a[:-k] if k > 0 else a
    return out


def _nanmedian_stack(arrs: list[np.ndarray]) -> np.ndarray:
    st = np.vstack(arrs)
    allnan = np.isnan(st).all(axis=0)
    st2 = np.where(allnan[None, :], 0.0, st)
    med = np.nanmedian(st2, axis=0)
    med[allnan] = np.nan
    return med


def stale_run(x: np.ndarray, cap: int) -> np.ndarray:
    """Number of consecutive exact repeats ending at t (0 if x_t != x_{t-1})."""
    out = np.zeros(len(x))
    for t in range(1, len(x)):
        if not np.isnan(x[t]) and not np.isnan(x[t - 1]) and x[t] == x[t - 1]:
            out[t] = min(out[t - 1] + 1, cap)
    return out


def compute_features(x: np.ndarray, local_hour: np.ndarray, local_dow: np.ndarray, fcfg: dict) -> pd.DataFrame:
    y = np.log(x)  # NaN stays NaN
    D, W = fcfg["seasonal_days"], fcfg["weekly_lags"]
    seas = _nanmedian_stack([lag(y, 24 * k) for k in range(1, D + 1)])
    week = _nanmedian_stack([lag(y, 168 * k) for k in range(1, W + 1)])
    d1 = y - lag(y, 1)
    d1prof = _nanmedian_stack([lag(d1, 24 * k) for k in range(1, D + 1)])
    vol = pd.Series(d1).rolling(fcfg["vol_window"], min_periods=6).std().to_numpy()
    miss = np.isnan(x).astype(float)
    f = pd.DataFrame({
        "rs": y - seas,
        "rw": y - week,
        "d1res": d1 - d1prof,
        "d1": d1,
        "vol24": vol,
        "stale": stale_run(x, fcfg["stale_cap"]),
        "hour_sin": np.sin(2 * np.pi * local_hour / 24.0),
        "hour_cos": np.cos(2 * np.pi * local_hour / 24.0),
        "weekend": (local_dow >= 5).astype(float),
        "miss_lag1": lag(miss, 1),
        "miss_frac24": pd.Series(lag(miss, 1)).rolling(24, min_periods=1).mean().to_numpy(),
        "miss_seas": np.mean(np.vstack([lag(miss, 24 * k) for k in range(1, D + 1)]), axis=0),
    })
    f.loc[:0, ["miss_lag1"]] = 1.0  # no previous hour exists at series start
    return f[ALL_FEATURES]


def local_calendar(local_end: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Local hour-beginning hour of day (0-23) and day of week from the EIA local
    hour-ending timestamp string."""
    loc = pd.to_datetime(local_end, format="%m/%d/%Y %I:%M:%S %p") - pd.Timedelta(hours=1)
    return loc.dt.hour.to_numpy(), loc.dt.day_of_week.to_numpy()
