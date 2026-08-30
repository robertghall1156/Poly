.PHONY: setup dev test build backend worker frontend ingest detect migrate lint
setup:      ; ./scripts/setup.sh
dev:        ; ./scripts/dev.sh
backend:    ; cd backend && .venv/bin/poly serve --reload
worker:     ; cd backend && .venv/bin/poly worker
frontend:   ; cd frontend && npm run dev
ingest:     ; cd backend && .venv/bin/poly ingest
detect:     ; cd backend && .venv/bin/poly detect
migrate:    ; cd backend && .venv/bin/alembic upgrade head
test:       ; cd backend && .venv/bin/python -m pytest -q
build:      ; cd frontend && npm run build
lint:       ; cd backend && .venv/bin/ruff check poly tests && cd ../frontend && npm run lint
