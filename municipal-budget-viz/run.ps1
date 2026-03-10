$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
$Clear        = $false
$SkipEtl      = $false
$Municipality = ""
$Year         = 2025
$ShowHelp     = $false

$i = 0
while ($i -lt $args.Count) {
    switch ($args[$i]) {
        { $_ -in "--clear", "-clear", "-Clear" }       { $Clear = $true }
        { $_ -in "--skip-etl", "-skip-etl" }           { $SkipEtl = $true }
        { $_ -in "--municipality", "-municipality" }    { $i++; $Municipality = $args[$i] }
        { $_ -in "--year", "-year" }                    { $i++; $Year = [int]$args[$i] }
        { $_ -in "--help", "-help", "-h" }              { $ShowHelp = $true }
    }
    $i++
}

if ($ShowHelp) {
    Write-Host @"
Usage: .\run.ps1 [OPTIONS]

Options:
  --clear              Wipe DB volume, node_modules, migrations and start fresh
  --skip-etl           Skip ETL (just start web server; DB already has data)
  --municipality NAME  Discover PDFs from Diavgeia for NAME (e.g. "Αχαρνές")
  --year YEAR          Year for Diavgeia search (default: 2025)
  -h, --help           Show this help

Examples:
  .\run.ps1                               # normal start: ETL local PDFs + web
  .\run.ps1 --skip-etl                    # DB already loaded, just open web
  .\run.ps1 --municipality "Αχαρνές"      # auto-discover from Diavgeia
  .\run.ps1 --clear                       # wipe everything and rebuild
"@
    exit 0
}

# ---------------------------------------------------------------------------
# --clear: wipe DB volume, node_modules, prisma migrations
# ---------------------------------------------------------------------------
if ($Clear) {
    Write-Host "==> [clear] Stopping containers + volumes..."
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

Write-Host "==> Waiting for postgres to be ready..."
do {
    Start-Sleep -Seconds 1
    docker compose exec -T postgres pg_isready -U budget -d municipal_budget -q 2>$null | Out-Null
} until ($LASTEXITCODE -eq 0)
Write-Host "    postgres is ready."

# ---------------------------------------------------------------------------
# Web: install deps, migrate, generate client
# ---------------------------------------------------------------------------
Set-Location "$ScriptDir\web"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "==> Created web\.env from example"
}

if (-not (Test-Path "node_modules")) {
    Write-Host "==> Installing web dependencies..."
    npm install
} else {
    Write-Host "==> Web deps already installed (skipping npm install)"
}

Write-Host "==> Running Prisma migrations..."
$migrationsExist = (Test-Path "prisma\migrations") -and
                   ((Get-ChildItem "prisma\migrations" -ErrorAction SilentlyContinue).Count -gt 0)
if ($migrationsExist) {
    npx prisma migrate deploy
} else {
    npx prisma migrate dev --name init
}

Write-Host "==> Generating Prisma client..."
npx prisma generate

Set-Location $ScriptDir

# ---------------------------------------------------------------------------
# Ollama health check
# ---------------------------------------------------------------------------
Write-Host "==> Checking Ollama server..."
try {
    $null = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -ErrorAction Stop
    Write-Host "    Ollama is running."
} catch {
    Write-Host "ERROR: Ollama is not running. Start it with: ollama serve"
    Write-Host "       Then pull the model: ollama pull qwen2.5:7b"
    exit 1
}

# ---------------------------------------------------------------------------
# ETL
# ---------------------------------------------------------------------------
if (-not $SkipEtl) {
    Set-Location "$ScriptDir\etl"

    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "==> Created etl\.env from example"
    }

    Write-Host "==> Installing ETL dependencies..."
    pip install -r requirements.txt -q

    if ($Municipality -ne "") {
        Write-Host "==> Running ETL via Diavgeia for municipality='$Municipality' year=$Year ..."
        python pipeline.py --municipality $Municipality --year $Year
    } else {
        Write-Host "==> Running ETL on budget_past\..."
        python pipeline.py --input ..\..\budget_past\ --type auto

        Write-Host "==> Running ETL on budget_plan\..."
        python pipeline.py --input ..\..\budget_plan\ --type auto
    }

    Set-Location $ScriptDir
} else {
    Write-Host "==> [skip-etl] Skipping ETL pipeline."
}

# ---------------------------------------------------------------------------
# Start Next.js dev server
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================"
Write-Host "  http://localhost:3000"
Write-Host "  Press Ctrl+C to stop."
Write-Host "============================================================"
Write-Host ""
Set-Location "$ScriptDir\web"
npm run dev
