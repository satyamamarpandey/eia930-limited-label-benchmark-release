# 07_REPRODUCTION

Windows PowerShell wrappers (PowerShell 7 should also work on Linux/macOS with the same arguments). The Python commands in the top-level README are platform independent.

| Purpose | Command | Time |
|---|---|---|
| Create the environment (needs uv) | `.\setup_environment.ps1` | ~1 min |
| Run all tests (strict) | `.\run_tests.ps1` | ~15 s |
| Re-run all 625 cells and compare with `05_RESULTS\final` | `.\rebuild_experiment.ps1` | ~13-40 min |
| Regenerate tables, key numbers and figures and report differences | `.\regenerate_outputs.ps1` | ~2 min |
| Remove temporary files | `.\clean.ps1` | - |

Put the two EIA-930 files in `03_DATA\raw\` first (see `03_DATA\PROVENANCE.md`); the scripts check their SHA-256 values.
Requirements: `ENVIRONMENT_REQUIREMENTS.md`. Expected results: `EXPECTED_OUTPUTS.md`.

If Windows Smart App Control blocks compiled Python packages at the environment location, create the environment on another drive with `.\setup_environment.ps1 -VenvDir <path>` and set `$env:PAPER4_PYTHON` to its `python.exe`.
