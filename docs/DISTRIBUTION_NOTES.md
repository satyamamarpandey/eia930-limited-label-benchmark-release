# Distribution notes

This repository is a clean distribution snapshot with a single initial commit. The development history of the research, the reviewer correspondence, the author's private declarations and the audit of the writing process are kept in separate private records and are not part of this repository.

* Code, configuration, saved results, data reports, the frozen protocol and its amendment history are byte-identical to the versions that were tested; only the documentation files were edited (repository name, EIA wording, this note).
* The frozen `04_CODE/configs/protocol.yaml` is unchanged, including its first comment (see `PROTOCOL_PATH_COMMENT.md`); its hash `0dd2e911745867f7b476eaddf4d404d6cd48c6f1afa5474cc4d4004623db2122` is recorded in the saved run manifest.
* The folder names (`03_DATA`, `04_CODE`, `05_RESULTS`, `06_AUDIT`, `07_REPRODUCTION`) are kept because the frozen code resolves its paths from them; renaming them would change frozen code and require a full re-verification.
* Raw EIA files are not included; `04_CODE/scripts/download_data.py` retrieves and verifies them.
