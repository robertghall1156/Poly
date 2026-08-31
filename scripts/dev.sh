#!/usr/bin/env bash
# Runs the API (:8000), the background worker, and the Next.js UI (:3000) together.
# Ctrl-C stops all three. Backend/worker output is echoed here AND kept in data/logs/.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
[ -f .env ] || cp .env.example .env
[ -d backend/.venv ] || { echo "Run ./scripts/setup.sh first"; exit 1; }
[ -d frontend/node_modules ] || { echo "Run ./scripts/setup.sh first"; exit 1; }
mkdir -p data/logs

PY="$ROOT/backend/.venv/bin/python"

# --- preflight: the venv must be able to import the app -----------------------
# An editable install can end up missing its path link (no .pth), which makes the
# backend die instantly with "ModuleNotFoundError: No module named 'poly'".
# Detect that here and repair it rather than failing three seconds later.
# checked from a neutral directory on purpose: inside backend/ the import always
# succeeds (cwd is on the path) and would hide a broken install.
if ! ( cd / && "$PY" -c "import poly" >/dev/null 2>&1 ); then
  echo "Repairing the backend install (missing package link)…"
  if command -v uv >/dev/null 2>&1; then
    ( cd backend && uv pip install -q -p "$PY" -e . ) || true
  else
    ( cd backend && "$PY" -m pip install -q -e . ) || true
  fi
  if ! ( cd / && "$PY" -c "import poly" >/dev/null 2>&1 ); then
    # last resort: point site-packages straight at the source tree
    SITE="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
    echo "$ROOT/backend" > "$SITE/poly_backend_src.pth"
  fi
  ( cd / && "$PY" -c "import poly" >/dev/null 2>&1 ) \
    || { echo "Backend still can't start. Run: cd backend && uv pip install -e . "; exit 1; }
  echo "Repaired."
fi

trap 'kill 0' EXIT INT TERM

# `python -m poly.cli` rather than the console script: it works even if the
# entry point is stale, because the backend directory is on the path.
( cd backend && "$PY" -m poly.cli serve   2>&1 | tee "$ROOT/data/logs/backend.log" ) &
( cd backend && "$PY" -m poly.cli worker  2>&1 | tee "$ROOT/data/logs/worker.log"  ) &
( cd frontend && npm run dev              2>&1 | tee "$ROOT/data/logs/frontend.log" ) &

# --- wait for the API, and say plainly if it never came up -------------------
API="http://localhost:8000/api/health"
for _ in $(seq 1 40); do
  sleep 1
  if curl -fsS -m 2 "$API" >/dev/null 2>&1; then
    echo
    echo "Poly is running:   UI http://localhost:3000    API http://localhost:8000/docs"
    echo "(logs: data/logs/)"
    wait
    exit 0
  fi
done
echo
echo "The API did not come up on :8000. The last lines of data/logs/backend.log:"
tail -20 "$ROOT/data/logs/backend.log" 2>/dev/null
echo
echo "The UI is still at http://localhost:3000 but it has nothing to talk to."
wait
