# Environment requirements

| Component | Used for the reported results | Notes |
|---|---|---|
| OS | Windows 11 Home (10.0.26200), x86-64 | Python stages are OS-independent; the `*.ps1` wrappers need Windows PowerShell 5.1 or later |
| CPU | 12 logical threads, no GPU | No GPU code |
| RAM | 16 GB total | With 2 workers the Python processes together used about 1.3–1.5 GB |
| Disk | ~1.5 GB free | Project folder ~270 MB; a full reproduction run adds ~120 MB temporarily (deleted after the comparison); the environment ~330 MB |
| Python | 3.12.15 (installed by uv) | |
| uv | 0.13.0 | Creates the environment and installs the lockfile |
| Packages | numpy 2.5.4, pandas 3.1.0, scikit-learn 1.9.1, scipy 1.18.1, matplotlib 3.11.2, pyyaml 6.0.3, pytest 9.1.1, pypdf 6.21.2, pillow 13.0.0 | Exact pins: `04_CODE/requirements.lock.txt` |
| Threads | The runner sets `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1` | Keeps results independent of BLAS threading |
| Network | Not needed, except to create the environment without a uv cache, and for the optional online citation check (`citation_audit.py` without `--offline` queries api.crossref.org) | |

Bitwise agreement has been verified only on this machine and software stack (three full reruns). On different CPUs, BLAS builds or package versions, small floating-point differences are possible. `verify_full_reproduction.py` reports them against a tolerance (rtol 1e-9) and with an exact-equality flag. Reproduction on a second machine has **not** been done.
