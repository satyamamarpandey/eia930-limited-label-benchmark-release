# 04_CODE: research implementation

Run everything through `07_REPRODUCTION/` or the commands in the top-level README. All paths are resolved relative to the project folder by `gridbench/config.py`, so the folder can be copied or moved. The Python environment is not stored here: `07_REPRODUCTION/setup_environment.ps1` creates `04_CODE/.venv` from `requirements.lock.txt`.

| Path | Content |
|---|---|
| `gridbench/io.py` | Reading, parsing and integrity checks of the EIA-930 files; UTC series; natural-suspect flags |
| `gridbench/inject.py` | Controlled fault placement (spike, level shift, drift, flatline, timing) and background missingness |
| `gridbench/features.py` | Causal features (seasonal residuals, differences, volatility, stale run, calendar, missingness indicators) |
| `gridbench/detectors.py` | A: robust seasonal statistic; B: Isolation Forest; C: budgeted PU logistic regression; label-budget sampling (labels read from the injection ledger) |
| `gridbench/metrics.py` | Label-free thresholds; AP, ROC-AUC, TPR@1%FPR; operating metrics; event detection and delay |
| `gridbench/experiment.py` | One experiment cell (authority × seed × missingness condition × variant) |
| `gridbench/stats.py` | Authority-balanced means, two-stage cluster bootstrap, exact sign-flip test, paired differences |
| `gridbench/config.py` | Configuration loading; all project paths |
| `configs/protocol.yaml` | Protocol v1.1 configuration (frozen; SHA-256 `0dd2e911…` recorded in each run manifest and in `06_AUDIT/protocol/PROTOCOL_FREEZE_v1_1.json`) |
| `scripts/run_experiment.py` | Memory-bounded, checkpointed, resumable runner (625 cells for the final stage) |
| `scripts/run_source_audit.py` | Source-data validation → `03_DATA/` |
| `scripts/analyze.py`, `scripts/exploratory_swpp.py` | Tables and `key_numbers.json` (every number in the paper); post-hoc SWPP refit |
| `scripts/make_figures.py`, `scripts/make_manuscript_assets.py` | Figures; LaTeX tables and `\kn{}` number macros |
| `scripts/verify_full_reproduction.py`, `scripts/resumption_test.py` | Full-reproduction comparison; checkpoint/resumption test |
| `tests/` | 57 pytest tests (I/O, injection, causality, leakage, label accounting, metrics, runner checkpoints, provenance, re-execution of saved cells) |
| `requirements.lock.txt` | Exact package versions (Python 3.12.15) |

| `scripts/labels_only_main_rows.py` | Main-table rows, paired differences and family breakdown for detector D (labels-only logistic regression) from the saved ablation runs; no new experiment |
| `scripts/download_data.py` | Downloads the two EIA-930 files and verifies their SHA-256 values (standard library only) |
