# Create the Python environment from the pinned lockfile (Python 3.12.15 + 04_CODE\requirements.lock.txt).
#   .\setup_environment.ps1                      -> creates 04_CODE\.venv
#   .\setup_environment.ps1 -VenvDir C:\envs\p4  -> creates it elsewhere; then set $env:PAPER4_PYTHON or pass -Python
# Needs uv (https://docs.astral.sh/uv/). The environment is not part of the deliverable; clean.ps1 -IncludeVenv removes it.
param([string]$VenvDir = "")
. "$PSScriptRoot\_common.ps1"
if (-not $VenvDir) { $VenvDir = Join-Path $Code ".venv" }
$py = Join-Path $VenvDir "Scripts\python.exe"
Step "create environment in $VenvDir" { uv venv --python 3.12.15 $VenvDir }
Step "install pinned packages" { uv pip install --link-mode=copy --python $py -r (Join-Path $Code "requirements.lock.txt") }
& $py -c "import numpy, pandas, sklearn, scipy, matplotlib, pypdf, yaml, pytest; print('environment OK:', pandas.__version__, sklearn.__version__, numpy.__version__)"
if ($LASTEXITCODE -ne 0) {
    Write-Warning ("The packages are installed but could not be loaded. If the message says 'An Application Control policy " +
        "has blocked this file', Windows Smart App Control is blocking the compiled package files at this location " +
        "(observed on 2026-10-23 for drive D:). Create the environment on another drive, e.g. " +
        ".\setup_environment.ps1 -VenvDir `"$env:LOCALAPPDATA\Paper4_venv`", then set `$env:PAPER4_PYTHON to its python.exe. " +
        "See TROUBLESHOOTING.md.")
    exit 1
}
if ($VenvDir -ne (Join-Path $Code ".venv")) { Write-Host "Set:  `$env:PAPER4_PYTHON = `"$py`"" -ForegroundColor Yellow }
