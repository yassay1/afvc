# Sync current working tree (plus built frontend/dist) to ECS.
# Does not upload .env, keys, raw workorders, or venvs.
#
# Usage:
#   cd frontend; npm ci; npm run build; cd ..
#   .\deploy\sync-to-server.ps1 -Remote "user@YOUR_ECS_IP" -RemotePath "/opt/afvc"
#
# Requires OpenSSH scp/rsync-compatible client. Prefer rsync if available.

param(
    [Parameter(Mandatory = $true)]
    [string]$Remote,
    [string]$RemotePath = "/opt/afvc",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$excludeFile = Join-Path $PSScriptRoot "rsync-exclude.txt"
$dist = Join-Path $RepoRoot "frontend\dist"
if (-not (Test-Path $dist)) {
    throw "frontend/dist missing. Run: cd frontend; npm ci; npm run build"
}

$rsync = Get-Command rsync -ErrorAction SilentlyContinue
if ($rsync) {
    & rsync -avz --delete `
        --exclude-from=$excludeFile `
        --exclude ".env" `
        --exclude "backend/data/raw/*" `
        --include "backend/data/raw/.gitkeep" `
        --include "frontend/dist/***" `
        --exclude "frontend/node_modules" `
        "$RepoRoot/" "${Remote}:${RemotePath}/"
} else {
    Write-Host "rsync not found; using tar+scp (no remote delete)."
    $staging = Join-Path $env:TEMP ("afvc-deploy-" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Path $staging | Out-Null
    try {
        $robocopyArgs = @(
            $RepoRoot, $staging, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np",
            "/XD", ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "key",
            "/XF", ".env", "*.xlsx", "*.xls", "*.pem", "*.key"
        )
        & robocopy @robocopyArgs | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed with code $LASTEXITCODE" }
        $rawDest = Join-Path $staging "backend\data\raw"
        if (Test-Path $rawDest) {
            Get-ChildItem $rawDest -File | Where-Object { $_.Name -ne ".gitkeep" } | Remove-Item -Force
        }
        $archive = Join-Path $env:TEMP "afvc-deploy.tgz"
        if (Test-Path $archive) { Remove-Item $archive -Force }
        tar -czf $archive -C $staging .
        scp $archive "${Remote}:/tmp/afvc-deploy.tgz"
        ssh $Remote "mkdir -p '$RemotePath' && tar -xzf /tmp/afvc-deploy.tgz -C '$RemotePath' && rm -f /tmp/afvc-deploy.tgz"
    }
    finally {
        Remove-Item -Recurse -Force $staging -ErrorAction SilentlyContinue
    }
}

Write-Host "Synced to ${Remote}:${RemotePath}"
Write-Host "On server: write .env, docker compose up -d, venv+pip, systemctl restart afvc, manage_user create"
