$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$WebDir = Join-Path $Root "apps\web"

if (-not (Test-Path (Join-Path $WebDir ".env.local"))) {
    if (Test-Path (Join-Path $Root ".env.example")) {
        Copy-Item (Join-Path $Root ".env.example") (Join-Path $WebDir ".env.local")
        Write-Host "Created apps/web/.env.local from .env.example"
    }
}

Push-Location $WebDir
try {
    npm run dev
} finally {
    Pop-Location
}
