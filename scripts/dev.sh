#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export CRC_ENV=development
if [[ -f .env ]]; then set -a; source .env; set +a; fi
if [[ "${CRC_ENV}" != development ]]; then echo 'Use the deployment route for production.'; exit 1; fi
.venv/bin/python -m backend.migrate
.venv/bin/uvicorn backend.api:app --host 127.0.0.1 --port 8000 & api_pid=$!
.venv/bin/python -m backend.worker & worker_pid=$!
trap 'kill "$api_pid" "$worker_pid" 2>/dev/null || true' EXIT INT TERM
npm run dev
