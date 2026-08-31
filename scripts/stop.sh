#!/usr/bin/env bash
# Stops everything Poly started: the API (:8000), the UI (:3000/:3001…) and the worker.
# Safe to run any time — it only ever kills Poly's own processes.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
found=0

stop_port() {
  local port="$1" label="$2" pid cmd
  for pid in $(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null); do
    cmd="$(ps -o command= -p "$pid" 2>/dev/null || true)"
    case "$cmd" in
      *poly.cli*|*uvicorn*|*next*dev*|*next-server*|*node*"$ROOT/frontend"*)
        echo "Stopping $label on :$port (pid $pid)"
        kill "$pid" 2>/dev/null || true
        found=1
        ;;
      *) echo "Leaving :$port alone — not Poly (pid $pid): $cmd" ;;
    esac
  done
}

stop_port 8000 "API"
for p in 3000 3001 3002; do stop_port "$p" "UI"; done

for pid in $(pgrep -f "poly\.cli worker" 2>/dev/null || true); do
  echo "Stopping worker (pid $pid)"
  kill "$pid" 2>/dev/null || true
  found=1
done

sleep 1
for pid in $(lsof -nP -tiTCP:8000 -sTCP:LISTEN 2>/dev/null); do kill -9 "$pid" 2>/dev/null || true; done

[ "$found" = "1" ] && echo "Stopped." || echo "Nothing of Poly's was running."
