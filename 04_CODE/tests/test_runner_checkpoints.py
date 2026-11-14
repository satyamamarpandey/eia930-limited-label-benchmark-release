"""Checkpoint handling of the memory-bounded runner (scripts/run_experiment.py)."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "run_experiment", Path(__file__).resolve().parents[1] / "scripts" / "run_experiment.py")
rx = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rx)


def _task(tmp_path, keep_scores=False):
    v = {"name": "primary" if keep_scores else "tuned", "keep_scores": keep_scores}
    return ("PJM", v, 11, 0, "test", str(tmp_path) if keep_scores else None)


def _result(task, error=None, rows=({"ap": 0.5},)):
    ba, v, s, _, _, _ = task
    return {"key": (v["name"], ba, s, "none"), "rows": list(rows), "event_rows": [], "events": None,
            "error": error, "warnings": {}, "seconds": 1.0}


def test_roundtrip_and_name(tmp_path):
    t = _task(tmp_path)
    p = tmp_path / f"{rx.cell_name(t)}.pkl"
    assert rx.cell_name(t) == "tuned__PJM__s11__c0"
    rx.save_checkpoint(p, _result(t))
    assert not p.with_suffix(".tmp").exists()  # atomic write leaves no temporary file
    assert rx.load_checkpoint(p, t)["rows"] == [{"ap": 0.5}]


@pytest.mark.parametrize("bad", ["error", "empty", "wrong_cell", "corrupt", "missing"])
def test_invalid_checkpoints_are_rerun(tmp_path, bad):
    t = _task(tmp_path)
    p = tmp_path / "c.pkl"
    if bad == "error":
        rx.save_checkpoint(p, _result(t, error="Traceback"))
    elif bad == "empty":
        rx.save_checkpoint(p, _result(t, rows=()))
    elif bad == "wrong_cell":
        rx.save_checkpoint(p, _result(("SWPP",) + t[1:]))
    elif bad == "corrupt":
        p.write_bytes(b"not a pickle")
    assert rx.load_checkpoint(p, t) is None


def test_primary_checkpoint_requires_score_file(tmp_path):
    t = _task(tmp_path, keep_scores=True)
    p = tmp_path / "c.pkl"
    rx.save_checkpoint(p, _result(t))
    assert rx.load_checkpoint(p, t) is None  # score file not written yet
    (tmp_path / "PJM_s11_none.npz").write_bytes(b"x")
    assert rx.load_checkpoint(p, t) is not None
