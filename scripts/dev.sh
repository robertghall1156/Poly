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

# --- preflight: reclaim our own ports ----------------------------------------
# Starting a second stack on top of a running one is the most confusing failure
# there is: the new API dies with "address already in use", the new UI silently
# moves to :3001, and the health check below passes against the OLD process — so
# the script says "Poly is running" while nothing you are looking at is current.
# Stop Poly's own leftovers first; refuse to touch anything that isn't ours.
reclaim_port() {   # $1 = port, $2 = what should be there
  local port="$1" label="$2" pids pid cmd
  pids="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  [ -n "$pids" ] || return 0
  for pid in $pids; do
    cmd="$(ps -o command= -p "$pid" 2>/dev/null || true)"
    case "$cmd" in
      *poly.cli*|*uvicorn*|*next*dev*|*next-server*|*node*"$ROOT/frontend"*)
        echo "Stopping the previous $label on :$port (pid $pid)…"
        kill "$pid" 2>/dev/null || true
        ;;
      *)
        echo "Port $port is held by something that isn't Poly (pid $pid):"
        echo "  $cmd"
        echo "Stop it yourself, or free the port, then run this again."
        exit 1
        ;;
    esac
  done
  for _ in $(seq 1 20); do
    lsof -nP -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 || return 0
    sleep 0.5
  done
  # still there after 10s — it ignored SIGTERM
  for pid in $(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null); do kill -9 "$pid" 2>/dev/null || true; done
  sleep 1
}

reclaim_port 8000 "Poly API"
reclaim_port 3000 "Poly UI"
# the worker holds no port, so find it by name
for pid in $(pgrep -f "poly\.cli worker" 2>/dev/null || true); do
  echo "Stopping the previous worker (pid $pid)…"
  kill "$pid" 2>/dev/null || true
done

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
    UI_PORT="$(grep -o 'using available port [0-9]*' "$ROOT/data/logs/frontend.log" 2>/dev/null | tail -1 | grep -o '[0-9]*$')"
    UI_PORT="${UI_PORT:-3000}"
    echo "Poly is running:   UI http://localhost:$UI_PORT    API http://localhost:8000/docs"
    [ "$UI_PORT" = "3000" ] || echo "(note: :3000 was taken, so the UI is on :$UI_PORT — open that one)"
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
