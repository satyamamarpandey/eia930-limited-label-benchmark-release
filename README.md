# EIA-930 limited-label anomaly benchmark

Code, frozen protocol, seeds, tests and saved results for the workshop paper *Detecting Controlled Errors in EIA-930 Hourly Demand Records Under Limited Labels: A Reproducible Multi-Region Benchmark* (Learning Representations with Limited Supervision, LRLS, co-located with IEEE BigData 2026; accepted, proceedings details to be added).

The commands below were tested on the platform listed in `docs/TESTED_ENVIRONMENT.md`; commands marked *untested* were not run.

## What is measured
Four detector configurations on hourly demand records of five U.S. balancing authorities (CISO, ERCO, NYIS, PJM, SWPP; EIA Form EIA-930, 2024) with controlled injected errors (spike, level shift, drift, flatline, timing shift), simulated label budgets of 8, 32 and 128 hours, contaminated backgrounds and added missingness: 625 experiment cells.
A: robust seasonal statistic. B: Isolation Forest. C: PU logistic regression (unlabeled hours as weak negatives). D: logistic regression on the labeled hours only.

**All positives are injected errors, not confirmed grid incidents; no human annotated any hour.** The label budget is oracle-curated and class-balanced (half injected, half known non-injected hours); it does not model realistic annotation cost. See `docs/LIMITATIONS.md`.

## Reproduce (Windows PowerShell; tested)
Requires Git, [uv](https://docs.astral.sh/uv/) and internet access. The full experiment takes about 20 minutes with 2 workers.
**Run from a short directory such as `C:\p4`** (`mkdir C:\p4; cd C:\p4`). Windows limits paths to 260 characters, and in a deeply nested location the virtual environment's compiled scikit-learn files exceed it, which makes the test suite fail at import time (observed during testing at a 267-character path).

```powershell
git clone https://github.com/satyamamarpandey/eia930-limited-label-benchmark-release.git
cd eia930-limited-label-benchmark-release
uv venv --python 3.12.15 .venv
uv pip install --python .venv\Scripts\python.exe -r 04_CODE\requirements.lock.txt
.venv\Scripts\python.exe 04_CODE\scripts\download_data.py
$env:GRIDBENCH_REQUIRE_ALL = "1"
cd 04_CODE
..\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
..\.venv\Scripts\python.exe scripts\run_experiment.py --stage final --outdir 05_RESULTS/_reproduction_run --workers 2 --batch-size 25
..\.venv\Scripts\python.exe scripts\verify_full_reproduction.py --repro 05_RESULTS/_reproduction_run
..\.venv\Scripts\python.exe scripts\run_source_audit.py
..\.venv\Scripts\python.exe scripts\analyze.py
..\.venv\Scripts\python.exe scripts\exploratory_swpp.py
..\.venv\Scripts\python.exe scripts\analyze.py
..\.venv\Scripts\python.exe scripts\make_figures.py
..\.venv\Scripts\python.exe scripts\labels_only_main_rows.py
cd ..
```
Expected: `57 passed`; the reproduction report ends with **Full reproduction: PASS** (all CSVs equal, 3,250 score arrays bitwise identical) and is written to `06_AUDIT/reproducibility/full_reproduction_report.md`. The regenerated tables, key numbers, data reports and figure images equal the shipped ones: afterwards `git status` shows only the five `05_RESULTS/figures/*.pdf` files as modified (their drawing content is identical; only embedded-font bytes differ, as observed in testing) and the new `06_AUDIT/reproducibility/full_reproduction_report.*` files. `04_CODE\scripts\labels_only_main_rows.py` writes the detector-D rows to `05_RESULTS/camera_ready_extra/`.
The same steps are wrapped in `07_REPRODUCTION\*.ps1` (`setup_environment.ps1`, `run_tests.ps1`, `rebuild_experiment.ps1`, `regenerate_outputs.ps1`).

## Reproduce with pip (any OS; untested except the test suite, see `docs/TESTED_ENVIRONMENT.md`)
Needs Python 3.12 on `PATH`.
```
python3.12 -m venv .venv
.venv/bin/python -m pip install -r 04_CODE/requirements.lock.txt      # Windows: .venv\Scripts\python.exe
.venv/bin/python 04_CODE/scripts/download_data.py
cd 04_CODE && GRIDBENCH_REQUIRE_ALL=1 ../.venv/bin/python -m pytest tests -q -p no:cacheprovider
```
The remaining steps are the same as above with the interpreter path adapted. Linux and macOS have not been tested.

## Data (not redistributed here)
Two EIA-930 BALANCE six-month files for 2024 from <https://www.eia.gov/electricity/gridmonitor/>. `download_data.py` downloads them and verifies the SHA-256 values in `03_DATA/SHA256SUMS.txt` (verified on 2026-11-13: a fresh download matched). EIA revises published data, so a later download may differ; then the script stops. Provenance, schema and quality reports: `03_DATA/`. Attribution: see `NOTICE_DATA.md`.

## Layout
| Folder | Content |
|---|---|
| `03_DATA/` | Provenance, hashes, schema and data-quality reports (raw files are downloaded, not stored) |
| `04_CODE/` | `gridbench/` package, `configs/protocol.yaml` (frozen protocol v1.1, includes seeds), `scripts/`, `tests/`, `requirements.lock.txt` |
| `05_RESULTS/` | Saved results of the reported run (per-run rows, injection ledger, score arrays, tables, key numbers, figures) |
| `06_AUDIT/` | Protocol and amendment history; the archived v1.0 run (75 MB; needed by `analyze.py` for the leakage numbers) |
| `07_REPRODUCTION/` | PowerShell wrappers and environment notes |
| `02_MANUSCRIPT_SOURCE/` | Empty placeholders only: `make_figures.py` and `make_manuscript_assets.py` write paper-ready copies here; the manuscript itself is not part of this repository |
| `docs/` | Limitations, tested environment, note on the frozen protocol file |
| `LICENSE`, `LICENSE-CC-BY-4.0.txt`, `LICENSES.md` | Licence texts and their scope |

## Protocol history
Protocol v1.0 was frozen before test evaluation; v1.1 corrects a missingness-mask design that leaked labels and was made after test results had been seen, so it is not pre-registered in the strict sense. v1.0 is archived. `04_CODE/configs/protocol.yaml` is the frozen v1.1 file, unchanged; see `docs/PROTOCOL_PATH_COMMENT.md` for why its first comment still contains a local path.

## Verification status
Reproduction was demonstrated on one Windows 11 machine with a pinned environment, through the documented automated workflow (Claude Code running the documented commands), not by an independent party; a second machine or operating system has not been tested.

## Licence, citation, data attribution
* Source code: MIT License (`LICENSE`). Documentation, derived tables and the original figures: CC BY 4.0 (`LICENSE-CC-BY-4.0.txt`). Scope and exceptions: `LICENSES.md`; third-party and redistribution notes: `docs/RIGHTS_AND_REDISTRIBUTION.md`.
* The EIA-930 data belong to the U.S. Energy Information Administration and are not part of this repository; please attribute EIA as the source (`NOTICE_DATA.md`).
* Citation: `CITATION.cff`. Proceedings details will be added after publication.

## AI assistance
The author directed the research and is responsible for its conclusions. Claude (Anthropic), used through Claude Code, assisted substantively with code, experiment execution, analysis, figures, references and text, as disclosed in the paper.

Author: Satyam Adharchandra Pandey, Independent Researcher, United States (ORCID 0009-0002-9127-6960).
