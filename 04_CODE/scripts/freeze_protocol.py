"""Protocol freeze records (06_AUDIT/protocol/PROTOCOL_FREEZE_v*.json).

History: this script wrote PROTOCOL_FREEZE_v1_0.json (before any test-period metric) and
PROTOCOL_FREEZE_v1_1.json (after the disclosed amendment) in the original build layout, where the
code lived in 03_CODE/ and the protocol in 02_RESEARCH_PROTOCOL/. Those records are never rewritten.

Default (check) mode: compares the current files with the hashes recorded in a freeze file and
reports which changed since the freeze. The configuration hash must be unchanged; other files
(the runner, path handling) were changed later for documented engineering reasons
(06_AUDIT/protocol/PROTOCOL_CHANGES.md) without changing any result.

Usage: python scripts/freeze_protocol.py [--freeze 06_AUDIT/protocol/PROTOCOL_FREEZE_v1_1.json]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))
from gridbench.config import load_config, project_paths  # noqa: E402

# original layout -> final folder layout
MOVED = {"03_CODE/": "04_CODE/", "02_RESEARCH_PROTOCOL/": "06_AUDIT/protocol/"}


def main():
    paths = project_paths(load_config())
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", default="06_AUDIT/protocol/PROTOCOL_FREEZE_v1_1.json")
    args = ap.parse_args()
    rec = json.loads((paths["root"] / args.freeze).read_text())
    rows, config_ok = [], None
    for rel, h in rec["files"].items():
        cur = rel
        for a, b in MOVED.items():
            cur = cur.replace(a, b)
        p = paths["root"] / cur
        now = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
        rows.append((rel, cur, "unchanged" if now == h else ("missing" if now is None else "changed")))
        if rel.endswith("configs/protocol.yaml"):
            config_ok = now == h == rec["protocol_config_sha256"]
    for r in rows:
        print(f"{r[2]:9s}  {r[0]}  ->  {r[1]}")
    print(f"frozen configuration unchanged: {config_ok}")
    sys.exit(0 if config_ok else 1)


if __name__ == "__main__":
    main()
