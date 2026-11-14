# Shared helpers for the 07_REPRODUCTION scripts (dot-sourced; not run directly).
# Every path is derived from this folder, so the project folder can be copied or moved as a whole.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Code = Join-Path $Root "04_CODE"
$env:PYTHONDONTWRITEBYTECODE = "1"   # keep __pycache__ out of the project folder

function Resolve-Python([string]$Python) {
    # order: -Python argument, PAPER4_PYTHON environment variable, 04_CODE\.venv
    if ($Python) { return (Resolve-Path $Python).Path }
    if ($env:PAPER4_PYTHON) { return $env:PAPER4_PYTHON }
    $p = Join-Path $Code ".venv\Scripts\python.exe"
    if (Test-Path $p) { return $p }
    throw "No Python environment found. Run .\setup_environment.ps1 first, or pass -Python <path to python.exe>."
}

function Step([string]$Name, [scriptblock]$Command) {
    Write-Host "== $Name" -ForegroundColor Cyan
    $global:LASTEXITCODE = 0
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Step failed: $Name (exit code $LASTEXITCODE)" }
}

function Test-SourceData {
    # the two raw EIA-930 files must match the recorded SHA-256 values exactly
    $sums = Get-Content (Join-Path $Root "03_DATA\SHA256SUMS.txt")
    foreach ($line in $sums) {
        $h, $rel = $line -split "\s+", 2
        $f = Join-Path (Join-Path $Root "03_DATA") $rel
        if (-not (Test-Path $f)) { throw "Missing $f (see 03_DATA\PROVENANCE.md for the download source)" }
        $a = (Get-FileHash $f -Algorithm SHA256).Hash.ToLower()
        if ($a -ne $h) { throw "SHA-256 mismatch for $rel : $a (expected $h)" }
        Write-Host "OK  $rel  $a"
    }
}
