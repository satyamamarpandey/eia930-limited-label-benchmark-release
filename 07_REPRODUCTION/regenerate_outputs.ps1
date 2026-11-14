# Regenerate every derived output (source audit, tables, key numbers, exploratory refit, figures, extra baseline rows)
# from 05_RESULTS\final\raw and report which files changed. Does NOT re-run the 625-cell experiment (see rebuild_experiment.ps1).
#   .\regenerate_outputs.ps1 [-Python <python.exe>]
param([string]$Python = "")
. "$PSScriptRoot\_common.ps1"
$py = Resolve-Python $Python
Step "source data hashes" { Test-SourceData }
function Snapshot { $h = @{}; foreach ($d in "03_DATA","05_RESULTS") { Get-ChildItem (Join-Path $Root $d) -Recurse -File |
    Where-Object { ($_.FullName -notmatch '\\raw\\' -or $_.FullName -match '05_RESULTS\\final\\raw\\(runs_|event_|injection)') -and $_.FullName -notmatch '05_RESULTS\\figures\\.*\.pdf$' } |
    ForEach-Object { $h[$_.FullName.Substring($Root.Length+1)] = (Get-FileHash $_.FullName -Algorithm SHA256).Hash } }; $h }
$before = Snapshot
Push-Location $Code
try {
    Step "source audit" { & $py scripts\run_source_audit.py | Out-Null }
    Step "analysis tables and key numbers" { & $py scripts\analyze.py }
    Step "post-hoc exploratory SWPP refit" { & $py scripts\exploratory_swpp.py | Out-Null }
    Step "analysis tables incl. exploratory keys" { & $py scripts\analyze.py }
    Step "figures" { & $py scripts\make_figures.py }
    Step "labels-only baseline rows for the main table" { & $py scripts\labels_only_main_rows.py | Out-Null }
}
finally { Pop-Location }
$after = Snapshot
$new = @($after.Keys | Where-Object { -not $before.ContainsKey($_) })
$changed = @($after.Keys | Where-Object { $before.ContainsKey($_) -and $before[$_] -ne $after[$_] })
if ($new.Count) { Write-Host "$($new.Count) files were created (not shipped):"; $new | ForEach-Object { Write-Host "  $_" } }
# figure PDFs are not compared byte-wise: their drawing content is identical, but embedded-font bytes can differ between environments; the PNGs and *_data.csv are compared instead
if ($changed.Count -eq 0) { Write-Host "All $($after.Count - $new.Count) shipped derived files are byte-identical after regeneration." -ForegroundColor Green }
else { Write-Warning "$($changed.Count) files differ from the shipped versions:"; $changed | ForEach-Object { Write-Host "  $_" } }
