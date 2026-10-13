"""Application configuration loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- KOHA ----
    koha_base_url: str = "https://catalog.nfsu.ac.in"
    search_backend: Literal["rss", "rest"] = "rss"
    koha_api_user: str = ""
    koha_api_pass: str = ""
    max_results: int = 5
    koha_timeout: float = 20.0

    # ---- LLM ----
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_timeout: float = 120.0

    # ---- Guard ----
    guard_enabled: bool = True
    guard_model: str = "meta-llama/Llama-Prompt-Guard-2-86M"
    guard_threshold: float = 0.5

    # ---- Service ----
    chatbot_enabled: bool = True
    allowed_origins: str = "*"
    host: str = "0.0.0.0"
    port: int = 5000
    log_level: str = "INFO"

    @property
    def koha_base(self) -> str:
        return self.koha_base_url.rstrip("/")

    @property
    def origins(self) -> list[str]:
        raw = self.allowed_origins.strip()
        if not raw or raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
