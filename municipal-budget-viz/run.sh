#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CLEAR=false
for arg in "$@"; do
  [[ "$arg" == "--clear" ]] && CLEAR=true
done

# ---------------------------------------------------------------------------
# --clear: wipe DB volume, node_modules, prisma migrations, etl .env
# ---------------------------------------------------------------------------
if $CLEAR; then
  echo "==> [clear] Stopping and removing containers + volumes..."
  docker compose down -v --remove-orphans 2>/dev/null || true

  echo "==> [clear] Removing Prisma migrations..."
  rm -rf web/prisma/migrations

  echo "==> [clear] Removing node_modules and Next.js cache..."
  rm -rf web/node_modules web/.next

  echo "==> [clear] Done clearing. Starting fresh..."
fi

# ---------------------------------------------------------------------------
# Start postgres
# ---------------------------------------------------------------------------
echo "==> Starting postgres..."
docker compose up -d postgres

echo "==> Waiting for postgres to be healthy..."
until docker compose exec -T postgres pg_isready -U budget -d municipal_budget -q; do
  sleep 1
done

# ---------------------------------------------------------------------------
# Web: install deps, migrate, generate client
# ---------------------------------------------------------------------------
cd web

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "==> Created web/.env from example"
fi

echo "==> Installing web dependencies..."
npm install --prefer-offline 2>/dev/null || npm install

echo "==> Running Prisma migration..."
npx prisma migrate dev --name init

echo "==> Generating Prisma client..."
npx prisma generate

cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# ETL: install deps, run pipeline
# ---------------------------------------------------------------------------
cd etl

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "==> Created etl/.env from example"
fi

echo "==> Installing ETL dependencies..."
pip install -r requirements.txt -q

echo "==> Running ETL on budget_past/..."
python pipeline.py --input ../../budget_past/ --type auto

echo "==> Running ETL on budget_plan/..."
python pipeline.py --input ../../budget_plan/ --type auto

cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Start Next.js dev server
# ---------------------------------------------------------------------------
echo ""
echo "==> Starting Next.js dev server at http://localhost:3000 ..."
echo "    (Press Ctrl+C or run stop.sh to stop)"
echo ""
cd web && npm run dev
