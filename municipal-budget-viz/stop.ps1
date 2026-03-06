$ErrorActionPreference = "SilentlyContinue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "==> Stopping Next.js (port 3000)..."
$conn = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    Stop-Process -Id $conn.OwningProcess -Force
    Write-Host "    Killed PID $($conn.OwningProcess)"
} else {
    Write-Host "    Nothing listening on port 3000"
}

Write-Host "==> Stopping docker containers..."
docker compose down

Write-Host "==> Done."
