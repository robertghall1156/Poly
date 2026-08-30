#!/usr/bin/env bash
# First-time setup for Poly on macOS (Apple Silicon) or Linux.
# Installs the Python backend (uv) and the Next.js frontend (npm), creates .env, seeds the database.
set -euo pipefail
cd "$(dirname "$0")/.."

need() { command -v "$1" >/dev/null 2>&1; }
echo "== Checking tools"
need uv || { echo "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
need node || { echo "node not found. Install Node 20+ (brew install node)"; exit 1; }
need ffmpeg || echo "WARNING: ffmpeg not found (brew install ffmpeg) — video features need it."
if curl -s -m 2 http://localhost:11434/api/version >/dev/null; then echo "Ollama: running"; else echo "Ollama: not reachable at :11434 (start it with 'ollama serve' or open the app)"; fi

[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example"; }

echo "== Backend"
( cd backend
  uv venv -q .venv --python 3.11 2>/dev/null || uv venv -q .venv
  EXTRA="dev"
  if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then EXTRA="dev,mlx,vision"; echo "Apple Silicon detected → installing mlx-whisper for local transcription"; else EXTRA="dev,whisper,vision"; fi
  uv pip install -q -p .venv/bin/python -e ".[${EXTRA}]"
  .venv/bin/poly init-db >/dev/null
  echo "Backend ready (.venv). Database seeded with your principles and default feeds."
)

echo "== Frontend"
( cd frontend && npm install --silent )

cat <<MSG

Setup complete. Start everything with:

  ./scripts/dev.sh

Then open http://localhost:3000
Recommended Ollama models (run once):  ollama pull nomic-embed-text   # semantic search
                                       ollama pull qwen2.5:14b        # reasoning / writing
                                       ollama pull llama3.2:3b        # fast classification
MSG
