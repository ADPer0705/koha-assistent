"""Prompt-injection guard.

Primary classifier: ``meta-llama/Llama-Prompt-Guard-2-86M`` via transformers.
If the model/deps are unavailable, a conservative regex heuristic is used so the
pipeline keeps working.

Only the raw user query is classified. Malicious input is rejected before it
ever reaches the planner LLM.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

log = logging.getLogger("library-assistant.guard")

# Conservative patterns for the fallback path.
_INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above|earlier) (instructions|prompts|rules)",
    r"disregard (all )?(previous|prior|above|earlier) (instructions|prompts|rules)",
    r"(reveal|show|print|repeat|output) (me )?(your |the )?(system |initial )?prompt",
    r"you are now|from now on,? you (are|will)",
    r"(developer|debug|jailbreak|god|dan) mode",
    r"no (rules|restrictions|filters|limitations)",
    r"override (your|the) (instructions|safety|rules|guardrails)",
    r"act as (an? )?(unrestricted|unfiltered|different)",
    r"prompt injection|forget (everything|your instructions)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

_SAFE_REFUSAL = (
    "I can only help with library resources and services. That request looks like "
    "it is trying to change my instructions, so I can't act on it. Try asking me "
    "to find a book or about library services."
)


@dataclass
class GuardResult:
    allowed: bool
    malicious: bool
    score: float
    reason: str
    source: str  # prompt_guard | heuristic | disabled | unavailable

    @property
    def refusal(self) -> str:
        return _SAFE_REFUSAL


class PromptGuard:
    def __init__(
        self,
        *,
        enabled: bool = True,
        model_name: str = "meta-llama/Llama-Prompt-Guard-2-86M",
        threshold: float = 0.5,
    ) -> None:
        self.enabled = enabled
        self.model_name = model_name
        self.threshold = threshold
        self._pipe = None
        self._load_error: str | None = None
        self._lock = asyncio.Lock()
        self._load_attempted = False

    @property
    def loaded(self) -> bool:
        return self._pipe is not None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    async def load(self) -> None:
        """Load the classifier once (blocking work runs in a thread)."""
        if not self.enabled or self._load_attempted:
            return
        async with self._lock:
            if self._load_attempted:
                return
            self._load_attempted = True
            try:
                self._pipe = await asyncio.to_thread(self._load_pipeline)
                log.info("Prompt Guard loaded: %s", self.model_name)
            except Exception as exc:  # optional dependency / missing weights
                self._load_error = str(exc)
                log.warning(
                    "Prompt Guard unavailable (%s); using heuristic fallback", exc
                )

    def _load_pipeline(self):
        from transformers import pipeline  # imported lazily

        return pipeline(
            "text-classification",
            model=self.model_name,
            device=-1,  # CPU
            truncation=True,
            max_length=512,
        )

    async def check(self, text: str) -> GuardResult:
        if not self.enabled:
            return GuardResult(True, False, 0.0, "guard disabled", "disabled")

        if not self._load_attempted:
            await self.load()

        if self._pipe is not None:
            try:
                out = await asyncio.to_thread(self._pipe, text)
                top = out[0] if isinstance(out, list) else out
                return self._interpret(top)
            except Exception as exc:  # pragma: no cover - runtime safety net
                log.warning("Prompt Guard inference failed: %s", exc)

        return self._heuristic(text)

    def _interpret(self, top: dict) -> GuardResult:
        label = str(top.get("label", "")).upper()
        score = float(top.get("score", 0.0))
        # Prompt Guard uses LABEL_0=benign / LABEL_1=malicious (sometimes named).
        if "MALICIOUS" in label or label.endswith("_1") or label == "1":
            malicious = score >= self.threshold
            return GuardResult(
                allowed=not malicious,
                malicious=malicious,
                score=score,
                reason="prompt_guard",
                source="prompt_guard",
            )
        return GuardResult(True, False, score, "prompt_guard:benign", "prompt_guard")

    def _heuristic(self, text: str) -> GuardResult:
        m = _INJECTION_RE.search(text or "")
        if m:
            return GuardResult(
                allowed=False,
                malicious=True,
                score=1.0,
                reason=f"heuristic:{m.group(0)}",
                source="heuristic",
            )
        return GuardResult(True, False, 0.0, "heuristic:clean", "heuristic")
