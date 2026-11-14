"""Loading and schema validation of EIA-930 BALANCE six-month CSV files.

Conventions (verified against the files and EIA documentation):
* Each row is one balancing authority (BA) and one hour, keyed by local date and
  hour number; the "UTC Time at End of Hour" column gives the hour-ending UTC
  timestamp, which is used as the canonical time index (it has no DST ambiguity).
* Numeric fields may be blank. Blank is kept as NaN; it is never replaced by 0.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

BA_COL = "Balancing Authority"
UTC_COL = "UTC Time at End of Hour"
LOCAL_COL = "Local Time at End of Hour"
DATE_COL = "Data Date"
HOUR_COL = "Hour Number"
DEMAND_COL = "Demand (MW)"
FORECAST_COL = "Demand Forecast (MW)"
NETGEN_COL = "Net Generation (MW)"
DEMAND_IMPUTED_COL = "Demand (MW) (Imputed)"
DEMAND_ADJUSTED_COL = "Demand (MW) (Adjusted)"

REQUIRED_COLUMNS = [BA_COL, DATE_COL, HOUR_COL, LOCAL_COL, UTC_COL, FORECAST_COL,
                    DEMAND_COL, NETGEN_COL, DEMAND_IMPUTED_COL, DEMAND_ADJUSTED_COL]
TS_FORMAT = "%m/%d/%Y %I:%M:%S %p"

NUMERIC_MAP = {
    DEMAND_COL: "demand",
    FORECAST_COL: "forecast",
    NETGEN_COL: "netgen",
    DEMAND_IMPUTED_COL: "demand_imputed",
    DEMAND_ADJUSTED_COL: "demand_adjusted",
}


class SchemaError(ValueError):
    pass


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def read_raw(path: str | Path) -> pd.DataFrame:
    """Read one EIA-930 BALANCE CSV as strings (no implicit NA conversion)."""
    with open(path, "rb") as fh:
        head = fh.read(4096)
    if head.lstrip().startswith(b"<"):
        raise SchemaError(f"{path} looks like HTML, not CSV")
    head.decode("ascii")  # raises if encoding is not plain ASCII/UTF-8 compatible
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"{path} missing required columns: {missing}")
    return df


def parse_numeric(s: pd.Series) -> pd.Series:
    """Parse numeric strings; blanks -> NaN; thousands separators removed.

    Raises if a non-blank value is not numeric (we do not silently coerce)."""
    s2 = s.str.replace(",", "", regex=False).str.strip()
    out = pd.to_numeric(s2.where(s2 != "", None), errors="coerce")
    bad = out.isna() & (s2 != "")
    if bad.any():
        raise SchemaError(f"non-numeric values: {s2[bad].unique()[:5]}")
    return out.astype(float)


def tidy(df: pd.DataFrame, bas: list[str] | None = None) -> pd.DataFrame:
    """Convert raw string frame into a typed frame indexed by (ba, utc_end)."""
    if bas is not None:
        df = df[df[BA_COL].isin(bas)]
    out = pd.DataFrame({
        "ba": df[BA_COL].values,
        "utc_end": pd.to_datetime(df[UTC_COL], format=TS_FORMAT).values,
        "local_end": df[LOCAL_COL].values,
        "data_date": df[DATE_COL].values,
        "hour_number": pd.to_numeric(df[HOUR_COL]).values,
    })
    for src, dst in NUMERIC_MAP.items():
        out[dst] = parse_numeric(df[src]).values
    return out


def load_eia(paths: list[str | Path], bas: list[str]) -> pd.DataFrame:
    """Load, concatenate and sort several BALANCE files for the given BAs."""
    frames = []
    for p in paths:
        t = tidy(read_raw(p), bas)
        t["source_file"] = Path(p).name
        frames.append(t)
    df = pd.concat(frames, ignore_index=True).sort_values(["ba", "utc_end"]).reset_index(drop=True)
    return df


def check_integrity(df: pd.DataFrame) -> dict:
    """Per-BA integrity statistics on the hour-ending UTC index."""
    rep = {}
    for ba, g in df.groupby("ba"):
        dup = g["utc_end"].duplicated(keep=False)
        conflicting = 0
        if dup.any():
            conflicting = int(g[dup].groupby("utc_end")["demand"].nunique(dropna=False).gt(1).sum())
        u = g["utc_end"].drop_duplicates().sort_values()
        full = pd.date_range(u.min(), u.max(), freq="h")
        rep[ba] = {
            "rows": int(len(g)),
            "utc_end_first": str(u.min()),
            "utc_end_last": str(u.max()),
            "expected_hours_in_span": int(len(full)),
            "duplicate_utc_rows": int(dup.sum()),
            "conflicting_duplicate_hours": conflicting,
            "missing_hours_in_span": int(len(full.difference(pd.DatetimeIndex(u)))),
            "demand_blank": int(g["demand"].isna().sum()),
            "demand_nonpositive": int((g["demand"] <= 0).sum()),
            "forecast_blank": int(g["forecast"].isna().sum()),
            "netgen_blank": int(g["netgen"].isna().sum()),
            "demand_imputed_nonblank": int(g["demand_imputed"].notna().sum()),
            "demand_adjusted_blank": int(g["demand_adjusted"].isna().sum()),
            "adjusted_differs_from_reported": int(((g["demand_adjusted"] != g["demand"]) & g["demand"].notna()
                                                   & g["demand_adjusted"].notna()).sum()),
            "demand_min": float(np.nanmin(g["demand"])),
            "demand_median": float(np.nanmedian(g["demand"])),
            "demand_max": float(np.nanmax(g["demand"])),
        }
    return rep


def build_series(df: pd.DataFrame, ba: str) -> pd.DataFrame:
    """Return the hourly UTC series for one BA with the analysis demand column.

    Inclusion rule: reported demand ('Demand (MW)') is used as-is.
    Exclusion rule: blank values and non-positive values (physically invalid for a
    BA's aggregate demand) are set to NaN and flagged `natural_invalid`; they are
    never scored and never used as injection sites. Extreme but positive values
    are retained."""
    g = df[df["ba"] == ba].drop_duplicates("utc_end").set_index("utc_end").sort_index()
    idx = pd.date_range(g.index.min(), g.index.max(), freq="h", name="utc_end")
    g = g.reindex(idx)
    s = pd.DataFrame(index=idx)
    s["demand_reported"] = g["demand"]
    s["natural_blank"] = g["demand"].isna()
    s["natural_nonpositive"] = g["demand"] <= 0
    s["natural_invalid"] = s["natural_blank"] | s["natural_nonpositive"]
    s["demand"] = g["demand"].where(~s["natural_invalid"])
    s["local_end"] = g["local_end"]
    s["natural_suspect"] = natural_suspect(s["demand"].to_numpy(dtype=float))
    return s


def natural_suspect(x: np.ndarray, min_run: int = 3, jump: float = 0.2) -> np.ndarray:
    """Label-free audit flag for *naturally occurring* suspicious reported values.

    Used only to define an evaluation sensitivity analysis (never a detector input):
    (a) every repeat hour in a run of >= `min_run` identical consecutive values;
    (b) isolated reversals: |dlog x_t| > jump and |dlog x_{t+1}| > jump with opposite
        signs (this uses x_{t+1}, acceptable because it is not available to detectors)."""
    n = len(x)
    flag = np.zeros(n, dtype=bool)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and not np.isnan(x[i]) and x[j + 1] == x[i]:
            j += 1
        if j - i + 1 >= min_run:
            flag[i + 1:j + 1] = True
        i = j + 1
    with np.errstate(invalid="ignore", divide="ignore"):
        d = np.diff(np.log(x), prepend=np.nan)
    d_next = np.append(d[1:], np.nan)
    flag |= (np.abs(d) > jump) & (np.abs(d_next) > jump) & (np.sign(d) != np.sign(d_next))
    return flag
