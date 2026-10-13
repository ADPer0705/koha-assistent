# NFSU Library Research Assistant — Backend

FastAPI service that answers natural-language library queries by searching the
NFSU KOHA OPAC and returns a summary plus resource links as JSON.

## Architecture — a single pass, no agent loop

```
 user query
    │
    ▼
┌─────────┐   malicious   ┌───────────────────┐
│  GUARD  │──────────────▶│ safe refusal JSON │
└────┬────┘               └───────────────────┘
     │ clean
     ▼
┌─────────┐   tool/params JSON
│ PLANNER │  intent, index, search_term
└────┬────┘
     ▼
┌──────────────┐  OPAC RSS search + public REST (metadata, availability)
│ KOHA CLIENT  │
└────┬─────────┘
     ▼
┌──────────────┐  LLM writes the prose; URLs come from real records only
│ SYNTHESISER  │
└────┬─────────┘
     ▼
 { text_summary, sources[] }
```

- **Guard** — `meta-llama/Llama-Prompt-Guard-2-86M` classifies the raw query;
  malformed/injection attempts are rejected before reaching the LLM. A regex
  heuristic is used automatically if the model/deps are unavailable.
- **Planner** — one Ollama call with a JSON schema; produces the search plan.
- **KOHA client** — search, MARC metadata and item availability.
- **Synthesiser** — one Ollama call for the summary/suggestions; **the model
  never emits URLs** — links are mapped from the fetched record set.

## Prerequisites

- `uv` (Python tooling) — already present.
- Ollama running locally with a model pulled (default `qwen3.5:9b`):

  ```bash
  ollama pull qwen3.5:9b
  ollama serve          # usually already running as a service
  ```

## Setup

From `backend/`, the fastest path is the setup script:

```bash
./scripts/setup.sh              # base deps + Prompt Guard (CPU torch)
WITH_GUARD=0 ./scripts/setup.sh # skip the optional guard model
```

Or install manually:

```bash
uv venv --python 3.12

# Base dependencies
uv pip install fastapi "uvicorn[standard]" httpx pydantic \
                pydantic-settings defusedxml pytest pytest-asyncio

# Optional: Prompt Guard 2 (CPU build of torch keeps the download small)
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install transformers safetensors
```

> The guard weights download automatically on first start (the Hugging Face CLI
> token already configured is used). If torch/transformers are missing the
> service still runs, falling back to a regex guard.

Copy the environment template and adjust if needed:

```bash
cp .env.example .env
```

## Run

```bash
./scripts/run.sh                     # http://localhost:5000
# or
uv run uvicorn app.main:app --host 0.0.0.0 --port 5000
```

Interactive API docs: <http://localhost:5000/docs>

## API

### `POST /` — browser-extension contract

Request:

```json
{ "text": "find books on forensic DNA analysis" }
```

Response:

```json
{
  "text_summary": "I found 7 catalogue records …",
  "sources": [
    {
      "url": "https://catalog.nfsu.ac.in/cgi-bin/koha/opac-detail.pl?biblionumber=8181",
      "description": "Forensic DNA analysis … — Pilli, Elena (2021), Apple Academic Press. ISBN …",
      "title": "Forensic DNA analysis …"
    }
  ]
}
```

> The frontend renders `sources[].description` and only links `https://` URLs.

### `POST /api/chat` — richer contract

Accepts `{"text": ...}` or `{"query": ...}` and returns
`{query, intent, summary, links, suggestions, meta}`. Used by the reference
widget and tests.

### `GET /api/health`, `GET /api/config`

Health/status probe and the enable/disable flag the frontend can read.

## KOHA integration notes

The staff REST search endpoint (`/api/v1/biblios`) requires an authenticated
API user. For the prototype the search uses the **unauthenticated OPAC RSS
feed** (`opac-search.pl?...&format=rss2`); metadata and availability come from
the unauthenticated public REST endpoints:

| Purpose      | Endpoint |
|--------------|----------|
| Search       | `GET /cgi-bin/koha/opac-search.pl?idx=<index>&q=<term>&format=rss2` |
| Metadata     | `GET /api/v1/public/biblios/{id}` (`Accept: application/marc-in-json`) |
| Availability | `GET /api/v1/public/items?q={"biblio_id":N}` |
| Branches     | `GET /api/v1/public/libraries` |

Set `SEARCH_BACKEND=rest` and provide `KOHA_API_USER`/`KOHA_API_PASS` to switch
to the staff REST search once credentials exist.

## Tests & demos

```bash
.venv/bin/python -m pytest -q          # 20 unit tests, no network

.venv/bin/python scripts/demo.py       # full pipeline, in-process, prints frontend JSON
.venv/bin/python scripts/demo_http.py  # hits a running server like the extension
.venv/bin/python scripts/smoke.py      # broader live smoke test
```

## Configuration

See `.env.example`. Highlights:

| Variable | Default | Meaning |
|----------|---------|---------|
| `SEARCH_BACKEND` | `rss` | `rss` (no auth) or `rest` |
| `OLLAMA_MODEL` | `qwen3.5:9b` | planner + synthesiser model |
| `GUARD_ENABLED` | `true` | toggle the prompt-injection guard |
| `MAX_RESULTS` | `5` | records enriched per query |
| `CHATBOT_ENABLED` | `true` | master on/off surfaced to the frontend |

## Troubleshooting

- **`uv sync`/`uv run` is slow the first time** — the lock resolves the optional
  guard extra (torch). Using the commands above (`uv pip install …`) avoids it.
- **First response is slow** — the guard model and LLM are warmed in the
  background at startup; the first request after boot may still be slower.
- **Guard logs "unavailable"** — torch/transformers not installed; the regex
  fallback is active and the pipeline continues.
- **No LLM reachable** — the planner falls back to a keyword heuristic and the
  summary falls back to a template, so the service still answers.
