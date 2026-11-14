"""Checkpointing and resumption test of the memory-bounded runner.

Runs the 25-cell holdout_spike variant into a temporary folder with batches of 5, stops after
2 batches (simulated interruption), resumes with the same command, and compares the assembled
outputs with 05_RESULTS/final (timing columns excluded). The temporary folder is deleted afterwards.
Writes 06_AUDIT/reproducibility/resumption_test.json.
Usage: python scripts/resumption_test.py [--workers 2]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
from gridbench.config import load_config, project_paths  # noqa: E402

TIMING = ["fit_seconds", "eval_seconds"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    paths = project_paths(load_config())
    rel = "05_RESULTS/_resumption_test"
    out = paths["root"] / rel
    if out.exists():
        shutil.rmtree(out)
    cmd = [sys.executable, str(CODE / "scripts" / "run_experiment.py"), "--stage", "final", "--outdir", rel,
           "--only", "holdout_spike", "--workers", str(args.workers), "--batch-size", "5"]
    p1 = subprocess.run(cmd + ["--stop-after-batches", "2"], capture_output=True, text=True)
    ck1 = sorted((out / "checkpoints").glob("*.pkl"))
    interrupted = p1.returncode == 3 and len(ck1) == 10 and not (out / "run_manifest.json").exists()
    p2 = subprocess.run(cmd, capture_output=True, text=True)
    man = json.loads((out / "run_manifest.json").read_text()) if p2.returncode == 0 else {}
    res = {"variant": "holdout_spike (25 cells)", "batch_size": 5, "workers": args.workers,
           "first_invocation": {"exit_code": p1.returncode, "checkpoints_after_interruption": len(ck1),
                                "manifest_written": (out / "run_manifest.json").exists() and p1.returncode == 0},
           "second_invocation": {"exit_code": p2.returncode, "execution": man.get("execution", {})},
           "errors": len(man.get("errors", [])) if man else None}
    ok = interrupted and p2.returncode == 0 and man["execution"]["cells_resumed_from_checkpoint"] == 10 \
        and man["execution"]["cells_executed_this_invocation"] == 15 and not man["errors"]
    F = paths["results"] / "final" / "raw"
    for f in ("runs_holdout_spike.csv", "event_detections_holdout_spike.csv"):
        a = pd.read_csv(F / f).drop(columns=TIMING, errors="ignore")
        b = pd.read_csv(out / "raw" / f).drop(columns=TIMING, errors="ignore") if p2.returncode == 0 else None
        exact = b is not None and a.shape == b.shape and a.equals(b)
        within = b is not None and a.shape == b.shape and all(
            np.allclose(a[c], b[c], rtol=1e-9, atol=1e-12, equal_nan=True) if a[c].dtype.kind in "fi" else a[c].equals(b[c])
            for c in a.columns)
        res[f] = {"rows": int(len(a)), "within_tol": bool(within), "exact": bool(exact)}
        ok &= exact
    res["pass"] = bool(ok)
    if not ok:
        res["stdout_tail"] = (p1.stdout + p1.stderr + p2.stdout + p2.stderr)[-3000:]
    (paths["reproducibility"] / "resumption_test.json").write_text(json.dumps(res, indent=1))
    shutil.rmtree(out, ignore_errors=True)
    print(json.dumps(res, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
