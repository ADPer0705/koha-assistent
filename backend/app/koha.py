"""Async KOHA client.

Two catalogue-search backends:

* ``rss``  – the OPAC's public RSS feed
  (``/cgi-bin/koha/opac-search.pl?idx=...&q=...&format=rss2``). No auth needed.
* ``rest`` – the staff REST API (``/api/v1/biblios?q=...``). Requires credentials.

Record metadata and item availability are always fetched from the *public*
REST endpoints (``/api/v1/public/...``) which need no authentication.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx
from defusedxml.ElementTree import fromstring as xml_fromstring

log = logging.getLogger("library-assistant.koha")

# OPAC search indexes exposed by KOHA.
VALID_INDEXES = {"kw", "ti", "au", "su", "isbn", "pb", "se", "nb"}

_NS = {
    "rss": "",
    "dc": "http://purl.org/dc/elements/1.1/",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
}

_BIBNO_RE = re.compile(r"biblionumber=(\d+)")
_YEAR_RE = re.compile(r"(1[5-9]\d{2}|20\d{2})")
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class SearchHit:
    """A raw catalogue hit from a search (enriched later)."""

    biblio_id: int | None
    title: str
    url: str
    isbn: str | None = None


@dataclass
class BiblioDetails:
    biblio_id: int
    title: str = ""
    author: str | None = None
    publisher: str | None = None
    year: str | None = None
    isbn: str | None = None
    subjects: list[str] = field(default_factory=list)
    url: str = ""


@dataclass
class Availability:
    biblio_id: int
    total_items: int = 0
    available: int = 0
    libraries: list[str] = field(default_factory=list)
    callnumbers: list[str] = field(default_factory=list)


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", text))).strip()


class KohaClient:
    def __init__(
        self,
        base_url: str,
        *,
        backend: str = "rss",
        api_user: str = "",
        api_pass: str = "",
        timeout: float = 20.0,
        max_results: int = 5,
    ) -> None:
        self.base = base_url.rstrip("/")
        self.backend = backend
        self.api_user = api_user
        self.api_pass = api_pass
        self.timeout = timeout
        self.max_results = max_results

    # ------------------------------------------------------------------ urls
    def opac_search_url(self, term: str, index: str = "kw") -> str:
        return (
            f"{self.base}/cgi-bin/koha/opac-search.pl"
            f"?idx={quote(index)}&q={quote(term)}&sort_by=relevance"
        )

    def biblio_url(self, biblio_id: int) -> str:
        return f"{self.base}/cgi-bin/koha/opac-detail.pl?biblionumber={biblio_id}"

    def _auth(self) -> tuple[str, str] | None:
        if self.backend == "rest" and self.api_user:
            return (self.api_user, self.api_pass)
        return None

    # ---------------------------------------------------------------- search
    async def search(
        self, term: str, index: str = "kw", limit: int | None = None
    ) -> tuple[list[SearchHit], int]:
        limit = limit or self.max_results
        index = index if index in VALID_INDEXES else "kw"
        if not term.strip():
            return [], 0
        try:
            if self.backend == "rest":
                return await self._search_rest(term, index, limit)
            return await self._search_rss(term, index, limit)
        except Exception as exc:  # never let a backend hiccup break the pipeline
            log.warning("catalogue search failed (%s=%r): %s", index, term, exc)
            return [], 0

    async def _search_rss(
        self, term: str, index: str, limit: int
    ) -> tuple[list[SearchHit], int]:
        url = (
            f"{self.base}/cgi-bin/koha/opac-search.pl"
            f"?idx={quote(index)}&q={quote(term)}&sort_by=relevance&format=rss2"
        )
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as c:
            resp = await c.get(url, headers={"User-Agent": "nfsu-library-assistant/0.1"})
            resp.raise_for_status()
        return self._parse_rss(resp.text, limit)

    @staticmethod
    def _parse_rss(xml_text: str, limit: int) -> tuple[list[SearchHit], int]:
        root = xml_fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return [], 0

        total = 0
        total_el = channel.find("opensearch:totalResults", _NS)
        if total_el is not None and total_el.text:
            total = int(total_el.text.strip() or 0)

        hits: list[SearchHit] = []
        for item in channel.findall("item")[:limit]:
            link_el = item.find("link")
            guid_el = item.find("guid")
            raw_link = (link_el.text or guid_el.text or "") if link_el is not None else ""
            raw_link = (raw_link or (guid_el.text if guid_el is not None else "") or "").strip()
            m = _BIBNO_RE.search(raw_link)
            biblio_id = int(m.group(1)) if m else None

            title = _clean(item.findtext("title"))
            isbn = None
            for ident in item.findall("dc:identifier", _NS):
                if ident.text and ident.text.startswith("ISBN:"):
                    isbn = ident.text.split(":", 1)[1].strip()
                    break
            if biblio_id is None and not title:
                continue
            hits.append(SearchHit(biblio_id=biblio_id, title=title, url=raw_link, isbn=isbn))

        return hits, total

    async def _search_rest(
        self, term: str, index: str, limit: int
    ) -> tuple[list[SearchHit], int]:
        # KOHA REST filtering: q={"field":{...}}. Field mapping kept deliberately
        # small for the POC; keyword search falls back to a plain match.
        field = {
            "ti": "title",
            "au": "author",
            "su": "subject",
            "isbn": "isbn",
            "pb": "publisher",
        }.get(index)
        if field:
            query = f'{{"{field}":{{"-like":"%{term}%"}}}}'
        else:
            query = f'{{"title":{{"-like":"%{term}%"}}}}'
        params = {"q": query, "_per_page": limit}
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.get(
                f"{self.base}/api/v1/biblios", params=params, auth=self._auth()
            )
            resp.raise_for_status()
            rows = resp.json()
            total = int(resp.headers.get("X-Total-Count", len(rows)))
        hits = []
        for row in rows[:limit]:
            bid = row.get("biblio_id")
            hits.append(
                SearchHit(
                    biblio_id=bid,
                    title="",
                    url=self.biblio_url(bid) if bid else "",
                )
            )
        return hits, total

    # -------------------------------------------------------------- describe
    async def describe(self, biblio_id: int) -> BiblioDetails | None:
        """Fetch MARC metadata for a record via the public endpoint."""
        url = f"{self.base}/api/v1/public/biblios/{biblio_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                resp = await c.get(
                    url,
                    headers={"Accept": "application/marc-in-json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            log.debug("describe(%s) failed: %s", biblio_id, exc)
            return None
        return self._parse_marc(biblio_id, data)

    @staticmethod
    def _parse_marc(biblio_id: int, data: dict) -> BiblioDetails:
        fields: dict[str, list[dict]] = {}
        for entry in data.get("fields", []):
            for tag, payload in entry.items():
                fields.setdefault(tag, []).append(payload)

        def sub(tag: str, code: str) -> str | None:
            for payload in fields.get(tag, []):
                for sf in payload.get("subfields", []):
                    if code in sf:
                        return _clean(sf[code])
            return None

        title = sub("245", "a") or ""
        subtitle = sub("245", "b")
        if subtitle:
            title = f"{title}: {subtitle}".rstrip(": ")

        author = sub("100", "a") or sub("110", "a") or sub("700", "a")
        publisher = sub("264", "b") or sub("260", "b")
        year_raw = sub("264", "c") or sub("260", "c")
        year = None
        if year_raw:
            m = _YEAR_RE.search(year_raw)
            year = m.group(1) if m else year_raw.strip(" .")

        isbn = None
        for payload in fields.get("020", []):
            for sf in payload.get("subfields", []):
                if "a" in sf:
                    isbn = _clean(sf["a"]).split(" ")[0]
                    break
            if isbn:
                break

        subjects: list[str] = []
        for tag in ("650", "651", "653"):
            for payload in fields.get(tag, []):
                for sf in payload.get("subfields", []):
                    if "a" in sf:
                        val = _clean(sf["a"])
                        if val and val not in subjects:
                            subjects.append(val)

        return BiblioDetails(
            biblio_id=biblio_id,
            title=title,
            author=author,
            publisher=publisher.rstrip(" ,") if publisher else None,
            year=year,
            isbn=isbn,
            subjects=subjects,
            url=f"https://catalog.nfsu.ac.in/cgi-bin/koha/opac-detail.pl?biblionumber={biblio_id}",
        )

    # ------------------------------------------------------------ availability
    async def availability(self, biblio_id: int) -> Availability | None:
        params = {"q": f'{{"biblio_id":{biblio_id}}}', "_per_page": 50}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                resp = await c.get(
                    f"{self.base}/api/v1/public/items", params=params
                )
                resp.raise_for_status()
                items = resp.json()
        except Exception as exc:
            log.debug("availability(%s) failed: %s", biblio_id, exc)
            return None

        avail = Availability(biblio_id=biblio_id)
        for it in items:
            avail.total_items += 1
            if it.get("home_library_id") and it["home_library_id"] not in avail.libraries:
                avail.libraries.append(it["home_library_id"])
            cn = (it.get("callnumber") or "").strip()
            if cn and cn not in avail.callnumbers:
                avail.callnumbers.append(cn)
            if (
                not it.get("withdrawn")
                and not it.get("lost_status")
                and not it.get("damaged_status")
                and not it.get("not_for_loan_status")
                and it.get("checked_out_date") is None
            ):
                avail.available += 1
        return avail

    # ------------------------------------------------------------- enrich N
    async def enrich(
        self, hits: list[SearchHit]
    ) -> list[tuple[SearchHit, BiblioDetails | None, Availability | None]]:
        """Fetch metadata + availability for each hit concurrently."""

        async def one(hit: SearchHit):
            if hit.biblio_id is None:
                return hit, None, None
            details, avail = await asyncio.gather(
                self.describe(hit.biblio_id),
                self.availability(hit.biblio_id),
            )
            return hit, details, avail

        return await asyncio.gather(*(one(h) for h in hits))
