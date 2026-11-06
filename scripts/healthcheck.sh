#!/usr/bin/env bash
cd "$(dirname "$0")/.."
ok=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; ok=1; fi; }
chk "API /api/health" "curl -fs http://localhost:8000/api/health"
chk "Dashboard"        "curl -fs http://localhost:3000"
chk "PostgreSQL"       "pg_isready -q"
chk "ffmpeg"           "command -v ffmpeg"
chk "n8n (optional)"   "curl -fs http://localhost:5678/healthz"
exit $ok
