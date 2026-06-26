$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

function Test-Command($Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Host "[FAIL] $Name not found in PATH" -ForegroundColor Red
        return $false
    }
    Write-Host "[OK]   $Name -> $($cmd.Source)" -ForegroundColor Green
    return $true
}

function Test-Version($Label, $Command, $MinVersion) {
    try {
        $raw = & $Command 2>&1 | Select-Object -First 1
        Write-Host "[OK]   $Label : $raw" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[FAIL] $Label check failed: $_" -ForegroundColor Red
        return $false
    }
}

$ok = $true

Write-Host "`nLeadsGen setup verification`n" -ForegroundColor Cyan

$ok = (Test-Command "python") -and $ok
$ok = (Test-Command "node") -and $ok
$ok = (Test-Command "npm") -and $ok

if (Test-Command "python") {
    $ok = (Test-Version "Python" { python --version } "3.12") -and $ok
}
if (Test-Command "node") {
    $ok = (Test-Version "Node.js" { node --version } "20") -and $ok
}

$sqliteDb = Join-Path $Root "services\api\data\leadsgen.db"
$sqliteDir = Split-Path $sqliteDb -Parent
if (-not (Test-Path $sqliteDir)) {
    New-Item -ItemType Directory -Path $sqliteDir -Force | Out-Null
}
if (Test-Path $sqliteDb) {
    Write-Host "[OK]   SQLite database exists at services/api/data/leadsgen.db" -ForegroundColor Green
} else {
    Write-Host "[INFO] SQLite DB not created yet — run: cd services\api; alembic upgrade head" -ForegroundColor DarkYellow
}

if (Test-Command "redis-cli") {
    try {
        $pong = redis-cli ping 2>&1
        if ($pong -match "PONG") {
            Write-Host "[OK]   Redis responding (PONG)" -ForegroundColor Green
        } else {
            Write-Host "[WARN] redis-cli did not return PONG — start Redis before Celery" -ForegroundColor Yellow
            $ok = $false
        }
    } catch {
        Write-Host "[WARN] Redis check failed: $_" -ForegroundColor Yellow
        $ok = $false
    }
} else {
    Write-Host "[WARN] redis-cli not found — required for Celery worker/beat" -ForegroundColor Yellow
    $ok = $false
}

$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
    Write-Host "[OK]   .env present" -ForegroundColor Green
} else {
    Write-Host "[WARN] .env missing — copy .env.example to .env" -ForegroundColor Yellow
    $ok = $false
}

$webEnv = Join-Path $Root "apps\web\.env.local"
if (Test-Path $webEnv) {
    Write-Host "[OK]   apps/web/.env.local present" -ForegroundColor Green
} else {
    Write-Host "[WARN] apps/web/.env.local missing — set NEXT_PUBLIC_API_URL=http://localhost:8000" -ForegroundColor Yellow
}

$venv = Join-Path $Root "services\api\.venv"
if (Test-Path $venv) {
    Write-Host "[OK]   Python venv at services/api/.venv" -ForegroundColor Green
} else {
    Write-Host "[INFO] Python venv not created yet — run: cd services\api; python -m venv .venv" -ForegroundColor DarkYellow
}

$nodeModules = Join-Path $Root "apps\web\node_modules"
if (Test-Path $nodeModules) {
    Write-Host "[OK]   Frontend node_modules installed" -ForegroundColor Green
} else {
    Write-Host "[INFO] Frontend deps not installed — run: cd apps\web; npm install" -ForegroundColor DarkYellow
}

Write-Host ""
if ($ok) {
    Write-Host "Setup looks good. Next steps:" -ForegroundColor Green
    Write-Host "  cd services\api; alembic upgrade head; python scripts\seed.py"
    Write-Host "  uvicorn app.main:app --reload --port 8000"
    Write-Host "  cd apps\web; npm run dev"
    exit 0
}

Write-Host "Some checks failed or need attention — see warnings above." -ForegroundColor Yellow
exit 1
