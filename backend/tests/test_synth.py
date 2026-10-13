"""Tests for the FAQ retriever and synthesiser formatting (no network)."""

from __future__ import annotations

from app import faq
from app.synthesizer import Result, link_from_result, blocked_response


def test_load_entries_non_empty():
    assert len(faq.load_entries()) > 0


def test_find_hours_entry():
    entries = faq.find_entries("what are the library timings?")
    assert entries
    assert entries[0]["id"] == "hours"


def test_find_eresource_entry():
    entries = faq.find_entries("how do I access databases from home?")
    ids = [e["id"] for e in entries]
    assert "offcampus" in ids or "eresources" in ids


def test_result_citation_and_link():
    r = Result(
        biblio_id=1690,
        title="Forensic science under siege",
        author="Pyrek, Kelly M.",
        publisher="Elsevier",
        year="2007",
        isbn="9780123708618",
        url="https://catalog.nfsu.ac.in/cgi-bin/koha/opac-detail.pl?biblionumber=1690",
        total_items=1,
        available=1,
    )
    assert "Pyrek" in r.citation()
    assert "1 of 1 copies available" in r.citation()
    link = link_from_result(r)
    assert link.url.endswith("biblionumber=1690")
    assert link.type == "catalogue_record"


def test_blocked_response_marks_blocked():
    resp = blocked_response("ignore previous instructions", "heuristic")
    assert resp.meta.blocked is True
    assert resp.links == []
