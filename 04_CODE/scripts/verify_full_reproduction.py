"""Compare a complete 625-cell re-execution with the original final run, file by file.

Usage: python scripts/verify_full_reproduction.py [--repro 05_RESULTS/_reproduction_run]
Writes 06_AUDIT/reproducibility/full_reproduction_report.{md,json}. Wall-clock timing columns are excluded;
every other column must agree (rtol 1e-9, atol 1e-12), and score arrays must be bitwise identical.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
from gridbench.config import load_config, project_paths  # noqa: E402

TIMING = ["fit_seconds", "eval_seconds"]
RTOL, ATOL = 1e-9, 1e-12


def compare_frames(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    """Tolerance comparison of two result tables (timing columns excluded)."""
    a, b = a.drop(columns=TIMING, errors="ignore"), b.drop(columns=TIMING, errors="ignore")
    res = {"rows_a": len(a), "rows_b": len(b), "same_columns": list(a.columns) == list(b.columns)}
    if len(a) != len(b) or not res["same_columns"]:
        res["match"] = False
        return res
    num = [c for c in a.columns if a[c].dtype.kind in "fiu"]
    oth = [c for c in a.columns if c not in num]
    max_abs = 0.0
    ok = True
    for c in num:
        x, y = a[c].to_numpy(float), b[c].to_numpy(float)
        same_nan = np.array_equal(np.isnan(x), np.isnan(y))
        m = ~np.isnan(x)
        d = float(np.max(np.abs(x[m] - y[m]))) if m.any() else 0.0
        max_abs = max(max_abs, d)
        ok &= same_nan and np.allclose(x[m], y[m], rtol=RTOL, atol=ATOL)
    ok &= all(a[c].astype(str).equals(b[c].astype(str)) for c in oth)
    res.update(match=bool(ok), max_abs_numeric_diff=max_abs, numeric_columns=len(num))
    return res


def exact_identical(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    a, b = a.drop(columns=["fit_seconds", "eval_seconds"], errors="ignore"), \
        b.drop(columns=["fit_seconds", "eval_seconds"], errors="ignore")
    return a.shape == b.shape and list(a.columns) == list(b.columns) and a.equals(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repro", default="05_RESULTS/_reproduction_run")
    args = ap.parse_args()
    paths = project_paths(load_config())
    F = paths["results"] / "final"
    P = paths["root"] / args.repro
    out = paths["reproducibility"]
    man_f = json.loads((F / "run_manifest.json").read_text())
    man_p = json.loads((P / "run_manifest.json").read_text())
    rep = {"original": "05_RESULTS/final", "reproduction": args.repro, "tolerance": {"rtol": RTOL, "atol": ATOL},
           "cells_expected": man_f["cells"], "cells_rerun": man_p["cells"],
           "cells_failed_rerun": len(man_p["errors"]),
           "cells_completed_rerun": sum(v["cells"] - v["failed_cells"] for v in man_p["counts"].values()),
           "result_rows_original": sum(v["result_rows"] for v in man_f["counts"].values()),
           "result_rows_rerun": sum(v["result_rows"] for v in man_p["counts"].values()),
           "same_counts_per_variant": man_f["counts"] == man_p["counts"],
           "same_config_hash": man_f["protocol_config_sha256"] == man_p["protocol_config_sha256"],
           "same_input_hashes": man_f["inputs"] == man_p["inputs"],
           "warnings_rerun": man_p["warnings"], "errors_rerun": man_p["errors"],
           "environment_original": man_f["environment"], "environment_rerun": man_p["environment"],
           "execution_rerun": man_p.get("execution"), "wall_seconds_original": man_f["wall_seconds"],
           "wall_seconds_rerun": man_p["wall_seconds"], "files": {}}

    names = sorted(p.name for p in (F / "raw").glob("*.csv"))
    for n in names:
        q = P / "raw" / n
        if not q.exists():
            rep["files"][n] = {"match": False, "missing_in_rerun": True}
            continue
        a, b = pd.read_csv(F / "raw" / n), pd.read_csv(q)
        r = compare_frames(a, b)
        r["exactly_equal_excluding_timing"] = exact_identical(a, b)
        rep["files"][n] = r
    extra = sorted(p.name for p in (P / "raw").glob("*.csv") if p.name not in names)
    rep["files_only_in_rerun"] = extra

    n_files, n_arrays, mism, missing = 0, 0, [], []
    for p in sorted((F / "raw" / "scores").glob("*.npz")):
        q = P / "raw" / "scores" / p.name
        if not q.exists():
            missing.append(p.name)
            continue
        za, zb = np.load(p, allow_pickle=True), np.load(q, allow_pickle=True)
        n_files += 1
        if sorted(za.files) != sorted(zb.files):
            mism.append(f"{p.name}:keys")
        for k in za.files:
            n_arrays += 1
            if k not in zb.files or not np.array_equal(za[k], zb[k], equal_nan=za[k].dtype.kind == "f"):
                mism.append(f"{p.name}:{k}")
    rep["score_files"] = {"files": n_files, "arrays": n_arrays, "bitwise_identical": not mism and not missing,
                          "mismatches": mism[:20], "missing": missing}

    checks = {
        "all_625_cells_rerun": rep["cells_rerun"] == rep["cells_expected"] == 625,
        "all_cells_completed_without_error": rep["cells_failed_rerun"] == 0 and rep["cells_completed_rerun"] == 625,
        "same_result_rows": rep["result_rows_original"] == rep["result_rows_rerun"],
        "same_counts_per_variant": rep["same_counts_per_variant"],
        "same_config_and_input_hashes": rep["same_config_hash"] and rep["same_input_hashes"],
        "all_csv_outputs_match": all(v.get("match") for v in rep["files"].values()) and not extra,
        "score_arrays_bitwise_identical": rep["score_files"]["bitwise_identical"],
    }
    rep["checks"] = checks
    rep["overall_pass"] = all(checks.values())
    (out / "full_reproduction_report.json").write_text(json.dumps(rep, indent=2, default=str))

    env = man_p["environment"]
    L = ["# Full reproduction report (all 625 experiment cells)", "",
         f"Original run: `05_RESULTS/final` (started {man_f['started']}). Reproduction: `{args.repro}` "
         f"(started {man_p['started']}, finished {man_p['finished']}), executed from the two raw EIA-930 CSV files "
         "with the memory-bounded, checkpointed runner (`scripts/run_experiment.py`). The original outputs were not "
         "modified.", "",
         "## Summary", "",
         "| Item | Value |", "|---|---|",
         f"| Cells re-run | {rep['cells_rerun']} of {rep['cells_expected']} |",
         f"| Cells completed successfully | {rep['cells_completed_rerun']} |",
         f"| Failed cells | {rep['cells_failed_rerun']} |",
         f"| Result rows (original / rerun) | {rep['result_rows_original']} / {rep['result_rows_rerun']} |",
         f"| Score files / arrays compared | {n_files} / {n_arrays} (bitwise identical: {rep['score_files']['bitwise_identical']}) |",
         f"| Execution | {json.dumps(rep['execution_rerun'])} |",
         f"| Wall time (original / rerun) | {man_f['wall_seconds']:.0f} s / {man_p['wall_seconds']:.0f} s |",
         f"| Warnings during rerun | {man_p['warnings'] or 'none'} |",
         f"| Errors during rerun | {len(man_p['errors'])} |", "",
         "## Agreement per output file", "",
         f"Tolerance: rtol={RTOL}, atol={ATOL}; timing columns (`fit_seconds`, `eval_seconds`) excluded.", "",
         "| File | Rows (orig / rerun) | Within tolerance | Exactly equal | Max abs numeric difference |",
         "|---|---|---|---|---|"]
    for n, r in rep["files"].items():
        L.append(f"| {n} | {r.get('rows_a')} / {r.get('rows_b')} | {'PASS' if r.get('match') else 'FAIL'} | "
                 f"{r.get('exactly_equal_excluding_timing')} | {r.get('max_abs_numeric_diff', 'n/a')} |")
    L += ["", "## Checks", "", "| Check | Result |", "|---|---|"]
    L += [f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in checks.items()]
    L += ["", "## Software", "",
          f"Python {env['python'].split()[0]}; platform {env['platform']}; CPU threads {env['cpu_count']}; GPU: {env['gpu']}.", "",
          "| Package | Version |", "|---|---|"] + [f"| {k} | {v} |" for k, v in env["packages"].items()]
    L += ["", f"**Full reproduction: {'PASS' if rep['overall_pass'] else 'FAIL'}**", "",
          "Scope: the original run and this reproduction ran on the same machine and software environment. "
          "Reproduction on a second machine or operating system has not been performed."]
    (out / "full_reproduction_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    sys.exit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
