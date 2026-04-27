param(
    [string]$Manifest = "docs/evals/trending-repos-2026-04-27.json",
    [string]$VendorRoot = "vendor/github-repos",
    [switch]$IncludeOptional,
    [switch]$Refresh,
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $repoRoot $Manifest
$vendorPath = Join-Path $repoRoot $VendorRoot

if (-not (Test-Path $manifestPath)) {
    throw "Missing manifest: $manifestPath"
}

$manifestData = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$repos = @($manifestData.repos)
if (-not $IncludeOptional) {
    $repos = @($repos | Where-Object { $_.beta_default -eq $true })
}
if ($Limit -gt 0) {
    $repos = @($repos | Select-Object -First $Limit)
}

New-Item -ItemType Directory -Force -Path $vendorPath | Out-Null

$results = @()
foreach ($repo in $repos) {
    $name = ($repo.full_name -replace "/", "__")
    $target = Join-Path $vendorPath $name
    if ((Test-Path $target) -and -not $Refresh) {
        $results += [pscustomobject]@{
            repo = $repo.full_name
            path = $target
            status = "exists"
            language = $repo.language
        }
        continue
    }
    if ((Test-Path $target) -and $Refresh) {
        git -C $target fetch --depth 1 origin
        git -C $target reset --hard origin/HEAD
        $status = "refreshed"
    } else {
        git clone --depth 1 --filter=blob:none $repo.url $target
        $status = "cloned"
    }
    if ($LASTEXITCODE -ne 0) {
        throw "git operation failed for $($repo.full_name)"
    }
    $results += [pscustomobject]@{
        repo = $repo.full_name
        path = $target
        status = $status
        language = $repo.language
    }
}

$results | ConvertTo-Json -Depth 4
