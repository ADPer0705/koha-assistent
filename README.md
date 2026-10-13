# NFSU Library Research Assistant (Chatbot)

Conversational assistant for the NFSU KOHA OPAC. Given a natural-language query
it returns a text summary plus relevant catalogue/resource links as JSON.

> **Hackathon prototype.** The browser-extension frontend is maintained by a
> separate team; this repository is the backend service it consumes, plus a
> reference widget and demo scripts.

## What it does

- Natural-language search of the KOHA catalogue (title, author, subject,
  keyword, ISBN, publisher).
- Links to individual bibliographic records with author, year, publisher, ISBN
  and copy availability.
- Answers FAQs about library services (hours, membership, loans, e-resources,
  remote access, theses, citations).
- Prompt-injection guard (`Llama Prompt Guard 2`) in front of the LLM.

## Repository layout

```
backend/     FastAPI service (the deliverable for the frontend team)
widget/      Reference floating chat embed for the OPAC (frontend owns the real one)
docs/        Demo runbook
koha-api.json  KOHA REST API v1 spec (reference)
misc/koha.json earlier spec dump
```

## Quick start

See **[docs/DEMO.md](docs/DEMO.md)** for the full runbook. Short version:

```bash
cd backend
uv venv --python 3.12
uv pip install fastapi "uvicorn[standard]" httpx pydantic \
                pydantic-settings defusedxml pytest pytest-asyncio
./scripts/run.sh          # http://localhost:5000
```

Then load the browser extension (unpacked) from the frontend team and open
<https://catalog.nfsu.ac.in>.

## API contract (used by the extension)

`POST http://localhost:5000/`

```json
{ "text": "find books on forensic DNA analysis" }
```

→

```json
{
  "text_summary": "I found 7 catalogue records …",
  "sources": [
    { "url": "https://catalog.nfsu.ac.in/cgi-bin/koha/opac-detail.pl?biblionumber=8181",
      "description": "Forensic DNA analysis … — Pilli, Elena (2021), Apple Academic Press. ISBN …",
      "title": "Forensic DNA analysis …" }
  ]
}
```

A richer endpoint, `POST /api/chat`, returns
`{query, intent, summary, links, suggestions, meta}`. OpenAPI docs at `/docs`.

## Design

A single-pass pipeline (no agentic loop): **guard → planner → KOHA client →
synthesiser**. The LLM plans the search and writes the summary, but never emits
URLs — links are always mapped from real KOHA records. Details in
[backend/README.md](backend/README.md).

## Status

- [x] Guard (Prompt Guard 2 + heuristic fallback)
- [x] Planner / search planning
- [x] KOHA search, MARC metadata, availability
- [x] FAQ knowledge base
- [x] Extension contract + reference widget
- [x] Tests, demos, docs
- [ ] Multilingual responses, ONOS/e-resource deep links, analytics (future)
