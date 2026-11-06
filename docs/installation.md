# Installation

Requirements: Python 3.12+ (3.13 used by the maintainer), Node.js 18.18+ (the Next.js 15 requirement; Node 26 used by the maintainer), PostgreSQL 16, FFmpeg, and `openssl`. macOS is the tested platform; Linux should work with `apt install ffmpeg postgresql nodejs python3-venv` but is untested. Windows is not supported.

## A. macOS local (no Docker, no paid services)
```bash
brew install ffmpeg postgresql@16 node python@3.13
brew services start postgresql@16
cd cyber-ai-studio
./scripts/setup.sh                 # venv, .env with random secrets, DB role+db, migrations, npm installs, workflow generation
echo 'FIRST_ADMIN_PASSWORD=choose-a-strong-one' >> .env
./scripts/start.sh                 # API :8000, dashboard :3000
make demo                          # renders the sample lesson → storage/demo/
make test
```
The default voice provider is Kokoro: download its two model files first (see `voice/README.md`), otherwise `make demo` stops with a "no local voice provider" message. Piper is optional and **research-licensed / GPL** (see `MODEL_AND_ASSET_LICENSES.md`). Optional Remotion engine: `RENDER_ENGINE=remotion` (first render downloads a headless Chrome). **Remotion has its own licence; companies with more than 3 employees need a paid licence** (see `THIRD_PARTY_NOTICES.md`).

## B. Docker (experimental, only partly verified — see architecture.md)
```bash
cp .env.example .env && $EDITOR .env      # set POSTGRES_PASSWORD, SECRET_KEY, SERVICE_TOKEN, N8N_*, FIRST_ADMIN_PASSWORD
make docker-up
./infrastructure/scripts/import_workflows.sh
```
Ports (bound to 127.0.0.1): API 8000, dashboard 3000, n8n 5678. Put nginx (`infrastructure/nginx/studio.conf`) + TLS in front.

## C. Hybrid
Run docker compose on the VPS (without publishing 8000 publicly), run `scripts/start.sh` on your Mac with `DATABASE_URL` pointing at the VPS over an SSH tunnel; heavy rendering uses your Mac.

## Backup / restore
`make backup` → `backups/db_*.sql.gz`. Restore: `gunzip -c backups/db_X.sql.gz | psql "$DATABASE_URL_WITHOUT_+psycopg"`. Videos live in `storage/local` (rsync it).
