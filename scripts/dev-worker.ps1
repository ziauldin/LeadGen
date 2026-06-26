$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Root "services\api"

if (Test-Path (Join-Path $Root ".env")) {
    Get-Content (Join-Path $Root ".env") | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

Push-Location $ApiDir
try {
    if (Test-Path ".\.venv\Scripts\Activate.ps1") {
        . .\.venv\Scripts\Activate.ps1
    }
    celery -A app.core.celery_app worker -l info
} finally {
    Pop-Location
}
