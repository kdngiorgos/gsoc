param(
    [switch]$Clear
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# ---------------------------------------------------------------------------
# --Clear: wipe DB volume, node_modules, prisma migrations
# ---------------------------------------------------------------------------
if ($Clear) {
    Write-Host "==> [clear] Stopping and removing containers + volumes..."
    docker compose down -v --remove-orphans 2>$null

    Write-Host "==> [clear] Removing Prisma migrations..."
    if (Test-Path "web\prisma\migrations") { Remove-Item -Recurse -Force "web\prisma\migrations" }

    Write-Host "==> [clear] Removing node_modules and Next.js cache..."
    if (Test-Path "web\node_modules") { Remove-Item -Recurse -Force "web\node_modules" }
    if (Test-Path "web\.next")        { Remove-Item -Recurse -Force "web\.next" }

    Write-Host "==> [clear] Done. Starting fresh..."
}

# ---------------------------------------------------------------------------
# Start postgres
# ---------------------------------------------------------------------------
Write-Host "==> Starting postgres..."
docker compose up -d postgres

Write-Host "==> Waiting for postgres to be healthy..."
do {
    Start-Sleep -Seconds 1
    $ready = docker compose exec -T postgres pg_isready -U budget -d municipal_budget -q 2>$null
} until ($LASTEXITCODE -eq 0)

# ---------------------------------------------------------------------------
# Web: install deps, migrate, generate client
# ---------------------------------------------------------------------------
Set-Location "$ScriptDir\web"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "==> Created web\.env from example"
}

Write-Host "==> Installing web dependencies..."
npm install

Write-Host "==> Running Prisma migration..."
npx prisma migrate dev --name init

Write-Host "==> Generating Prisma client..."
npx prisma generate

Set-Location $ScriptDir

# ---------------------------------------------------------------------------
# ETL: install deps, run pipeline
# ---------------------------------------------------------------------------
Set-Location "$ScriptDir\etl"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "==> Created etl\.env from example"
}

Write-Host "==> Installing ETL dependencies..."
pip install -r requirements.txt -q

Write-Host "==> Running ETL on budget_past\..."
python pipeline.py --input ..\..\budget_past\ --type auto

Write-Host "==> Running ETL on budget_plan\..."
python pipeline.py --input ..\..\budget_plan\ --type auto

Set-Location $ScriptDir

# ---------------------------------------------------------------------------
# Start Next.js dev server
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "==> Starting Next.js dev server at http://localhost:3000 ..."
Write-Host "    (Press Ctrl+C or run stop.ps1 to stop)"
Write-Host ""
Set-Location "$ScriptDir\web"
npm run dev
