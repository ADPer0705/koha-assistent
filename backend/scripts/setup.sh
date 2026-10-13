#!/usr/bin/env bash
# One-shot environment setup for the library assistant backend.
#
#   ./scripts/setup.sh              # with Prompt Guard (CPU torch)
#   WITH_GUARD=0 ./scripts/setup.sh # skip the optional guard model
set -euo pipefail
cd "$(dirname "$0")/.."

uv venv --python 3.12 --allow-existing

echo ">> Installing base dependencies…"
uv pip install fastapi "uvicorn[standard]" httpx pydantic \
                pydantic-settings defusedxml pytest pytest-asyncio

if [ "${WITH_GUARD:-1}" = "1" ]; then
  echo ">> Installing Prompt Guard runtime (CPU torch)…"
  uv pip install torch --index-url https://download.pytorch.org/whl/cpu
  uv pip install transformers safetensors
fi

[ -f .env ] || cp .env.example .env

echo
echo "Setup complete."
echo "  * Ensure Ollama is running:  ollama pull qwen3.5:9b"
echo "  * Start the server:          ./scripts/run.sh"
