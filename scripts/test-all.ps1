$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "Running backend tests..."
Push-Location (Join-Path $Root "services\api")
try {
    if (Test-Path ".\.venv\Scripts\Activate.ps1") {
        . .\.venv\Scripts\Activate.ps1
    }
    pytest tests/ -v
} finally {
    Pop-Location
}

Write-Host "Running frontend lint and build..."
Push-Location (Join-Path $Root "apps\web")
try {
    npm run lint
    npm run build
} finally {
    Pop-Location
}

Write-Host "All checks passed."
