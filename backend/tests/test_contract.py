"""Contract tests: request parsing and the browser-extension response shape."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ChatRequest, ChatResponse, Link, Meta
from app.synthesizer import to_frontend


def test_request_accepts_text_field():
    req = ChatRequest(text="find forensic books")
    assert req.user_text == "find forensic books"


def test_request_accepts_query_field():
    req = ChatRequest(query="find forensic books")
    assert req.user_text == "find forensic books"


def test_request_rejects_empty():
    with pytest.raises(ValidationError):
        ChatRequest(text="   ")


def test_to_frontend_maps_summary_and_sources():
    resp = ChatResponse(
        query="q",
        intent="catalogue_search",
        summary="Found 1 record.",
        links=[
            Link(
                title="Forensic DNA Typing",
                url="https://catalog.nfsu.ac.in/cgi-bin/koha/opac-detail.pl?biblionumber=1",
                description="Butler, John M. ISBN 9780121479510.",
            )
        ],
        meta=Meta(total_results=1, showing=1),
    )
    fe = to_frontend(resp)
    assert fe.text_summary == "Found 1 record."
    assert len(fe.sources) == 1
    assert fe.sources[0].url.startswith("https://")
    # Title is baked into the description for the extension card.
    assert fe.sources[0].description.startswith("Forensic DNA Typing —")


def test_to_frontend_drops_non_https_urls():
    resp = ChatResponse(
        query="q",
        summary="s",
        links=[Link(title="t", url="http://insecure.example/x", description="d")],
    )
    fe = to_frontend(resp)
    assert fe.sources[0].url is None
    assert fe.sources[0].description == "t — d"
