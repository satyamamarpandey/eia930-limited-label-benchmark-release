# Protocol changes log

## Before freeze (v1.0 development; validation-only data seen)

| When | Change | Reason |
|---|---|---|
| Development | Minimum event gap set to 24 h (from 48 h); contamination levels 2/6/10 (from 2/6/12) events per family | 12 events/family could not be placed in the training period with a 48 h gap |
| Development | Natural-suspect audit flag and sensitivity analysis added | Validation-only debugging revealed naturally repeated values in SWPP and isolated natural reversals |
| Development | Contamination ablation at 2 events/family runs only B = 8, 32 | Fewer than 64 altered training hours can exist; B = 128 would break the label definition |

v1.0 frozen 2026-10-22T21:33:25-04:00 (`PROTOCOL_FREEZE.json`, config SHA-256 `1e2d6a4a…8037`).

## Amendment v1.1 (after the v1.0 held-out test run)

**Timing.** Made after the v1.0 final run and its first aggregation, i.e., after test-period metrics had been computed. This is therefore a *post-hoc* amendment, and it is disclosed as such in the manuscript.

**What was found.** When the prevalence-invariant ROC-AUC was added to the missingness analysis, PU-LR's ROC-AUC *increased* with nuisance missingness (e.g., +0.098 at MCAR 15%, B = 128). A diagnostic showed why. In v1.0, nuisance missingness was never placed inside injected event windows (`protected = event windows`), so the previous hour of an injected hour was almost never missing. Example: PJM, seed 11, MCAR 15%, test hours: P(previous hour missing | injected) = 0.000 versus 0.158 for normal hours. The missingness-indicator features therefore carried label information, which is a benchmark artifact, not a detector property. The no-missingness-indicator ablation confirmed it: without indicators, PU-LR's ROC-AUC is flat across conditions, and Isolation Forest's degradation largely disappears.

**Change.** `missingness.protect_injected_hours: false`. Nuisance masks are drawn over all naturally valid hours, independently of the injections. Masked injected hours are not scored (as for any masked hour); event-level metrics use each event's remaining scored hours. Everything else is unchanged: rates, mechanisms, seeds and RNG streams, injections, detectors, thresholds and metrics.

**Also fixed in v1.1 (no effect on any metric).** The `utc_index` field written to score files was truncated (pandas 3 stores timestamps in microseconds, and the code divided by 10^9). v1.1 stores exact epoch seconds. In addition, `scripts/analyze.py` rebuilds the index from the source manifest, and a test checks the stored index against the source.

**Not chosen in response to performance.** The change addresses a leakage diagnostic (a property of the labels, not of any detector's score), and it is applied uniformly to all detectors.

**Reporting.**
* The v1.0 results are archived unchanged in `04_RESULTS/final_v1_0_protected/`.
* v1.1 results are in `04_RESULTS/final/`. The 0%-missingness condition is unaffected by construction, and it is verified identical between versions in `09_FINAL_AUDIT`.
* The manuscript reports v1.1 and discloses the amendment and the v1.0 artifact.
* A regression test (`test_missingness_independent_of_labels`) now guards against the leak.

## Final review, 2026-10-23 (no change to the experimental design)

| Change | Type | Effect on results |
|---|---|---|
| Matched difference-in-differences of missingness-induced AP change, with vs. without missingness indicators (`scripts/analyze.py`, `table_missingness_indicator_did.csv`, keys `missind_did_*`) | **Post-hoc analysis** of existing outputs of the pre-registered no-missingness-indicator ablation. Added because the earlier text attributed Isolation Forest's loss to the indicators without isolating it. Labelled post hoc in the manuscript | Adds 66 key numbers; all 1,650 existing key numbers verified unchanged |
| Experiment runner made memory-bounded and resumable: sequential checkpointed batches, `--workers` default 2, a fresh worker pool per batch, validation after each batch, refusal to overwrite a completed run | Execution only. Tasks, seeds, RNG streams and output assembly order are unchanged | Full 625-cell re-execution is bitwise identical to `04_RESULTS/final` (`07_REPRODUCIBILITY/full_reproduction_report.md`) |
| `reproduce_all.ps1` re-executes into a separate directory and compares; never writes into `04_RESULTS/final` when it exists; falls back to pdflatex/bibtex without Perl | Execution only | None |
| Manuscript wording: v1.1 explicitly not pre-registered; contribution bullet no longer says "pre-registered"; Isolation Forest causal claim narrowed to the DiD evidence; "released" removed; AI disclosure no longer claims author review; reproducibility sentence updated to the full rerun | Reporting | None on numbers; 9 pages |

## Final consolidation review, 2026-10-23 (no change to the experimental design or to any result)

| Change | Type | Effect on results |
|---|---|---|
| Label terminology in the manuscript: "verified labels/hours" and "expert-verified" replaced by "labeled hours", "simulated annotation budget", "injection-derived labels" and "known non-injected hours"; text added that no human annotated any hour and that non-injected hours are not verified to be free of natural reporting errors | Reporting correction. No human expert annotated or verified any observation; budgeted labels are read from the injection ledger | None. Internal identifiers (`n_verified_labels` result column, the docstring in `gridbench/detectors.py`) keep their original names so that the frozen code and saved outputs stay byte-identical |
| Section V-E: "pre-registered ablation" changed to "ablation ... (specified before any test evaluation)"; "attributable" changed to neutral difference-in-differences wording, with a sentence that the post-hoc comparison is not a formal causal decomposition | Reporting | None |
| Last-page column balancing (`\IEEEtriggeratref`) | Formatting | None; still 9 pages |
| Project consolidated into `Submission__Final_Paper4____`: code moved from `03_CODE/` to `04_CODE/`, protocol records from `02_RESEARCH_PROTOCOL/` to `06_AUDIT/protocol/`, results from `04_RESULTS/` to `05_RESULTS/`, raw data from `data/` to `03_DATA/raw/`. `gridbench/config.py` resolves all paths relative to the project folder and takes only the file names from `protocol.yaml`, which stays byte-identical (SHA-256 `0dd2e911…`) | Engineering | None: every table, key number, figure-data file and score array regenerated byte-identically from the new location; all 625 cells re-executed from the new location (`06_AUDIT/reproducibility/full_reproduction_report.md`) |
| `run_experiment.py`: `--stop-after-batches` testing option (simulated interruption) and new default output folders | Engineering | None |
| Test replacing the comparison with the deleted primary-only rerun folder: re-executes two primary cells and requires identical rows and bitwise-identical score arrays; a second test checks every final raw output against the SHA-256 values recorded on 2026-10-22 | Tests (stronger, self-contained) | None |

## Folder rename, 2026-10-23 (no change to design, code behaviour or results)
The final project folder was renamed from `Submission__Final_Paper4____` to `Submission_Final_Paper4` at the author's instruction. All paths in the code are relative, so nothing else changed. The entry above keeps the name in use at the time.

## Author metadata, 2026-10-23 (no change to design, code behaviour or results)
After the author's review, the author block and the Acknowledgments and Disclosures paragraph of the manuscript were updated with the author's supplied details and declarations (`06_AUDIT/FINAL_REVIEW_CHANGELOG.md`, section H). The protocol, the frozen configuration and all results are unchanged.
