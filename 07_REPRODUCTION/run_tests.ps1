# Run the complete automated test suite (57 tests). Missing inputs are failures, not skips.
#   .\run_tests.ps1 [-Python <python.exe>]
param([string]$Python = "")
. "$PSScriptRoot\_common.ps1"
$py = Resolve-Python $Python
$env:GRIDBENCH_REQUIRE_ALL = "1"
Push-Location $Code
try { Step "pytest (strict: no skips allowed)" { & $py -m pytest tests -q -p no:cacheprovider -rs } }
finally { Pop-Location; Remove-Item Env:\GRIDBENCH_REQUIRE_ALL -ErrorAction SilentlyContinue }
