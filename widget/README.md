# Reference OPAC widget

Frontend owns the real integration. This folder is a working reference so the
JSON contract can be exercised before the OPAC skin is ready.

## Run

1. Start the API (from `backend/`):

   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 5000
   ```

2. Open `widget/index.html` in a browser (or serve the folder).

## Embed in the KOHA OPAC

Add a single, non-intrusive tag to the OPAC theme (e.g. `opac-main.pl`
`<head>`), pointing at the deployed service:

```html
<script src="https://YOUR-API-HOST/widget.js"
        data-api-base="https://YOUR-API-HOST" defer></script>
```

The widget mounts one fixed-position element (bottom-right) and never modifies
the OPAC search UI. `GET /api/config` can disable it server-side.

## Contract

`POST {api-base}/api/chat`

```json
{ "query": "find books on forensic DNA analysis" }
```

→

```json
{
  "query": "find books on forensic DNA analysis",
  "intent": "catalogue_search",
  "summary": "I found 7 matching records …",
  "links": [
    { "title": "…", "url": "…", "description": "…", "type": "catalogue_record" }
  ],
  "suggestions": ["…"],
  "meta": {
    "total_results": 7, "showing": 5,
    "catalogue_search_url": "…", "source": "koha_opac", "blocked": false
  }
}
```

`GET /api/health` and `GET /api/config` are also available. OpenAPI docs are at
`/docs`.
