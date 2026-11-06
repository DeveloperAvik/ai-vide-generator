#!/usr/bin/env bash
# Local (no Docker) setup for macOS/Linux. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-$(command -v python3.13 || command -v python3.12 || command -v python3)}
"$PY" -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ required"'
command -v ffmpeg >/dev/null || { echo "Install ffmpeg first (brew install ffmpeg | apt install ffmpeg)"; exit 1; }
[ -f .env ] || { cp .env.example .env
  sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|; s|^SERVICE_TOKEN=.*|SERVICE_TOKEN=$(openssl rand -hex 32)|; s|^N8N_ENCRYPTION_KEY=.*|N8N_ENCRYPTION_KEY=$(openssl rand -hex 16)|" .env && rm -f .env.bak
  echo "created .env with fresh random secrets"; }
[ -d backend/.venv ] || "$PY" -m venv backend/.venv
backend/.venv/bin/pip install -q -r backend/requirements.txt
# Postgres (local): create role+db if psql is available and they don't exist
if command -v psql >/dev/null && pg_isready -q; then
  psql -d postgres -tAc "select 1 from pg_roles where rolname='studio'" | grep -q 1 || psql -d postgres -c "create role studio login password 'studio'"
  psql -d postgres -tAc "select 1 from pg_database where datname='cyber_studio'" | grep -q 1 || psql -d postgres -c "create database cyber_studio owner studio"
fi
(cd backend && .venv/bin/alembic upgrade head)
(cd video-engine && npm install --no-audit --no-fund)
(cd frontend && npm install --no-audit --no-fund)
python3 automation/generate_workflows.py
echo "setup done. Next: scripts/start.sh"
