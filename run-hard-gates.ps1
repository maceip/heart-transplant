param(
    [string]$ArtifactDir = "",
    [string]$GoldSet = ""
)

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $repoRoot "backend\.venv-win\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
}
$harness = "C:\Users\mac\Documents\Codex\2026-04-22-github-plugin-github-openai-curated-you\heart_transplant_private\run_private_phase_gates.py"

if (-not (Test-Path $pythonExe)) {
    Write-Error "Missing Python executable: $pythonExe"
    exit 1
}

if (-not (Test-Path $harness)) {
    Write-Error "Missing private gate harness: $harness"
    exit 1
}

$args = @($harness, "--repo-root", $repoRoot)
if ($ArtifactDir) {
    $args += @("--artifact-dir", $ArtifactDir)
}
if ($GoldSet) {
    $args += @("--gold-set", $GoldSet)
}

& $pythonExe @args
exit $LASTEXITCODE
