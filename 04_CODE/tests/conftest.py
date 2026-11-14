import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))

from gridbench import io  # noqa: E402
from gridbench.config import load_config, project_paths  # noqa: E402


def missing(reason: str):
    """Skip a test whose inputs are absent (e.g. the review archive without the EIA CSVs).
    With GRIDBENCH_REQUIRE_ALL=1 (set by 07_REPRODUCTION/run_tests.ps1) a missing input is a failure."""
    if os.environ.get("GRIDBENCH_REQUIRE_ALL") == "1":
        pytest.fail(f"required input missing: {reason}")
    pytest.skip(reason)


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def paths(cfg):
    return project_paths(cfg)


def make_eia_csv(path: Path, ba="TEST", start_utc="2024-03-09 08:00", hours=72, offset_std=-8, blanks=(),
                 extra_rows=None):
    """Write a small file in the EIA-930 BALANCE layout (all required columns)."""
    utc = pd.date_range(start_utc, periods=hours, freq="h")
    rows = []
    for i, t in enumerate(utc):
        # US Pacific-like DST: 2024-03-10 10:00 UTC switch
        off = offset_std + (1 if t >= pd.Timestamp("2024-03-10 10:00") else 0)
        loc = t + pd.Timedelta(hours=off)
        dem = "" if i in blanks else str(1000 + 100 * np.sin(2 * np.pi * i / 24))
        rows.append({io.BA_COL: ba, io.DATE_COL: (loc - pd.Timedelta(hours=1)).strftime("%m/%d/%Y"),
                     io.HOUR_COL: str(((loc - pd.Timedelta(hours=1)).hour) + 1),
                     io.LOCAL_COL: loc.strftime("%m/%d/%Y %I:%M:%S %p").lstrip("0"),
                     io.UTC_COL: t.strftime("%m/%d/%Y %I:%M:%S %p"),
                     io.FORECAST_COL: "1000", io.DEMAND_COL: dem, io.NETGEN_COL: "990",
                     io.DEMAND_IMPUTED_COL: "", io.DEMAND_ADJUSTED_COL: dem})
    df = pd.DataFrame(rows)
    if extra_rows is not None:
        df = pd.concat([df, pd.DataFrame(extra_rows)], ignore_index=True)
    df.to_csv(path, index=False)
    return df


@pytest.fixture
def tiny_csv(tmp_path):
    p = tmp_path / "tiny.csv"
    make_eia_csv(p, blanks=(5,))
    return p


@pytest.fixture(scope="session")
def real_df(cfg, paths):
    if not all(p.exists() for p in paths["inputs"]):
        missing("EIA input files not available")
    return io.load_eia(paths["inputs"], cfg["data"]["authorities"])


@pytest.fixture
def synth_series():
    """Deterministic demand-like series for unit tests (not used for any result)."""
    t = np.arange(24 * 60)
    x = 1000 * (1 + 0.2 * np.sin(2 * np.pi * t / 24) + 0.05 * np.sin(2 * np.pi * t / 168))
    return x.astype(float)
