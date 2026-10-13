"""Pydantic request/response models — the API contract with the frontend."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Intent = Literal[
    "catalogue_search",
    "faq",
    "research_help",
    "smalltalk",
    "out_of_scope",
]


class ChatRequest(BaseModel):
    """Input from the OPAC widget: a single natural-language query."""

    query: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(
        default=None, description="Optional client session identifier (analytics only)."
    )


class Link(BaseModel):
    """A single result link returned to the frontend."""

    title: str
    url: str
    description: str = ""
    type: str = "catalogue_record"


class Meta(BaseModel):
    total_results: int = 0
    showing: int = 0
    catalogue_search_url: str | None = None
    source: str = "koha_opac"
    blocked: bool = False


class ChatResponse(BaseModel):
    """Output consumed by the frontend."""

    query: str
    intent: Intent = "catalogue_search"
    summary: str
    links: list[Link] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    meta: Meta = Field(default_factory=Meta)


class PublicConfig(BaseModel):
    enabled: bool
    version: str
    welcome_message: str | None = None
    suggested_questions: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    version: str
    chatbot_enabled: bool
    guard_enabled: bool
    search_backend: str
    llm_model: str
    llm_reachable: bool | None = None
