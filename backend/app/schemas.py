"""Pydantic request/response models — the API contract with the frontend."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Intent = Literal[
    "catalogue_search",
    "faq",
    "research_help",
    "smalltalk",
    "out_of_scope",
]


class ChatRequest(BaseModel):
    """Input from the OPAC widget.

    Accepts either ``{"text": ...}`` (the browser-extension contract) or
    ``{"query": ...}`` (the richer internal contract).
    """

    text: str | None = Field(default=None, max_length=2000)
    query: str | None = Field(default=None, max_length=2000)
    session_id: str | None = Field(
        default=None, description="Optional client session identifier (analytics only)."
    )

    @model_validator(mode="after")
    def _require_user_text(self) -> "ChatRequest":
        if not (self.text or self.query or "").strip():
            raise ValueError("either 'text' or 'query' must be a non-empty string")
        return self

    @property
    def user_text(self) -> str:
        return (self.text or self.query or "").strip()


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


class Source(BaseModel):
    """A source entry in the browser-extension response contract."""

    url: str | None = None
    description: str = ""
    title: str | None = None


class FrontendResponse(BaseModel):
    """Exact response shape expected by the browser-extension frontend."""

    text_summary: str
    sources: list[Source] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    version: str
    chatbot_enabled: bool
    guard_enabled: bool
    search_backend: str
    llm_model: str
    llm_reachable: bool | None = None
