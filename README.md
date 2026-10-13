# NFSU Library Research Assistant (Chatbot)

Conversational assistant for the NFSU KOHA OPAC. Given a natural-language query it
returns a text summary plus relevant catalogue/resource links as JSON.

## Status

Hackathon prototype. Frontend (OPAC floating widget) is handled by a separate team;
this service exposes the JSON contract they consume.

## Layout

- `backend/` — FastAPI service implementing the single-pass pipeline
  (prompt-injection guard → planner → KOHA client → synthesiser).
- `koha-api.json` — KOHA REST API v1 spec (reference).
- `misc/koha.json` — earlier fetched spec dump.

## Quick start

```bash
cd backend
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 5000
```

See `backend/README.md` for details. (Full docs are a later task.)
