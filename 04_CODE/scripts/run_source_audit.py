"""Phase 1: source validation of the two EIA-930 BALANCE 2024 files.

Writes the dataset manifest, checksums and data-quality report to 03_DATA.
Usage: python scripts/run_source_audit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
from gridbench import io  # noqa: E402
from gridbench.config import load_config, project_paths  # noqa: E402


def runs_of_true(mask: pd.Series) -> list[tuple[str, str, int]]:
    out = []
    m = mask.values.astype(bool)
    i = 0
    while i < len(m):
        if m[i]:
            j = i
            while j + 1 < len(m) and m[j + 1]:
                j += 1
            out.append((str(mask.index[i]), str(mask.index[j]), j - i + 1))
            i = j + 1
        else:
            i += 1
    return out


def main() -> None:
    cfg = load_config()
    paths = project_paths(cfg)
    outdir = paths["data"]
    outdir.mkdir(parents=True, exist_ok=True)
    bas = cfg["data"]["authorities"]

    files = []
    raw_frames = []
    for p in paths["inputs"]:
        raw = io.read_raw(p)
        raw_frames.append(raw)
        dates = pd.to_datetime(raw[io.DATE_COL], format="%m/%d/%Y")
        utc = pd.to_datetime(raw[io.UTC_COL], format=io.TS_FORMAT)
        per_ba = raw.groupby(io.BA_COL).size()
        tgt = raw[raw[io.BA_COL].isin(bas)]
        hours_per_day = tgt.groupby([io.BA_COL, io.DATE_COL]).size()
        odd_days = hours_per_day[hours_per_day != 24].reset_index().rename(columns={0: "local_hours"})
        files.append({
            "file": p.name,
            "path_relative_to_root": str(p.relative_to(paths["root"])).replace("\\", "/"),
            "bytes": p.stat().st_size,
            "sha256": io.sha256_file(p),
            "encoding": "ASCII (UTF-8 compatible); comma-delimited; double-quoted header; 1 header row",
            "rows": int(len(raw)),
            "columns": int(raw.shape[1]),
            "n_balancing_authorities": int(raw[io.BA_COL].nunique()),
            "data_date_min": str(dates.min().date()),
            "data_date_max": str(dates.max().date()),
            "utc_end_min": str(utc.min()),
            "utc_end_max": str(utc.max()),
            "rows_per_target_ba": {b: int(per_ba.get(b, 0)) for b in bas},
            "target_ba_local_days_not_24h": odd_days.to_dict(orient="records"),
        })
    col_a, col_b = set(raw_frames[0].columns), set(raw_frames[1].columns)
    schema = {
        "common_columns": len(col_a & col_b),
        "only_in_" + files[0]["file"]: sorted(col_a - col_b),
        "only_in_" + files[1]["file"]: sorted(col_b - col_a),
        "required_columns_present_in_both": all(c in col_a and c in col_b for c in io.REQUIRED_COLUMNS),
    }

    df = io.load_eia(paths["inputs"], bas)
    integ = io.check_integrity(df)

    # timestamp convention check: UTC - local offset per BA (hour-ending in both)
    offsets = {}
    for ba, g in df.groupby("ba"):
        loc = pd.to_datetime(g["local_end"], format=io.TS_FORMAT)
        off = (loc.values - g["utc_end"].values) / np.timedelta64(1, "h")
        offsets[ba] = {str(int(k)): int(v) for k, v in pd.Series(off).value_counts().sort_index().items()}

    splits = cfg["splits"]
    natural = {}
    for ba in bas:
        s = io.build_series(df, ba)
        x = s["demand"]
        rep = (x == x.shift(1)) & x.notna()
        natural[ba] = {"exact_repeat_hours": int(rep.sum()),
                       "exact_repeat_runs": int((rep & ~rep.shift(1, fill_value=False)).sum()),
                       "natural_suspect_hours": int(s["natural_suspect"].sum())}
        for name, (lo, hi) in splits.items():
            m = (s.index >= pd.Timestamp(lo)) & (s.index <= pd.Timestamp(hi))
            natural[ba][f"natural_suspect_{name}"] = int(s.loc[m, "natural_suspect"].sum())
            natural[ba][f"exact_repeat_{name}"] = int(rep[m].sum())
    split_rows = {}
    natural_runs = {}
    for ba in bas:
        s = io.build_series(df, ba)
        natural_runs[ba] = [
            {"first_utc_end": a, "last_utc_end": b, "hours": n}
            for a, b, n in runs_of_true(s["natural_invalid"])
        ]
        nonpos = s.index[s["natural_nonpositive"]]
        natural_runs[ba + "_nonpositive_hours"] = [str(t) for t in nonpos]
        split_rows[ba] = {}
        for name, (lo, hi) in splits.items():
            m = (s.index >= pd.Timestamp(lo)) & (s.index <= pd.Timestamp(hi))
            split_rows[ba][name] = {
                "hours": int(m.sum()),
                "natural_invalid": int(s.loc[m, "natural_invalid"].sum()),
                "valid_fraction": round(float(1 - s.loc[m, "natural_invalid"].mean()), 6),
            }

    manifest = {
        "source": "U.S. Energy Information Administration, Form EIA-930 Hourly Electric Grid Monitor, "
                  "BALANCE six-month files for 2024",
        "documentation": "https://www.eia.gov/electricity/930-content/about.html",
        "files": files,
        "schema_comparison": schema,
        "target_authorities": bas,
        "authority_codes_verified_present": {b: bool((df["ba"] == b).any()) for b in bas},
        "time_index": "UTC Time at End of Hour (hour-ending, UTC)",
        "utc_minus_local_offset_hours_counts": offsets,
        "integrity": integ,
        "split_coverage": split_rows,
        "natural": natural,
        "inclusion_rules": cfg["data"]["inclusion_rules"],
    }
    (outdir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    (outdir / "natural_invalid_runs.json").write_text(json.dumps(natural_runs, indent=2))
    with open(outdir / "SHA256SUMS.txt", "w", newline="\n") as fh:  # LF for sha256sum -c
        for f in files:
            fh.write(f"{f['sha256']}  raw/{f['file']}\n")  # relative to 03_DATA

    # human-readable report
    L = ["# Source data validation and quality report", "",
         "Generated by `04_CODE/scripts/run_source_audit.py`. All numbers computed from the files.", "",
         "## Files", "", "| File | Bytes | Rows | Cols | BAs | Data dates | SHA-256 |", "|---|---|---|---|---|---|---|"]
    for f in files:
        L.append(f"| {f['file']} | {f['bytes']:,} | {f['rows']:,} | {f['columns']} | {f['n_balancing_authorities']} | "
                 f"{f['data_date_min']} to {f['data_date_max']} | `{f['sha256']}` |")
    L += ["", f"Encoding: {files[0]['encoding']}.", "",
          f"Schema: {schema['common_columns']} common columns. The Jul-Dec file adds "
          f"{len(schema['only_in_' + files[1]['file']])} generation-by-energy-source columns (battery, geothermal, "
          "storage subtypes); the Jan-Jun file has "
          f"{len(schema['only_in_' + files[0]['file']])} columns absent from Jul-Dec. All analysis columns are in both.", "",
          "## Rows per target authority and local-day structure", "",
          "Rows are keyed by local `Data Date` and `Hour Number`. Days with != 24 local hours (DST transitions):", ""]
    for f in files:
        L.append(f"* {f['file']}: rows per BA {f['rows_per_target_ba']}; non-24h local days: "
                 + "; ".join(f"{r[io.BA_COL]} {r[io.DATE_COL]} ({r['local_hours']} h)" for r in f["target_ba_local_days_not_24h"]))
    L += ["", "Hour-ending UTC timestamps are unique and contiguous; local time repeats/skips at DST, so UTC is the "
          "canonical index. UTC minus local offsets (hours: count):", ""]
    for b, o in offsets.items():
        L.append(f"* {b}: {o}")
    L += ["", "## Integrity per authority (full 2024 span)", "",
          "| BA | Rows | UTC first (end) | UTC last (end) | Dup rows | Missing hours | Demand blank | Demand <= 0 | "
          "EIA imputed demand | Adjusted != reported | Demand min / median / max (MW) |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for b, r in integ.items():
        L.append(f"| {b} | {r['rows']} | {r['utc_end_first']} | {r['utc_end_last']} | {r['duplicate_utc_rows']} | "
                 f"{r['missing_hours_in_span']} | {r['demand_blank']} | {r['demand_nonpositive']} | "
                 f"{r['demand_imputed_nonblank']} | {r['adjusted_differs_from_reported']} | "
                 f"{r['demand_min']:.0f} / {r['demand_median']:.0f} / {r['demand_max']:.0f} |")
    L += ["", "## Natural invalid runs (blank or non-positive reported demand)", ""]
    for b in bas:
        runs = natural_runs[b]
        L.append(f"* {b}: {len(runs)} runs, {sum(r['hours'] for r in runs)} hours"
                 + (": " + "; ".join(f"{r['first_utc_end']}..{r['last_utc_end']} ({r['hours']} h)" for r in runs) if runs else ""))
        if natural_runs[b + "_nonpositive_hours"]:
            L.append(f"  * non-positive (0 MW) hours: {', '.join(natural_runs[b + '_nonpositive_hours'])}")
    L += ["", "## Naturally repeated values and natural-suspect hours (audit flag; not detector input)", "",
          "| BA | Exact repeat hours | Repeat runs | Suspect hours | Suspect train / val / test | Repeats train / val / test |",
          "|---|---|---|---|---|---|"]
    for b in bas:
        n = natural[b]
        L.append(f"| {b} | {n['exact_repeat_hours']} | {n['exact_repeat_runs']} | {n['natural_suspect_hours']} | "
                 f"{n['natural_suspect_train']} / {n['natural_suspect_val']} / {n['natural_suspect_test']} | "
                 f"{n['exact_repeat_train']} / {n['exact_repeat_val']} / {n['exact_repeat_test']} |")
    L += ["", "## Split coverage (hour-ending UTC, inclusive bounds)", "",
          "| BA | " + " | ".join(f"{k} hours / invalid" for k in splits) + " |", "|---|" + "---|" * len(splits)]
    for b in bas:
        L.append(f"| {b} | " + " | ".join(f"{split_rows[b][k]['hours']} / {split_rows[b][k]['natural_invalid']}" for k in splits) + " |")
    L += ["", "## Inclusion and exclusion rules", ""] + [f"* {r}" for r in cfg["data"]["inclusion_rules"]]
    thr = cfg["data"]["min_valid_fraction_per_split"]
    worst = min(((split_rows[b][k]["valid_fraction"], b, k) for b in bas for k in splits))
    ok = worst[0] >= thr
    L += ["", "## Sufficiency", "",
          f"Protocol minimum valid fraction per authority and split: {thr:.0%}. Lowest observed: "
          f"{worst[0]:.2%} ({worst[1]}, {worst[2]}). "
          + ("PASS: no authority was excluded." if ok else "FAIL: see table; authority must be excluded.")]
    manifest["sufficiency"] = {"threshold": thr, "lowest": {"fraction": worst[0], "ba": worst[1], "split": worst[2]},
                               "pass": ok}
    (outdir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    (outdir / "data_quality_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
