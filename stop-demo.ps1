param(
    [int]$Port = 8020
)

$ErrorActionPreference = "SilentlyContinue"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $RepoRoot ".demo"
$PidFile = Join-Path $StateDir "backend.pid"

Write-Host "[demo] Stopping backend on port $Port..."

if (Test-Path $PidFile) {
    $pidValue = Get-Content $PidFile | Select-Object -First 1
    if ($pidValue) {
        Stop-Process -Id ([int]$pidValue) -Force -ErrorAction SilentlyContinue
        Write-Host "[demo] Stopped PID from pid file: $pidValue"
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
        Write-Host "[demo] Stopped listener PID: $_"
    }

Start-Sleep -Seconds 1
$listeners = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
if ($listeners) {
    Write-Host "[demo] Port $Port is still in use."
} else {
    Write-Host "✅ [demo] Port $Port is clear."
}
