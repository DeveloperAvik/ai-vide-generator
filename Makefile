.PHONY: setup start stop test demo docker-up docker-infra-up docker-full-up docker-down backup health workflows n8n-import n8n-test
COMPOSE = docker compose -f infrastructure/docker-compose.yml --env-file .env
setup: ; ./scripts/setup.sh
start: ; ./scripts/start.sh
stop: ; ./scripts/stop.sh
test: ; cd backend && .venv/bin/python -m pytest -q
demo: ; cd backend && .venv/bin/python -m app.cli.demo
workflows: ; python3 automation/generate_workflows.py

# Hybrid: ONLY postgres + n8n in Docker. FastAPI/Next.js/rendering stay on the Mac (scripts/start.sh).
# Existing volumes are reused; nothing is deleted. Any half-started backend/frontend containers are stopped (not removed).
docker-infra-up:
	-$(COMPOSE) stop backend frontend
	$(COMPOSE) up -d --build postgres
	./infrastructure/scripts/ensure_n8n_db.sh
	$(COMPOSE) up -d --build n8n
	$(COMPOSE) ps

# Everything in Docker (stop the Mac copies first: ports 8000/3000). n8n then talks to http://backend:8000.
docker-full-up:
	$(COMPOSE) up -d --build postgres
	./infrastructure/scripts/ensure_n8n_db.sh
	STUDIO_API_URL_FOR_N8N=http://backend:8000 $(COMPOSE) --profile full up -d --build
	$(COMPOSE) --profile full ps

docker-up: docker-infra-up   # kept for backwards compatibility; now the hybrid mode

# Stops and removes containers/networks. Volumes (pgdata, n8n-data, studio-data) are KEPT.
docker-down: ; $(COMPOSE) --profile full down

n8n-import: ; ./infrastructure/scripts/import_workflows.sh
n8n-test: ; backend/.venv/bin/python infrastructure/scripts/n8n_test.py
backup: ; ./scripts/backup.sh
health: ; ./scripts/healthcheck.sh
