"""Download the two EIA-930 BALANCE 2024 six-month files and verify their SHA-256 values (standard library only).

    python 04_CODE/scripts/download_data.py

Files are written to 03_DATA/raw/ (never modified afterwards; they are not stored in this repository).
The expected SHA-256 values are in 03_DATA/SHA256SUMS.txt. EIA may revise published data: if a hash differs the script
stops, keeps the file under a .mismatch suffix, and the results of this repository cannot be expected to reproduce
exactly for that file.
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "03_DATA"
BASE = "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    expected = {}
    for line in (DATA / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        h, rel = line.split(None, 1)
        expected[rel.strip().lstrip("*")] = h
    status = 0
    for rel, h in expected.items():
        dest = DATA / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and sha256(dest) == h:
            print(f"OK (already present)  {rel}")
            continue
        url = BASE + Path(rel).name
        print(f"downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research reproduction)"})
        tmp = dest.with_suffix(".part")
        with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as fh:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
        got = sha256(tmp)
        if got == h:
            tmp.replace(dest)
            print(f"OK  {rel}  {got}")
        else:
            tmp.replace(dest.with_suffix(".mismatch"))
            print(f"SHA-256 MISMATCH for {rel}: got {got}, expected {h}", file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
