#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Stopping Next.js (port 3000)..."
if command -v fuser &>/dev/null; then
  fuser -k 3000/tcp 2>/dev/null || true
elif command -v lsof &>/dev/null; then
  lsof -ti tcp:3000 | xargs kill -9 2>/dev/null || true
else
  # Windows / Git Bash fallback
  PID=$(netstat -ano 2>/dev/null | grep ":3000 " | grep LISTENING | awk '{print $5}' | head -1)
  [[ -n "$PID" ]] && taskkill //F //PID "$PID" 2>/dev/null && echo "Killed PID $PID" || true
fi

echo "==> Stopping docker containers..."
docker compose down 2>/dev/null || true

echo "==> Done."
