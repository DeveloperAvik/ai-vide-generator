#!/usr/bin/env bash
# Dumps the database and manifests. Restore: gunzip -c backups/db_X.sql.gz | psql "$DB"
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
mkdir -p backups
STAMP=$(date +%Y%m%d_%H%M%S)
DB=${BACKUP_DATABASE_URL:-$(echo "$DATABASE_URL" | sed 's/+psycopg//')}
pg_dump "$DB" | gzip > "backups/db_$STAMP.sql.gz"
tar czf "backups/manifests_$STAMP.tgz" storage/manifests 2>/dev/null || true
ls -t backups/db_*.sql.gz | tail -n +15 | xargs -I{} rm -f {}   # keep 14 newest
chmod 600 backups/*
echo "backup written: backups/db_$STAMP.sql.gz"
