"""FastAPI entrypoint for the NFSU Library Research Assistant.

Pipeline (single pass, no agentic loop):

    guard -> planner -> KOHA client -> synthesiser -> JSON

Two chat endpoints are exposed:

* ``POST /``          – the browser-extension contract
  (``{"text": ...}`` → ``{"text_summary": ..., "sources": [...]}``).
* ``POST /api/chat``  – the richer contract
  (``{"query"|"text": ...}`` → ``{summary, links, suggestions, meta}``).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_settings
from .pipeline import Pipeline
from .schemas import (
    ChatRequest,
    ChatResponse,
    FrontendResponse,
    HealthResponse,
    Meta,
    PublicConfig,
)
from .synthesizer import to_frontend

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("library-assistant")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pipeline = Pipeline(settings)
    log.info(
        "pipeline ready (backend=%s model=%s guard=%s)",
        settings.search_backend,
        settings.ollama_model,
        settings.guard_enabled,
    )
    # Warm the guard and the LLM in the background so the first request is fast.
    asyncio.create_task(app.state.pipeline.warmup())
    yield


app = FastAPI(
    title="NFSU Library Research Assistant",
    version=__version__,
    description=(
        "Conversational assistant for the NFSU KOHA OPAC. Accepts a natural-language "
        "query and returns a summary plus relevant resource links as JSON."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

WELCOME_MESSAGE = (
    "Hello! I'm the NFSU Library assistant. Ask me to find books, journals, "
    "theses or other resources, or ask about library services."
)

SUGGESTED_QUESTIONS = [
    "Find books on forensic DNA analysis",
    "Show books on cybercrime investigation",
    "What are the library opening hours?",
    "Do you have journals on forensic toxicology?",
]


async def _run(request: ChatRequest) -> ChatResponse:
    if not settings.chatbot_enabled:
        return ChatResponse(
            query=request.user_text,
            intent="out_of_scope",
            summary=(
                "The library assistant is temporarily unavailable. Please use the "
                "classic catalogue search."
            ),
            links=[],
            suggestions=[],
            meta=Meta(source="disabled"),
        )
    pipeline: Pipeline = app.state.pipeline
    return await pipeline.handle(request)


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    pipeline: Pipeline = app.state.pipeline
    reachable = await pipeline.llm.is_reachable()
    return HealthResponse(
        status="ok",
        version=__version__,
        chatbot_enabled=settings.chatbot_enabled,
        guard_enabled=settings.guard_enabled,
        search_backend=settings.search_backend,
        llm_model=settings.ollama_model,
        llm_reachable=reachable,
    )


@app.get("/api/config", response_model=PublicConfig, tags=["system"])
async def public_config() -> PublicConfig:
    """Frontend reads this to decide whether to show the widget."""
    return PublicConfig(
        enabled=settings.chatbot_enabled,
        version=__version__,
        welcome_message=WELCOME_MESSAGE,
        suggested_questions=SUGGESTED_QUESTIONS,
    )


@app.post("/", response_model=FrontendResponse, tags=["chat"])
async def chat_root(request: ChatRequest) -> FrontendResponse:
    """Browser-extension endpoint: ``{text}`` -> ``{text_summary, sources}``."""
    return to_frontend(await _run(request))


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    """Rich endpoint used by the reference widget and tests."""
    return await _run(request)
