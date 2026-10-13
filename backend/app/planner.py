"""Planner node: turns a natural-language query into a KOHA search plan."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from .llm import OllamaClient

log = logging.getLogger("library-assistant.planner")

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "catalogue_search",
                "faq",
                "research_help",
                "smalltalk",
                "out_of_scope",
            ],
        },
        "index": {
            "type": "string",
            "enum": ["kw", "ti", "au", "su", "isbn", "pb"],
        },
        "search_term": {"type": "string"},
        "corrected_query": {"type": "string"},
        "language": {"type": "string"},
        "alternatives": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["intent", "index", "search_term", "corrected_query"],
}

SYSTEM_PROMPT = """\
You are the query-planner for the National Forensic Sciences University (NFSU) \
library catalogue assistant. Convert the user's message into a single catalogue \
search plan. Output ONLY JSON matching the schema.

Definitions:
- intent:
  * "catalogue_search" - the user wants to find books, journals, theses, \
dissertations or other items in the library.
  * "faq" - the user asks about library services: timings, membership, loan \
rules, fines, library locations, ONOS, remote/e-resource access, etc.
  * "research_help" - the user wants guidance on databases, citation tools, \
scholarly communication, or research strategy (no specific item search).
  * "smalltalk" - greetings, thanks.
  * "out_of_scope" - anything unrelated to the library.

- index: which KOHA search index to use for a catalogue search:
  * "kw" keyword (default — use for general topic searches like "books on X")
  * "ti" title (only when the user explicitly refers to a title)
  * "au" author (only for an author name)
  * "su" subject (only when the user asks about a subject heading)
  * "isbn" ISBN (only for an ISBN number)
  * "pb" publisher (only for a publisher name)

Rules:
- Prefer "kw" unless the user clearly asks for a specific field above.
- search_term: the core terms to search, WITHOUT filler words. Do not include \
the field name (e.g. drop the word "author" when index is "au"). Keep it short \
(2-6 words). Fix obvious spelling mistakes.
- corrected_query: the user's intent restated cleanly in English.
- language: BCP-47 code of the user's language (e.g. "en", "hi").
- alternatives: up to 3 alternative phrasings to try if the first search is empty.

Examples:
User: "Find books on forensic DNA analysis"
{"intent":"catalogue_search","index":"kw","search_term":"forensic DNA analysis",\
"corrected_query":"books on forensic DNA analysis","language":"en",\
"alternatives":["DNA profiling","forensic genetics"]}

User: "books written by John Butler"
{"intent":"catalogue_search","index":"au","search_term":"John Butler",\
"corrected_query":"books by John Butler","language":"en","alternatives":[]}

User: "What are the library opening hours?"
{"intent":"faq","index":"kw","search_term":"opening hours",\
"corrected_query":"library opening hours","language":"en","alternatives":[]}
"""


@dataclass
class Plan:
    intent: str = "catalogue_search"
    index: str = "kw"
    search_term: str = ""
    corrected_query: str = ""
    language: str = "en"
    alternatives: list[str] = field(default_factory=list)
    used_fallback: bool = False


def _heuristic(query: str) -> Plan:
    """Used when the LLM is unavailable or returns unusable JSON."""
    q = re.sub(r"\s+", " ", query).strip()
    ai_match = re.match(r"(?:books|works|publications)\s+(?:written\s+)?by\s+(.+)", q, re.I)
    if ai_match:
        return Plan(index="au", search_term=ai_match.group(1).strip(), corrected_query=q)
    return Plan(index="kw", search_term=q, corrected_query=q, used_fallback=True)


async def plan_query(client: OllamaClient, query: str) -> Plan:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    try:
        data = await client.chat_json(messages, PLAN_SCHEMA, temperature=0.0)
    except Exception as exc:
        log.warning("planner LLM failed: %s", exc)
        return _heuristic(query)

    if not data or not data.get("intent"):
        return _heuristic(query)

    term = (data.get("search_term") or "").strip() or query.strip()
    return Plan(
        intent=data.get("intent", "catalogue_search"),
        index=data.get("index", "kw"),
        search_term=term,
        corrected_query=(data.get("corrected_query") or query).strip(),
        language=(data.get("language") or "en").strip() or "en",
        alternatives=[a for a in (data.get("alternatives") or []) if a][:3],
    )
