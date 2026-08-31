.PHONY: setup dev stop doctor test build backend worker frontend ingest detect migrate lint
setup:      ; ./scripts/setup.sh
dev:        ; ./scripts/dev.sh
stop:       ; ./scripts/stop.sh
doctor:     ; ./scripts/doctor.sh
backend:    ; cd backend && .venv/bin/python -m poly.cli serve --reload
worker:     ; cd backend && .venv/bin/python -m poly.cli worker
frontend:   ; cd frontend && npm run dev
ingest:     ; cd backend && .venv/bin/python -m poly.cli ingest
detect:     ; cd backend && .venv/bin/python -m poly.cli detect
migrate:    ; cd backend && .venv/bin/alembic upgrade head
test:       ; cd backend && .venv/bin/python -m pytest -q
build:      ; cd frontend && npm run build
lint:       ; cd backend && .venv/bin/ruff check poly tests && cd ../frontend && npm run lint
