"""Configuration loading and path resolution.

All paths are resolved relative to the final project folder (the parent of 04_CODE), so the
folder can be copied or moved as a whole.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

CODE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = CODE_DIR.parent
DEFAULT_CONFIG = CODE_DIR / "configs" / "protocol.yaml"


def load_config(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT_CONFIG, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def config_hash(path: str | Path | None = None) -> str:
    return hashlib.sha256(Path(path or DEFAULT_CONFIG).read_bytes()).hexdigest()


def project_paths(cfg: dict) -> dict:
    # The frozen protocol.yaml lists the inputs as data/<file>; only the file names are used here,
    # so the frozen configuration (and its recorded SHA-256) stays unchanged.
    return {
        "root": ROOT_DIR,
        "code": CODE_DIR,
        "data": ROOT_DIR / "03_DATA",
        "inputs": [ROOT_DIR / "03_DATA" / "raw" / Path(p).name for p in cfg["data"]["inputs"]],
        "results": ROOT_DIR / "05_RESULTS",
        "figures": ROOT_DIR / "05_RESULTS" / "figures",
        "manuscript": ROOT_DIR / "02_MANUSCRIPT_SOURCE",
        "submission": ROOT_DIR / "01_SUBMISSION",
        "audit": ROOT_DIR / "06_AUDIT",
        "protocol": ROOT_DIR / "06_AUDIT" / "protocol",
        "reproducibility": ROOT_DIR / "06_AUDIT" / "reproducibility",
        "v1_0_archive": ROOT_DIR / "06_AUDIT" / "historical_evidence" / "v1_0_pre_amendment_run.zip",
    }
