# Rebuild the final experiment (all 625 cells) from the raw EIA-930 files.
#   .\rebuild_experiment.ps1 [-Python <python.exe>] [-Workers 2] [-BatchSize 25] [-KeepRun]
# If 05_RESULTS\final exists (normal case), the experiment is re-executed into 05_RESULTS\_reproduction_run with the
# memory-bounded, checkpointed runner and compared file by file with 05_RESULTS\final, which is never modified.
# The report is written to 06_AUDIT\reproducibility\full_reproduction_report.{md,json}. After a PASS the
# reproduction folder is deleted (it duplicates the final outputs) unless -KeepRun is given.
# An interrupted run resumes from its checkpoints when the same command is repeated.
# If 05_RESULTS\final does not exist, the experiment is run into 05_RESULTS\final and all tables, key numbers,
# figures and manuscript macros are regenerated from it.
# Runtime: about 13 minutes with 2 workers on a 12-thread laptop CPU; about 1.5 GB RAM.
param([string]$Python = "", [int]$Workers = 2, [int]$BatchSize = 25, [switch]$KeepRun)
. "$PSScriptRoot\_common.ps1"
$py = Resolve-Python $Python
Step "verify source data" { Test-SourceData }
Push-Location $Code
try {
    $final = Join-Path $Root "05_RESULTS\final\run_manifest.json"
    if (Test-Path $final) {
        $rel = "05_RESULTS/_reproduction_run"
        if (-not (Test-Path (Join-Path $Root "$rel\run_manifest.json"))) {
            Step "run 625 cells into $rel" { & $py scripts\run_experiment.py --stage final --outdir $rel --workers $Workers --batch-size $BatchSize }
        }
        Step "compare with 05_RESULTS\final" { & $py scripts\verify_full_reproduction.py --repro $rel }
        if (-not $KeepRun) { Remove-Item -Recurse -Force (Join-Path $Root $rel); Write-Host "removed $rel (report kept)" }
    } else {
        Step "run 625 cells into 05_RESULTS\final" { & $py scripts\run_experiment.py --stage final --workers $Workers --batch-size $BatchSize }
        Step "analysis tables and key numbers" { & $py scripts\analyze.py }
        Step "post-hoc exploratory SWPP refit" { & $py scripts\exploratory_swpp.py }
        Step "analysis tables incl. exploratory keys" { & $py scripts\analyze.py }
        Step "figures" { & $py scripts\make_figures.py }
        Step "manuscript macros and tables" { & $py scripts\make_manuscript_assets.py }
    }
}
finally { Pop-Location }
Write-Host "Done. See 06_AUDIT\reproducibility\full_reproduction_report.md" -ForegroundColor Green
