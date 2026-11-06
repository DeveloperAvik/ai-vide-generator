#!/usr/bin/env bash
# Starts API (8000) and dashboard (3000) locally. Logs in .run/. Docker users: make docker-up
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p .run
[ -f .env ] || { echo "run scripts/setup.sh first"; exit 1; }
set -a; . ./.env; set +a
if [ -f .run/api.pid ] && kill -0 "$(cat .run/api.pid)" 2>/dev/null; then echo "already running"; exit 0; fi
cd "$ROOT/backend"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$ROOT/.run/api.log" 2>&1 &
echo $! > "$ROOT/.run/api.pid"
cd "$ROOT/frontend"
[ -d .next ] || npm run build >/dev/null
NEXT_PUBLIC_API_URL=http://localhost:8000 nohup npm start -- -H 127.0.0.1 > "$ROOT/.run/web.log" 2>&1 &
echo $! > "$ROOT/.run/web.pid"
echo "API http://localhost:8000/docs   Dashboard http://localhost:3000   (n8n: docker compose, port 5678)"
