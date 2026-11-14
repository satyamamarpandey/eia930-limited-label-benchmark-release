# The first comment of the frozen protocol file

`04_CODE/configs/protocol.yaml` is the frozen protocol v1.1 configuration. Its second line is a comment stating that paths are relative to the project root and naming the author's original Windows project folder. The name contains no user name or other personal identifier.

The file is distributed **unchanged** (SHA-256 `0dd2e911745867f7b476eaddf4d404d6cd48c6f1afa5474cc4d4004623db2122`) because that hash is verified by the code and the tests:
* `run_experiment.py` records the configuration hash in every run manifest (`05_RESULTS/final/run_manifest.json`);
* `verify_full_reproduction.py` requires the reproduction's configuration hash to equal the original run's;
* `tests/test_experiment.py` asserts that the manifest hash equals the hash of the file on disk;
* `06_AUDIT/protocol/PROTOCOL_FREEZE_v1_1.json` records the frozen hash.

A copy without the comment would change the hash, so a reproduction would no longer match the recorded run manifest and these checks would fail, although no experimental parameter would differ. Removing the comment would also require changing recorded history. The comment is therefore left in place and documented here.
