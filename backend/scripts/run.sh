#!/usr/bin/env bash
# Start the library assistant API on http://localhost:5000
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-5000}" "$@"
