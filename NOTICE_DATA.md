# Data notice

This repository does not contain EIA-930 data files. The experiments use the EIA-930 BALANCE six-month files for 2024 (source: U.S. Energy Information Administration, Form EIA-930, <https://www.eia.gov/electricity/gridmonitor/>). The EIA is the source of the underlying observations. Suggested acknowledgment: "Source: U.S. Energy Information Administration, Form EIA-930, 2024 BALANCE files (retrieved 2026-11-13)." This work is not an EIA product and is not endorsed by the EIA. Retrieval instructions and SHA-256 values are in `03_DATA/`; use `04_CODE/scripts/download_data.py`.
Saved per-run results and tables in `05_RESULTS/` are derived from those data after injecting synthetic errors; the injected positives are not real reporting errors.
