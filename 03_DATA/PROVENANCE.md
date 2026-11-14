# Data provenance (03_DATA)

| Item | Value |
|---|---|
| Source | U.S. Energy Information Administration (EIA), Form EIA-930 "Hourly Electric Grid Monitor", BALANCE six-month files for 2024 |
| Download page | https://www.eia.gov/electricity/gridmonitor/ (six-month files). The legacy helper used the path pattern `https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/<file name>`; EIA website paths may change |
| Documentation | https://www.eia.gov/electricity/930-content/about.html; EIA-930 instructions (cited in the paper); field notes in `eia930_field_documentation.md` |
| Files (canonical copies) | `raw/EIA930_BALANCE_2024_Jan_Jun.csv` (41,742,812 bytes; 266,398 rows; 44 columns); `raw/EIA930_BALANCE_2024_Jul_Dec.csv` (47,928,993 bytes; 269,426 rows; 65 columns) |
| SHA-256 | Jan–Jun `26768c495c3ba987e29d79df2e40d4e741f9dbcff086f53c12ff774465756a10`; Jul–Dec `a602a8e577cfdd2fa3083413eaa4dd8ba7f0d2b26a2986f8f6d22917465ea49f` (`SHA256SUMS.txt`; check with `sha256sum -c SHA256SUMS.txt` from this folder) |
| Retrieval | Supplied by the author. The download date was not recorded; the local copies were written on 2026-10-22. EIA revises published data, so a later download may differ; compare hashes |
| Licence / status | Public U.S. government data. The EIA is the source of the observations and does not endorse this work |
| Modification | None. The files are byte-identical to the ones analysed; all processing happens in code |
| Authorities analysed | CISO, ERCO, NYIS, PJM, SWPP (8,784 contiguous hour-ending UTC records each) |
| Attribution used in the paper | "U.S. Energy Information Administration, Form EIA-930, 2024 BALANCE files" |

Schema, coverage, missingness, DST handling and naturally invalid hours are documented in `dataset_manifest.json` (machine-readable), `data_quality_report.md`, and `natural_invalid_runs.json`. These are produced by `04_CODE/scripts/run_source_audit.py`.

No employer, proprietary or personal data are included.

## Retrieval check (added for the public package, 2026-11-13)
A fresh download from `https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/<file name>` of both files produced exactly the SHA-256 values above (41,742,812 and 47,928,993 bytes). `04_CODE/scripts/download_data.py` automates this and verifies the hashes. EIA may revise the files later; the hashes pin the analysed versions.
