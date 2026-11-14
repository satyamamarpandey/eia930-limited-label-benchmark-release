"""Run the benchmark.

  python scripts/run_experiment.py --stage dev     # validation-only development run (no test metrics)
  python scripts/run_experiment.py --stage final   # frozen-protocol run with held-out test evaluation
  python scripts/run_experiment.py --stage final --outdir 05_RESULTS/rerun_primary --only primary   # primary-only rerun
  python scripts/run_experiment.py --stage final --outdir 05_RESULTS/_reproduction_run --workers 2  # memory-bounded full rerun

Execution is memory-bounded and resumable: cells run in sequential batches, each on a fresh, small
process pool that is shut down after the batch (this releases worker memory; per-child task limits
are not used because ProcessPoolExecutor can deadlock while replacing such workers); each finished cell is checkpointed to <outdir>/checkpoints/ and validated before the
next batch starts, and an interrupted run continues from its checkpoints when restarted. Outputs are
assembled from the checkpoints in the fixed task order, so they do not depend on batching, worker
count or resumption. An outdir that already holds a run manifest is never overwritten unless
--overwrite is given.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import pickle
import platform
import sys
import time
import traceback
import warnings
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from importlib import metadata
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
from gridbench import inject, io  # noqa: E402
from gridbench.config import config_hash, load_config, project_paths  # noqa: E402
from gridbench.experiment import make_context, run_cell  # noqa: E402

_CTX = {}
_CFG = {}


def variants(cfg: dict) -> list[dict]:
    conds = [c["name"] for c in cfg["missingness"]["conditions"]]
    v = [{"name": "primary", "conditions": conds, "keep_scores": True},
         {"name": "tuned", "regime": "tuned", "conditions": conds},
         {"name": "abl_no_residual", "feature_set": "no_residual", "methods": ["iforest", "pu"],
          "conditions": ["none", "mcar15", "block15"]},
         {"name": "abl_no_missing_ind", "feature_set": "no_missing_ind", "methods": ["iforest", "pu"],
          "conditions": ["none", "mcar15", "block15"]},
         {"name": "abl_labels_only", "u_share": 0.0, "methods": ["pu"], "conditions": ["none", "mcar15"]}]
    for n in cfg["ablations"]["contamination_events_per_family"]:
        if n != cfg["injection"]["events_per_family"]["train"]:
            # with 2 events/family the training period can hold < 64 altered hours, so B=128
            # cannot be filled without breaking the label definition; it is omitted there
            budgets = [b for b in cfg["methods"]["label_budgets"] if n >= 6 or b <= 32]
            v.append({"name": f"contam_{n}", "n_train": n, "conditions": ["none"], "budgets": budgets})
    for fam in inject.FAMILIES:
        v.append({"name": f"holdout_{fam}", "exclude_families": [fam], "methods": ["pu"], "budgets": [32],
                  "conditions": ["none"]})
    return v


def _init(ctxs, cfg):
    _CTX.update(ctxs)
    _CFG.update(cfg)


def _task(args):
    ba, variant, seed, cond_idx, eval_split, score_dir = args
    cfg = _CFG
    cond = cfg["missingness"]["conditions"][cond_idx]
    t0 = time.perf_counter()
    with warnings.catch_warnings(record=True) as wlist:
        warnings.simplefilter("always")
        try:
            rows, erows, ev_df, blob = run_cell(_CTX[ba], seed, cond_idx, cond, cfg, variant, eval_split,
                                                keep_scores=variant.get("keep_scores", False) and score_dir is not None)
            err = None
        except Exception:  # recorded, never silently dropped
            rows, erows, ev_df, blob = [], [], None, None
            err = traceback.format_exc()
    if blob is not None:
        np.savez_compressed(Path(score_dir) / f"{ba}_s{seed}_{cond['name']}.npz",
                            **{f"score__{k}": v for k, v in blob.pop("scores").items()}, **blob)
    warn = Counter(f"{w.category.__name__}: {str(w.message)[:160]}" for w in wlist)
    return {"key": (variant["name"], ba, seed, cond["name"]), "rows": rows, "event_rows": erows,
            "events": ev_df, "error": err, "warnings": dict(warn), "seconds": time.perf_counter() - t0}


def environment() -> dict:
    pk = {}
    for p in ["numpy", "pandas", "scikit-learn", "scipy", "matplotlib", "pyyaml", "pytest"]:
        try:
            pk[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            pk[p] = None
    return {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
            "processor": platform.processor(), "cpu_count": os.cpu_count(), "gpu": "not used", "packages": pk}


def cell_name(task) -> str:
    ba, v, s, ci, _, _ = task
    return f"{v['name']}__{ba}__s{s}__c{ci}"


def save_checkpoint(path: Path, r: dict) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "wb") as fh:
        pickle.dump(r, fh, protocol=5)
    os.replace(tmp, path)  # atomic: a checkpoint is either complete or absent


def load_checkpoint(path: Path, task) -> dict | None:
    """Return the checkpointed result if it is readable, error-free and belongs to this task."""
    try:
        with open(path, "rb") as fh:
            r = pickle.load(fh)
    except Exception:
        return None
    ba, v, s, ci, _, score_dir = task
    if r.get("error") or r["key"][:3] != (v["name"], ba, s) or not r["rows"]:
        return None
    if v.get("keep_scores") and score_dir and not (Path(score_dir) / f"{ba}_s{s}_{r['key'][3]}.npz").exists():
        return None
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["dev", "final"], required=True)
    ap.add_argument("--outdir", default=None, help="relative to the final project folder")
    ap.add_argument("--only", default=None, help="comma-separated variant names")
    ap.add_argument("--workers", type=int, default=2, help="concurrent worker processes (memory-bound)")
    ap.add_argument("--batch-size", type=int, default=25, help="cells per checkpointed batch")
    ap.add_argument("--overwrite", action="store_true", help="allow replacing an existing completed run")
    ap.add_argument("--seeds", default=None, help="override seeds (dev only)")
    ap.add_argument("--stop-after-batches", type=int, default=None,
                    help="testing aid: exit after N batches, as if interrupted (see scripts/resumption_test.py)")
    args = ap.parse_args()
    cfg = load_config()
    paths = project_paths(cfg)
    outdir = paths["root"] / (args.outdir or f"05_RESULTS/{args.stage}")
    if (outdir / "run_manifest.json").exists() and not args.overwrite:
        raise SystemExit(f"{outdir} already holds a completed run; choose a new --outdir (or pass --overwrite)")
    raw = outdir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    ckpt = outdir / "checkpoints"
    ckpt.mkdir(exist_ok=True)
    score_dir = None
    eval_split = "test" if args.stage == "final" else "val"
    if args.stage == "final":
        score_dir = raw / "scores"
        score_dir.mkdir(exist_ok=True)
    seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else cfg["seeds"]
    if args.seeds and args.stage == "final":
        raise SystemExit("seed override not allowed for final stage")

    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    t_start = time.perf_counter()
    df = io.load_eia(paths["inputs"], cfg["data"]["authorities"])
    ctxs = {ba: make_context(df, ba, i, cfg) for i, ba in enumerate(cfg["data"]["authorities"])}
    vs = variants(cfg)
    if args.only:
        keep = set(args.only.split(","))
        vs = [v for v in vs if v["name"] in keep]
    cond_names = [c["name"] for c in cfg["missingness"]["conditions"]]
    tasks = [(ba, v, s, cond_names.index(c), eval_split, str(score_dir) if score_dir else None)
             for v in vs for ba in ctxs for s in seeds for c in v["conditions"]]
    paths_ck = [ckpt / f"{cell_name(t)}.pkl" for t in tasks]
    done = [load_checkpoint(p, t) is not None for p, t in zip(paths_ck, tasks)]
    pending = [i for i, d in enumerate(done) if not d]
    print(f"{len(tasks)} cells ({len(tasks) - len(pending)} already checkpointed), {args.workers} workers, "
          f"batch {args.batch_size}, eval split = {eval_split}", flush=True)
    for b0 in range(0, len(pending), args.batch_size):
        batch = pending[b0:b0 + args.batch_size]
        with ProcessPoolExecutor(max_workers=args.workers, initializer=_init, initargs=(ctxs, cfg)) as ex:
            for i, r in zip(batch, ex.map(_task, [tasks[i] for i in batch], chunksize=1)):
                if r["error"]:
                    print("ERROR", r["key"], r["error"], flush=True)
                save_checkpoint(paths_ck[i], r)
                del r
        bad = [cell_name(tasks[i]) for i in batch if load_checkpoint(paths_ck[i], tasks[i]) is None]
        gc.collect()
        n_done = len(tasks) - len(pending) + b0 + len(batch)
        print(f"  {n_done}/{len(tasks)} cells done; batch validated: "
              f"{'OK' if not bad else 'INVALID ' + ', '.join(bad)}", flush=True)
        if bad:
            raise SystemExit("checkpoint validation failed; fix the cause and re-run to resume")
        if args.stop_after_batches and b0 // args.batch_size + 1 >= args.stop_after_batches and n_done < len(tasks):
            print(f"stopped after {args.stop_after_batches} batch(es) on request (simulated interruption)", flush=True)
            raise SystemExit(3)

    # Assemble outputs variant by variant from the checkpoints, in task order.
    errors, warn_total, counts, inj_parts, cell_seconds = [], Counter(), {}, [], []
    for v in vs:
        rows, erows, n_cells, n_failed = [], [], 0, 0
        for p, t in zip(paths_ck, tasks):
            if t[1]["name"] != v["name"]:
                continue
            with open(p, "rb") as fh:
                r = pickle.load(fh)
            n_cells += 1
            cell_seconds.append(r["seconds"])
            warn_total.update(r["warnings"])
            if r["error"]:
                n_failed += 1
                errors.append({"cell": list(r["key"]), "traceback": r["error"]})
            rows.extend(r["rows"])
            erows.extend(r["event_rows"])
            if r["events"] is not None and (r["key"][3] == "none" or v["name"].startswith("contam")):
                inj_parts.append((0 if r["key"][3] == "none" else 1, len(inj_parts), r["events"]))
        runs = pd.DataFrame(rows)
        runs.to_csv(raw / f"runs_{v['name']}.csv", index=False, float_format="%.10g")
        ev = pd.DataFrame(erows)
        if len(ev):
            ev.to_csv(raw / f"event_detections_{v['name']}.csv", index=False, float_format="%.10g")
        counts[v["name"]] = {"cells": n_cells, "result_rows": int(len(runs)), "failed_cells": n_failed}
        del rows, erows, runs, ev
        gc.collect()
    # same concatenation order as the original runner: condition-'none' cells first, then contamination cells
    inj = pd.concat([e for _, _, e in sorted(inj_parts, key=lambda x: (x[0], x[1]))],
                    ignore_index=True).drop_duplicates(["ba", "seed", "n_train_events_per_family", "event_id"])
    inj = inj.sort_values(["n_train_events_per_family", "ba", "seed", "event_id"])
    inj.to_csv(raw / "injection_ground_truth.csv", index=False)

    manifest = {
        "stage": args.stage, "eval_split": eval_split, "started": started,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "wall_seconds": time.perf_counter() - t_start,
        "protocol_config_sha256": config_hash(), "protocol_version": cfg["protocol_version"],
        "inputs": [{"file": p.name, "sha256": io.sha256_file(p)} for p in paths["inputs"]],
        "seeds": seeds, "label_draws_per_seed": cfg["label_draws_per_seed"],
        "splits": cfg["splits"], "variants": vs, "cells": len(tasks), "counts": counts,
        "errors": errors, "warnings": dict(warn_total), "environment": environment(),
        "execution": {"workers": args.workers, "batch_size": args.batch_size,
                      "worker_pool": "fresh pool per batch",
                      "cells_resumed_from_checkpoint": len(tasks) - len(pending),
                      "cells_executed_this_invocation": len(pending),
                      "cell_seconds_total": round(float(sum(cell_seconds)), 1)},
        "hyperparameters": cfg["methods"], "tuning_grid": cfg["tuning"],
    }
    (outdir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(json.dumps({"counts": counts, "errors": len(errors), "warnings": dict(warn_total),
                      "wall_seconds": round(manifest["wall_seconds"], 1)}, indent=2))


if __name__ == "__main__":
    main()
