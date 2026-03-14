#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------
CLEAR=false
SKIP_ETL=false
MUNICIPALITY=""
YEAR=2025

usage() {
  cat <<EOF
Usage: ./run.sh [OPTIONS]

Options:
  --clear              Wipe DB volume, node_modules, migrations and start fresh
  --skip-etl           Skip ETL (just start web server; DB already has data)
  --municipality NAME  Discover PDFs from Diavgeia for NAME (Greek, e.g. "Αχαρνές")
  --year YEAR          Year for Diavgeia search (default: 2025)
  -h, --help           Show this help

Examples:
  ./run.sh                              # normal start: ETL local PDFs + web
  ./run.sh --skip-etl                   # DB already loaded, just open web
  ./run.sh --municipality "Αχαρνές"     # auto-discover from Diavgeia
  ./run.sh --clear                      # wipe everything and rebuild
EOF
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clear)       CLEAR=true ;;
    --skip-etl)    SKIP_ETL=true ;;
    --municipality) MUNICIPALITY="$2"; shift ;;
    --year)        YEAR="$2"; shift ;;
    -h|--help)     usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
  shift
done

# ---------------------------------------------------------------------------
# --clear: wipe DB volume, node_modules, prisma migrations
# ---------------------------------------------------------------------------
if $CLEAR; then
  echo "==> [clear] Stopping containers + volumes..."
  docker compose down -v --remove-orphans 2>/dev/null || true

  echo "==> [clear] Removing Prisma migrations..."
  rm -rf web/prisma/migrations

  echo "==> [clear] Removing node_modules and Next.js cache..."
  rm -rf web/node_modules web/.next

  echo "==> [clear] Done. Starting fresh..."
fi

# ---------------------------------------------------------------------------
# Start postgres
# ---------------------------------------------------------------------------
echo "==> Starting postgres..."
docker compose up -d postgres

echo "==> Waiting for postgres to be ready..."
until docker compose exec -T postgres pg_isready -U budget -d municipal_budget -q; do
  sleep 1
done
echo "    postgres is ready."

# ---------------------------------------------------------------------------
# Web: install deps, migrate, generate client
# ---------------------------------------------------------------------------
cd web

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "==> Created web/.env from example"
fi

if [[ ! -d node_modules ]]; then
  echo "==> Installing web dependencies..."
  npm install
else
  echo "==> Web deps already installed (skipping npm install)"
fi

echo "==> Running Prisma migrations..."
if [[ -d prisma/migrations && "$(ls -A prisma/migrations 2>/dev/null)" ]]; then
  npx prisma migrate deploy
else
  npx prisma migrate dev --name init
fi

echo "==> Generating Prisma client..."
npx prisma generate

cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# ETL
# ---------------------------------------------------------------------------
if ! $SKIP_ETL; then
  cd etl

  if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "==> Created etl/.env from example"
  fi

  # Check whether Claude (Haiku) or Ollama will be used
  if grep -qE '^ANTHROPIC_API_KEY=.+' .env 2>/dev/null; then
    echo "==> ANTHROPIC_API_KEY detected — using Claude Haiku (skipping Ollama check)."
  else
    echo "==> Checking Ollama server (no ANTHROPIC_API_KEY found)..."
    if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
      echo "ERROR: Ollama is not running. Start it with: ollama serve"
      echo "       Then pull the model: ollama pull qwen2.5:7b"
      echo "       Or set ANTHROPIC_API_KEY in etl/.env to use Claude Haiku instead."
      exit 1
    fi
    echo "    Ollama is running."
  fi

  echo "==> Installing ETL dependencies..."
  pip install -r requirements.txt -q

  if [[ -n "$MUNICIPALITY" ]]; then
    echo "==> Running ETL via Diavgeia for municipality='$MUNICIPALITY' year=$YEAR ..."
    python pipeline.py --municipality "$MUNICIPALITY" --year "$YEAR"
  else
    echo "==> Running ETL on budget_past/..."
    python pipeline.py --input ../../budget_past/ --type auto

    echo "==> Running ETL on budget_plan/..."
    python pipeline.py --input ../../budget_plan/ --type auto
  fi

  cd "$SCRIPT_DIR"
else
  echo "==> [skip-etl] Skipping ETL pipeline."
fi

# ---------------------------------------------------------------------------
# Start Next.js dev server
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  http://localhost:3000"
echo "  Press Ctrl+C to stop."
echo "============================================================"
echo ""
cd web && npm run dev
