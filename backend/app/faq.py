"""Static knowledge base for library-services questions (FAQ intent)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).parent / "data" / "faq.json"
_WORD_RE = re.compile(r"[a-z0-9]+")


@lru_cache
def load_entries() -> list[dict]:
    try:
        data = json.loads(_DATA.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data.get("entries", [])


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def find_entries(query: str, k: int = 3) -> list[dict]:
    """Rank FAQ entries by keyword overlap with the query."""
    qtokens = _tokens(query)
    if not qtokens:
        return []
    scored: list[tuple[float, dict]] = []
    for entry in load_entries():
        keywords = entry.get("keywords", [])
        kset: set[str] = set()
        for kw in keywords:
            kset |= _tokens(kw)
        qset = _tokens(entry.get("question", ""))
        overlap = len(qtokens & kset)
        overlap += 0.5 * len(qtokens & qset)
        # favour entries whose keywords phrase appears verbatim
        for kw in keywords:
            if kw.lower() in query.lower():
                overlap += 1.5
        if overlap > 0:
            scored.append((overlap, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:k]]


def as_context(entries: list[dict]) -> str:
    parts = []
    for e in entries:
        parts.append(f"Q: {e['question']}\nA: {e['answer']}")
    return "\n\n".join(parts)
