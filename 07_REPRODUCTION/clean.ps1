# Remove temporary files created by the scripts (LaTeX build folder, Python caches, reproduction/test runs).
#   .\clean.ps1 [-IncludeVenv]     (-IncludeVenv also removes 04_CODE\.venv)
param([switch]$IncludeVenv)
. "$PSScriptRoot\_common.ps1"
$targets = @("05_RESULTS\_reproduction_run", "05_RESULTS\_resumption_test")
if ($IncludeVenv) { $targets += "04_CODE\.venv" }
foreach ($t in $targets) {
    $p = Join-Path $Root $t
    if (Test-Path $p) { Remove-Item -Recurse -Force $p; Write-Host "removed $t" }
}
Get-ChildItem $Code -Recurse -Directory -Force -Include "__pycache__", ".pytest_cache" |
    Where-Object { $_.FullName -notlike "*\.venv\*" } | ForEach-Object { Remove-Item -Recurse -Force $_.FullName; Write-Host "removed $($_.FullName.Substring($Root.Length + 1))" }
