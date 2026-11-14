# Rights and redistribution notes

| Topic | Finding |
|---|---|
| Authorship of the code | Written for this research under the author's direction with substantial assistance from Claude (Anthropic) through Claude Code. The author licenses it under MIT as rights holder to the extent rights exist; the legal status of AI-assisted material varies by jurisdiction, so the repository states that assistance openly. |
| Third-party source code | None is copied into the repository. Dependencies (numpy, pandas, scikit-learn, scipy, matplotlib, pyyaml, pytest, pypdf, pillow and their requirements, pinned in `04_CODE/requirements.lock.txt`) are installed from PyPI and are not redistributed. |
| EIA-930 data | Published by the U.S. Energy Information Administration. The raw files are not redistributed; `04_CODE/scripts/download_data.py` retrieves them from EIA and verifies the SHA-256 values. EIA's copyright and reuse page (https://www.eia.gov/about/copyrights_reuse.php, read on 2026-11-13) states that U.S. government publications are in the public domain, that its data and files may be used and distributed, and that an acknowledgment of the source with the date is requested (for example "Source: U.S. Energy Information Administration (date)"). The EIA logo, the Energy Ant graphic and photographs have separate conditions and are not used here. Please attribute EIA; this work is not endorsed by the EIA. |
| Derived results | Per-run results, injection ledgers, score arrays and tables are computations on the EIA data plus synthetic errors. Injected positives are not real reporting errors. |
| Fonts in figures | Figure PDFs embed subsets of Times New Roman as embedded in documents; the font software is not redistributed. |
| Publisher material | The accompanying paper, its PDF and the IEEE class files are not included. The paper is subject to IEEE's publication terms. |
| Personal data | The repository names the author and ORCID only; it contains no e-mail address, credentials or machine identifiers. |
| Local path in the frozen protocol file | `04_CODE/configs/protocol.yaml` keeps its original first comment, which names the author's original Windows project folder (no user name). See `PROTOCOL_PATH_COMMENT.md` for why it was not edited. |
