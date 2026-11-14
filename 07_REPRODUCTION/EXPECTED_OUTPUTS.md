# Expected outputs

## Source data (`03_DATA`)
| File | SHA-256 | Rows | Columns |
|---|---|---|---|
| `raw/EIA930_BALANCE_2024_Jan_Jun.csv` | `26768c495c3ba987e29d79df2e40d4e741f9dbcff086f53c12ff774465756a10` | 266,398 | 44 |
| `raw/EIA930_BALANCE_2024_Jul_Dec.csv` | `a602a8e577cfdd2fa3083413eaa4dd8ba7f0d2b26a2986f8f6d22917465ea49f` | 269,426 | 65 |

## Experiment (`05_RESULTS/final`)
625 cells, 8,750 result rows, 0 failed cells, 0 errors, no warnings. Protocol v1.1, configuration SHA-256 `0dd2e911…` (full value in `run_manifest.json`).

| Variant | Cells | Result rows |
|---|---|---|
| primary | 125 | 2,125 |
| tuned | 125 | 2,125 |
| abl_no_residual | 75 | 1,200 |
| abl_no_missing_ind | 75 | 1,200 |
| abl_labels_only | 50 | 750 |
| contam_2 | 25 | 300 |
| contam_10 | 25 | 425 |
| holdout_spike / level_shift / drift / flatline / timing | 25 each | 125 each |
| **Total** | **625** | **8,750** |

Other outputs:
* 125 score files (`raw/scores/*.npz`, 3,250 arrays);
* `injection_ground_truth.csv`: 4,125 events, of which 1,375 are at the primary contamination level, 375 of them test events.

A correct full reproduction (`rebuild_experiment.ps1`) gives, in `06_AUDIT/reproducibility/full_reproduction_report.md`:
* every CSV within tolerance, and exactly equal on the recorded software stack (wall-clock columns `fit_seconds` and `eval_seconds` excluded);
* all 3,250 score arrays bitwise identical;
* overall PASS.

Derived files are regenerated with `regenerate_outputs.ps1`, which reports any file that differs from the shipped version.
