"""Thin async client for a local Ollama server."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

log = logging.getLogger("library-assistant.llm")


class OllamaClient:
    def __init__(
        self,
        host: str,
        model: str,
        *,
        timeout: float = 120.0,
        think: bool | None = False,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.think = think

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.1,
        num_predict: int = 256,
        keep_alive: str = "30m",
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
        if self.think is not None:
            # Disable long reasoning traces for thinking models (qwen3.x etc.).
            payload["think"] = self.think
        if schema is not None:
            # Ollama constrains output to this JSON schema.
            payload["format"] = schema

        url = f"{self.host}/api/chat"
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.post(url, json=payload)
            if resp.status_code >= 400 and "think" in payload:
                # Some models don't support the think flag; retry without it.
                payload.pop("think", None)
                resp = await c.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return (data.get("message") or {}).get("content", "")

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        temperature: float = 0.1,
        num_predict: int = 256,
    ) -> dict[str, Any]:
        content = await self.chat(
            messages,
            schema=schema,
            temperature=temperature,
            num_predict=num_predict,
        )
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            log.warning("model returned non-JSON: %r", content[:200])
            return {}

    async def is_reachable(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                resp = await c.get(f"{self.host}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
