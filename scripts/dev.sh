#!/usr/bin/env bash
# Runs the API (:8000), the background worker, and the Next.js UI (:3000) together. Ctrl-C stops all three.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
[ -x backend/.venv/bin/poly ] || { echo "Run ./scripts/setup.sh first"; exit 1; }
[ -d frontend/node_modules ] || { echo "Run ./scripts/setup.sh first"; exit 1; }

trap 'kill 0' EXIT INT TERM
( cd backend && .venv/bin/poly serve ) &
( cd backend && .venv/bin/poly worker ) &
( cd frontend && npm run dev ) &
sleep 3
echo
echo "Poly is starting:  UI http://localhost:3000   API http://localhost:8000/docs"
wait
