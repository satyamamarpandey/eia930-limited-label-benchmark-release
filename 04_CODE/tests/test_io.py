"""CSV schema handling, hashing, timestamp parsing, BA identification, duplicates, missingness."""
import hashlib
import json

import numpy as np
import pandas as pd
import pytest
from conftest import missing

from gridbench import io
from conftest import make_eia_csv


def test_schema_required_columns(tiny_csv):
    df = io.read_raw(tiny_csv)
    assert all(c in df.columns for c in io.REQUIRED_COLUMNS)


def test_schema_missing_column_raises(tmp_path):
    p = tmp_path / "bad.csv"
    df = make_eia_csv(p)
    df.drop(columns=[io.DEMAND_COL]).to_csv(p, index=False)
    with pytest.raises(io.SchemaError):
        io.read_raw(p)


def test_html_masquerading_as_csv_rejected(tmp_path):
    p = tmp_path / "page.csv"
    p.write_text("<html><body>error</body></html>")
    with pytest.raises(io.SchemaError):
        io.read_raw(p)


def test_non_numeric_value_raises():
    with pytest.raises(io.SchemaError):
        io.parse_numeric(pd.Series(["1", "abc"]))


def test_blank_is_nan_not_zero_and_commas_parsed():
    out = io.parse_numeric(pd.Series(["", "1,234", "5"]))
    assert np.isnan(out.iloc[0]) and out.iloc[1] == 1234 and out.iloc[2] == 5


def test_sha256_matches_hashlib(tiny_csv):
    assert io.sha256_file(tiny_csv) == hashlib.sha256(tiny_csv.read_bytes()).hexdigest()


def test_utc_parsing_contiguous_across_dst(tiny_csv):
    df = io.load_eia([tiny_csv], ["TEST"])
    d = df["utc_end"].diff().dropna()
    assert (d == pd.Timedelta("1h")).all()
    assert df["utc_end"].iloc[0] == pd.Timestamp("2024-03-09 08:00")


def test_ba_filtering(tmp_path):
    p1 = tmp_path / "a.csv"
    df = make_eia_csv(p1, ba="AAA", hours=10)
    df2 = df.copy()
    df2[io.BA_COL] = "BBB"
    pd.concat([df, df2]).to_csv(p1, index=False)
    out = io.load_eia([p1], ["BBB"])
    assert set(out["ba"]) == {"BBB"} and len(out) == 10


def test_duplicate_and_conflict_detection(tmp_path):
    p = tmp_path / "dup.csv"
    df = make_eia_csv(p, hours=10)
    dup = df.iloc[[3]].copy()
    dup[io.DEMAND_COL] = "1"
    pd.concat([df, dup]).to_csv(p, index=False)
    rep = io.check_integrity(io.load_eia([p], ["TEST"]))["TEST"]
    assert rep["duplicate_utc_rows"] == 2 and rep["conflicting_duplicate_hours"] == 1


def test_missing_hours_detected(tmp_path):
    p = tmp_path / "gap.csv"
    df = make_eia_csv(p, hours=10)
    df.drop(index=4).to_csv(p, index=False)
    rep = io.check_integrity(io.load_eia([p], ["TEST"]))["TEST"]
    assert rep["missing_hours_in_span"] == 1


def test_build_series_invalid_rules(tmp_path):
    p = tmp_path / "z.csv"
    df = make_eia_csv(p, hours=10, blanks=(2,))
    df.loc[5, io.DEMAND_COL] = "0"
    df.to_csv(p, index=False)
    s = io.build_series(io.load_eia([p], ["TEST"]), "TEST")
    assert s["natural_blank"].sum() == 1 and s["natural_nonpositive"].sum() == 1
    assert s["demand"].isna().sum() == 2
    assert (s["demand"].dropna() > 0).all()


def test_natural_suspect_rule():
    x = np.array([10, 11, 12, 12, 12, 13, 14, 5, 14, 15], dtype=float)
    f = io.natural_suspect(x)
    assert f.tolist() == [False, False, False, True, True, False, False, True, False, False]


# ---------------- real-data integration -----------------

def test_real_files_authorities_and_hours(real_df, cfg):
    assert set(real_df["ba"]) == set(cfg["data"]["authorities"])
    rep = io.check_integrity(real_df)
    for ba, r in rep.items():
        assert r["rows"] == 8784
        assert r["duplicate_utc_rows"] == 0 and r["missing_hours_in_span"] == 0


def test_manifest_hashes_match_files(paths):
    man = paths["data"] / "dataset_manifest.json"
    if not man.exists():
        missing("source audit not yet run")
    m = json.loads(man.read_text())
    for f, p in zip(m["files"], paths["inputs"]):
        assert f["sha256"] == io.sha256_file(p)
        assert f["bytes"] == p.stat().st_size
