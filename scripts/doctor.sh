#!/usr/bin/env bash
# Checks that everything Poly needs is present and working. Run this first when something won't start.
cd "$(dirname "$0")/.."
PY="$PWD/backend/.venv/bin/python"
ok() { printf "  OK    %s\n" "$1"; }
bad() { printf "  FAIL  %s\n     ↳ %s\n" "$1" "$2"; }

echo "Poly doctor"
echo
command -v node >/dev/null && ok "node $(node --version)" || bad "node" "install Node 20+ (brew install node)"
command -v ffmpeg >/dev/null && ok "ffmpeg" || bad "ffmpeg" "brew install ffmpeg — video and audio features need it"
[ -x "$PY" ] && ok "python venv" || bad "python venv" "run ./scripts/setup.sh"
[ -d frontend/node_modules ] && ok "frontend packages" || bad "frontend packages" "run ./scripts/setup.sh"

if [ -x "$PY" ]; then
  if ( cd / && "$PY" -c "import poly" >/dev/null 2>&1 ); then ok "backend package importable"
  else bad "backend package importable" "cd backend && uv pip install -e .   (dev.sh repairs this automatically)"; fi
fi

if curl -fsS -m 2 http://localhost:11434/api/version >/dev/null 2>&1; then
  ok "Ollama running ($(curl -fsS -m 2 http://localhost:11434/api/tags | grep -o '"name"' | wc -l | tr -d ' ') models)"
else
  bad "Ollama" "open the Ollama app, or run: ollama serve"
fi

if curl -fsS -m 2 http://localhost:8000/api/health >/dev/null 2>&1; then ok "API on :8000"
else printf "  ----  API not running (start it with ./scripts/dev.sh)\n"; fi
if curl -fsS -m 2 http://localhost:3000 >/dev/null 2>&1; then ok "UI on :3000"
else printf "  ----  UI not running (start it with ./scripts/dev.sh)\n"; fi

if [ -s data/logs/backend.log ]; then
  echo
  echo "Last backend errors (data/logs/backend.log):"
  grep -iE "error|traceback|exception" -A3 data/logs/backend.log 2>/dev/null | tail -12 || echo "  none"
fi
