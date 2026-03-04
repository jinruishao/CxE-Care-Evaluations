param(
    [int]$Port = 8020,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $RepoRoot ".demo"
$PidFile = Join-Path $StateDir "backend.pid"
$StdOutLog = Join-Path $StateDir "backend-$Port.out.log"
$StdErrLog = Join-Path $StateDir "backend-$Port.err.log"

New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
Set-Location $RepoRoot

Write-Host "[demo] Repo: $RepoRoot"
Write-Host "[demo] Target port: $Port"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not installed or not in PATH."
}

if (-not $SkipInstall) {
    Write-Host "[demo] Installing Python dependencies (requirements.txt)..."
    python -m pip install -r requirements.txt | Out-Host
}

Write-Host "[demo] Clearing listeners on port $Port..."
Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

$env:PYTHONPATH = $RepoRoot
$env:APP_HOST = "127.0.0.1"
$env:APP_PORT = "$Port"
$env:CORS_ORIGINS = "https://jinruishao.github.io,http://localhost:$Port,http://127.0.0.1:$Port"

Write-Host "[demo] Starting backend..."
$proc = Start-Process -FilePath "python" `
    -ArgumentList @("-m", "uvicorn", "--app-dir", $RepoRoot, "backend.app:app", "--host", "127.0.0.1", "--port", "$Port") `
    -WorkingDirectory $RepoRoot `
    -PassThru `
    -RedirectStandardOutput $StdOutLog `
    -RedirectStandardError $StdErrLog

$proc.Id | Set-Content -Path $PidFile -Encoding UTF8

$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -Method GET -TimeoutSec 2
        $healthy = $true
        break
    }
    catch {
    }
}

if (-not $healthy) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    throw "Backend failed to become healthy. Check logs: $StdOutLog and $StdErrLog"
}

Write-Host "[demo] Backend is healthy: http://127.0.0.1:$Port/api/health"
Write-Host "[demo] Opening GitHub Pages frontend..."
Start-Process "https://jinruishao.github.io/CxE-Care-Evaluations/"

Write-Host ""
Write-Host "✅ Demo is ready"
Write-Host "- Frontend: https://jinruishao.github.io/CxE-Care-Evaluations/"
Write-Host "- Backend:  http://127.0.0.1:$Port"
Write-Host "- Stop:     .\\stop-demo.ps1 -Port $Port"
