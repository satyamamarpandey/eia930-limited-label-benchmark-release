# Tested environment

All verification of this package was done on **one machine**; no other machine, operating system or independent party has reproduced the results. The tests were executed through the documented automated workflow (Claude Code running the documented commands).

| Item | Value |
|---|---|
| Operating system | Windows 11 Home 10.0.26200, x86-64 |
| CPU / RAM | 12 logical threads, no GPU; 16 GB |
| Python | 3.12.15 (installed and managed by uv 0.13.0) |
| Packages | exactly `04_CODE/requirements.lock.txt` (numpy 2.5.4, pandas 3.1.0, scikit-learn 1.9.1, scipy 1.18.1, matplotlib 3.11.2, pyyaml 6.0.3, pytest 9.1.1, pypdf 6.21.2, pillow 13.0.0, ...) |
| Shell | Windows PowerShell 5.1 |
| Git | 2.55 |
| Working directory | a short path (`C:\p4t\...`); a 267-character path made the compiled scikit-learn modules fail to import (Windows MAX_PATH) |
| Network | needed for `uv`, `pip`, and the EIA download |

## What was run
* The 17 commands of the README's PowerShell block, executed literally, one by one, from a fresh `git clone` of an earlier staging commit whose code, results, data reports and protocol files are identical to this repository (2026-11-13, 11:56-12:12 local time), including `download_data.py` (the EIA files downloaded fresh and matched the recorded SHA-256 values). All 17 commands exited with code 0. An earlier attempt at a 267-character path failed at the test step (see above) and led to the short-path instruction; a second attempt failed in `make_figures.py` because an empty folder is not kept by git, which led to the placeholder files.
* Strict test suite: 57 passed (`GRIDBENCH_REQUIRE_ALL=1`), about 14 seconds.
* The 625-cell reproduction: about 11 minutes with 2 workers (about 12 minutes for the whole block after the environment setup); all result CSVs equal, 3,250 score arrays bitwise identical.
* Regeneration of tables, key numbers and figures: after the run `git status` listed only the five figure PDFs as modified (embedded-font bytes) plus the two new reproduction-report files; the regenerated detector-D files were byte-identical to those used for the paper.
The wrappers in `07_REPRODUCTION/` were run in an earlier fresh-environment test and call the same scripts.

## Not tested
Linux and macOS; the pip route as written in the README for POSIX shells (the POSIX path strings were not run; a Windows-adapted equivalent, `python3.12 -m venv`, `pip install -r 04_CODE/requirements.lock.txt`, then the strict test suite, gave 57 passed in about one minute using the uv-installed Python 3.12.15); the experiment and regeneration steps with a pip-created environment; other Python versions; other CPUs or BLAS builds (small floating-point differences are possible, and `verify_full_reproduction.py` reports them against a tolerance).
