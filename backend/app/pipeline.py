"""Single-pass pipeline: guard -> planner -> KOHA -> synthesiser."""

from __future__ import annotations

import asyncio
import logging
import re

from . import faq as faq_kb
from .config import Settings
from .guard import PromptGuard
from .koha import KohaClient, SearchHit
from .llm import OllamaClient
from .planner import Plan, plan_query
from .schemas import ChatRequest, ChatResponse
from .synthesizer import (
    Result,
    blocked_response,
    synthesise_catalogue,
    synthesise_faq,
    synthesise_generic,
)

log = logging.getLogger("library-assistant.pipeline")

_GENERIC_GUIDANCE = {
    "research_help": (
        "The user wants research guidance (databases, citation tools, scholarly "
        "communication). Give brief, practical pointers and mention that they can "
        "also ask you to search the catalogue."
    ),
    "smalltalk": "Respond warmly and briefly, then invite a library question.",
    "out_of_scope": (
        "Politely explain you only help with library resources and services, and "
        "offer an example of something you can do."
    ),
}

# Filler words that hurt KOHA's AND-based keyword search.
_STOPWORDS = {
    "find", "show", "search", "get", "give", "list", "looking", "look", "need",
    "want", "please", "me", "all", "any", "some", "the", "a", "an", "of", "on",
    "in", "for", "about", "related", "regarding", "with", "by", "to", "and",
    "books", "book", "resources", "resource", "publications", "publication",
    "materials", "material", "items", "item", "available", "do", "we", "have",
    "is", "are", "there",
}


def _significant_tokens(term: str) -> list[str]:
    tokens = [t for t in re.split(r"[^0-9A-Za-z]+", term) if t]
    sig = [t for t in tokens if t.lower() not in _STOPWORDS and len(t) > 1]
    return sig or tokens


def strip_stopwords(term: str) -> str:
    sig = _significant_tokens(term)
    return " ".join(sig)


def _query_candidates(plan: Plan) -> list[str]:
    """Ordered queries to try, from most to least specific."""
    seen: set[str] = set()
    out: list[str] = []

    def add(t: str | None) -> None:
        t = (t or "").strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)

    add(plan.search_term)
    stripped = strip_stopwords(plan.search_term)
    add(stripped if stripped != plan.search_term else None)

    # KOHA ANDs terms, so for field searches fall back to OR then to single terms.
    # (Skipped for author and ISBN, where OR would produce nonsense.)
    if plan.index not in ("au", "isbn"):
        tokens = _significant_tokens(plan.search_term)
        if len(tokens) >= 2:
            add(" OR ".join(tokens))
        for tok in sorted(tokens, key=len, reverse=True):
            add(tok)

    for alt in plan.alternatives:
        add(alt)
        add(strip_stopwords(alt))

    return out


class Pipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = OllamaClient(
            settings.ollama_host,
            settings.ollama_model,
            timeout=settings.ollama_timeout,
            think=settings.ollama_think,
        )
        self.koha = KohaClient(
            settings.koha_base,
            backend=settings.search_backend,
            api_user=settings.koha_api_user,
            api_pass=settings.koha_api_pass,
            timeout=settings.koha_timeout,
            max_results=settings.max_results,
        )
        self.guard = PromptGuard(
            enabled=settings.guard_enabled,
            model_name=settings.guard_model,
            threshold=settings.guard_threshold,
        )

    async def warmup(self) -> None:
        """Load the guard and preload the LLM (best effort, non-fatal)."""
        tasks = [self._warm_llm()]
        if self.guard.enabled:
            tasks.append(self.guard.load())
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                log.debug("warmup task failed: %s", r)

    async def _warm_llm(self) -> None:
        try:
            await self.llm.chat(
                [{"role": "user", "content": "hi"}], num_predict=1, keep_alive="30m"
            )
        except Exception as exc:
            log.debug("LLM warmup failed (will retry on demand): %s", exc)

    async def handle(self, request: ChatRequest) -> ChatResponse:
        query = request.user_text

        # 1. Prompt-injection guard.
        verdict = await self.guard.check(query)
        if not verdict.allowed:
            log.info("blocked query (%s): %r", verdict.reason, query)
            return blocked_response(query, verdict.reason)

        # 2. Plan.
        plan = await plan_query(self.llm, query)
        log.info(
            "plan intent=%s index=%s term=%r (fallback=%s)",
            plan.intent,
            plan.index,
            plan.search_term,
            plan.used_fallback,
        )

        # 3. Route.
        if plan.intent == "faq":
            entries = faq_kb.find_entries(query)
            return await synthesise_faq(self.llm, query, entries)

        if plan.intent in _GENERIC_GUIDANCE:
            return await synthesise_generic(
                self.llm, query, plan.intent, _GENERIC_GUIDANCE[plan.intent]
            )

        # catalogue_search (default)
        return await self._catalogue(query, plan)

    async def _catalogue(self, query: str, plan: Plan) -> ChatResponse:
        hits: list = []
        total = 0
        used_term = plan.search_term

        for term in _query_candidates(plan):
            hits, total = await self.koha.search(term, plan.index)
            if hits:
                used_term = term
                if term != plan.search_term:
                    log.info("relaxed query to %r -> %d hits", term, len(hits))
                break

        hits = hits[: self.settings.max_results]
        enriched = await self.koha.enrich(hits)

        results: list[Result] = []
        for hit, details, avail in enriched:
            results.append(self._to_result(hit, details, avail))

        search_url = self.koha.opac_search_url(used_term, plan.index)
        return await synthesise_catalogue(
            self.llm, query, plan, results, total, search_url
        )

    @staticmethod
    def _to_result(hit: SearchHit, details, avail) -> Result:
        biblio_id = hit.biblio_id or 0
        return Result(
            biblio_id=biblio_id,
            title=(details.title if details and details.title else hit.title)
            or f"Catalogue record {biblio_id}",
            author=details.author if details else None,
            publisher=details.publisher if details else None,
            year=details.year if details else None,
            isbn=(details.isbn if details else None) or hit.isbn,
            url=(details.url if details and details.url else hit.url),
            total_items=avail.total_items if avail else 0,
            available=avail.available if avail else 0,
            libraries=avail.libraries if avail else [],
            callnumbers=avail.callnumbers if avail else [],
        )
