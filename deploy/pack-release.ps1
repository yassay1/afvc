# Build a release tarball from the current working tree (no secrets / raw / venvs).
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$OutFile = (Join-Path $env:TEMP "afvc-release.tgz")
)

$ErrorActionPreference = "Stop"
$dist = Join-Path $RepoRoot "frontend\dist\index.html"
if (-not (Test-Path $dist)) {
    throw "frontend/dist missing. Run: cd frontend; npm ci; npm run build"
}

$staging = Join-Path $env:TEMP ("afvc-pack-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $staging | Out-Null
try {
    & robocopy $RepoRoot $staging /E /NFL /NDL /NJH /NJS /nc /ns /np `
        /XD .git .venv venv node_modules __pycache__ .pytest_cache .ruff_cache .idea .vscode key agent-transcripts terminals .planning `
        /XF .env *.xlsx *.xls *.pem *.key *.p12 *.pfx | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed: $LASTEXITCODE" }

    $raw = Join-Path $staging "backend\data\raw"
    if (Test-Path $raw) {
        Get-ChildItem $raw -File -Force | Where-Object { $_.Name -ne ".gitkeep" } | Remove-Item -Force
    }
    foreach ($pattern in @("*AccessKey*", "*access_key*", "id_rsa*", "id_ed25519*")) {
        Get-ChildItem $staging -Recurse -Force -Filter $pattern -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }

    if (Test-Path $OutFile) { Remove-Item $OutFile -Force }
    tar -czf $OutFile -C $staging .
    Write-Host "Wrote $OutFile"
    Get-Item $OutFile | Select-Object FullName, Length, LastWriteTime
}
finally {
    Remove-Item -Recurse -Force $staging -ErrorAction SilentlyContinue
}
