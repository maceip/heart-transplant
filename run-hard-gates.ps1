param(
    [string]$ArtifactDir = "",
    [string]$GoldSet = "",
    [string]$HoldoutArtifactDir = "",
    [string]$HoldoutGoldSet = ""
)

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $repoRoot "backend\.venv-win\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
}

if (-not (Test-Path $pythonExe)) {
    Write-Error "Missing Python executable: $pythonExe"
    exit 1
}

if (-not $ArtifactDir) {
    Write-Error "ArtifactDir is required. Run ingest-local/classify first, then pass --ArtifactDir <artifact-directory>."
    exit 1
}

if (-not $GoldSet) {
    $GoldSet = Join-Path $repoRoot "docs\evals\gold_block_benchmark.json"
}
if (-not $HoldoutGoldSet) {
    $defaultHoldoutGold = Join-Path $repoRoot "docs\evals\gold_block_benchmark_holdout.json"
    if (Test-Path $defaultHoldoutGold) {
        $HoldoutGoldSet = $defaultHoldoutGold
    }
}

function Invoke-Gate {
    param(
        [string]$Name,
        [string[]]$Args
    )

    Write-Host "==> $Name"
    & $pythonExe @Args
    if ($LASTEXITCODE -ne 0) {
        Write-Error "$Name failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

Push-Location (Join-Path $repoRoot "backend")
try {
    Invoke-Gate "pytest" @("-m", "pytest")
    Invoke-Gate "program-surface" @("-m", "heart_transplant.cli", "program-surface")
    Invoke-Gate "validate-gates" @("-m", "heart_transplant.cli", "validate-gates", "--artifact-dir", $ArtifactDir)

    $maximizeArgs = @("-m", "heart_transplant.cli", "maximize-gates", $ArtifactDir, "--gold-set", $GoldSet)
    if ($HoldoutArtifactDir) {
        $maximizeArgs += @("--holdout-artifact-dir", $HoldoutArtifactDir)
        if ($HoldoutGoldSet) {
            $maximizeArgs += @("--holdout-gold-set", $HoldoutGoldSet)
        }
    }
    Invoke-Gate "maximize-gates" $maximizeArgs
} finally {
    Pop-Location
}

Write-Host "All in-repo hard gates passed."
exit 0
