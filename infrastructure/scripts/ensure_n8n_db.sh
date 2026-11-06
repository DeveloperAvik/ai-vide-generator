#!/usr/bin/env bash
# Idempotently creates the `n8n` database inside the compose Postgres (the data volume is preserved; init scripts
# would not re-run on an existing volume). Safe to run repeatedly.
set -euo pipefail
cd "$(dirname "$0")/../.."
C="docker compose -f infrastructure/docker-compose.yml --env-file .env"
for i in $(seq 1 30); do $C exec -T postgres pg_isready -U studio -d cyber_studio -q && break; sleep 2; done
$C exec -T postgres pg_isready -U studio -d cyber_studio
if $C exec -T postgres psql -U studio -d cyber_studio -tAc "select 1 from pg_database where datname='n8n'" | grep -q 1; then
  echo "database n8n already exists"
else
  $C exec -T postgres psql -U studio -d cyber_studio -c "create database n8n owner studio"
fi
