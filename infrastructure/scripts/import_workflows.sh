#!/usr/bin/env bash
# Imports automation/workflows/*.json into the running n8n container. Workflows have stable ids, so re-running updates
# them in place. Aborts if a DIFFERENT workflow already uses one of our names (never silently overwrites yours).
set -euo pipefail
cd "$(dirname "$0")/../.."
C="docker compose -f infrastructure/docker-compose.yml --env-file .env"
python3 automation/generate_workflows.py >/dev/null
existing=$($C exec -T n8n n8n list:workflow 2>/dev/null || true)
echo "existing workflows in n8n:"; echo "${existing:-  (none)}"
python3 - "$existing" <<'PY'
import json, glob, sys
ours = {json.load(open(f))["name"]: json.load(open(f))["id"] for f in glob.glob("automation/workflows/*.json")}
for line in sys.argv[1].splitlines():
    if "|" in line:
        wid, name = line.split("|", 1)
        if name in ours and ours[name] != wid:
            sys.exit(f"ABORT: workflow '{name}' exists with id {wid} (ours: {ours[name]}). Rename or delete it in n8n first.")
print("no conflicting workflows; importing")
PY
$C exec -T n8n n8n import:workflow --separate --input=/workflows
$C exec -T n8n n8n list:workflow
