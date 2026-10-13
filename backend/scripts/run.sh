#!/usr/bin/env bash
# Start the library assistant API on http://localhost:5000
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-5000}"

# Prefer the project venv directly (avoids `uv run` re-resolving dependencies).
if [ -x .venv/bin/uvicorn ]; then
  exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT" "$@"
fi

exec uv run uvicorn app.main:app --host 0.0.0.0 --port "$PORT" "$@"
