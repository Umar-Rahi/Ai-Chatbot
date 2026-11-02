"""
AI service — wraps the OpenAI Python SDK pointed at OpenRouter's
OpenAI-compatible API (https://openrouter.ai/api/v1).

Supports both streaming and non-streaming completions.
All provider-specific error conditions are translated into AIServiceError
with a descriptive user-facing message and a machine-readable code.
"""

from __future__ import annotations

import logging
from typing import Generator

from openai import (
    OpenAI,
    OpenAIError,
    AuthenticationError,
    RateLimitError,
    APIConnectionError,
    APIStatusError,
)

from backend.config import Config

logger = logging.getLogger(__name__)

# ── Client (lazy singleton) ───────────────────────────────────────────────────

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Return a cached OpenAI-SDK client aimed at OpenRouter."""
    global _client
    if _client is None:
        if not Config.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is not configured.")
        _client = OpenAI(
            api_key=Config.OPENROUTER_API_KEY,
            base_url=Config.OPENROUTER_BASE_URL,
        )
    return _client


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a helpful, knowledgeable, and friendly AI assistant. "
    "You can help with a wide range of tasks including answering questions, "
    "writing, coding, analysis, brainstorming, and general conversation. "
    "When providing code, always use proper markdown code blocks with the language identifier. "
    "Be concise but thorough. Format responses with markdown when it improves readability."
)


# ── Public interface ──────────────────────────────────────────────────────────

def chat_stream(
    messages: list[dict],
    model: str | None = None,
) -> Generator[str, None, None]:
    """
    Yield response text chunks as they arrive from OpenRouter.

    ``messages`` must be a list of ``{"role": ..., "content": ...}`` dicts.
    The system prompt is prepended automatically unless it is already present.

    Raises :class:`AIServiceError` for all provider-level errors so the
    caller can surface a friendly message without leaking internals.
    """
    effective_model = (
        model if model in Config.ALLOWED_MODELS else Config.OPENROUTER_MODEL
    )

    # Prepend system prompt when not already present
    if not messages or messages[0].get("role") != "system":
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    try:
        client = _get_client()
        stream = client.chat.completions.create(
            model=effective_model,
            messages=messages,  # type: ignore[arg-type]
            stream=True,
            max_tokens=2048,
            temperature=0.7,
        )
        for chunk in stream:
            # OpenRouter may return empty choices on keep-alive ticks
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    except AuthenticationError:
        raise AIServiceError(
            "Authentication failed. Please check your OPENROUTER_API_KEY.",
            code="auth_error",
        )
    except RateLimitError:
        raise AIServiceError(
            "Rate limit exceeded. Please wait a moment and try again.",
            code="rate_limit",
        )
    except APIConnectionError:
        raise AIServiceError(
            "Could not connect to OpenRouter. Check your internet connection.",
            code="connection_error",
        )
    except APIStatusError as exc:
        # Covers 402 (quota exhausted), 503 (model unavailable), etc.
        status = exc.status_code
        if status == 402:
            raise AIServiceError(
                "OpenRouter quota exhausted. Add credits at openrouter.ai.",
                code="quota_exceeded",
            )
        if status == 503:
            raise AIServiceError(
                f"The model '{effective_model}' is currently unavailable. "
                "Try a different model.",
                code="model_unavailable",
            )
        logger.error("OpenRouter API error %s: %s", status, exc.message)
        raise AIServiceError(
            f"Provider error ({status}): {exc.message}",
            code="provider_error",
        ) from exc
    except OpenAIError as exc:
        logger.exception("OpenRouter SDK error during chat_stream")
        raise AIServiceError(str(exc), code="openai_error") from exc
    except ValueError as exc:
        raise AIServiceError(str(exc), code="config_error") from exc


def chat_complete(
    messages: list[dict],
    model: str | None = None,
) -> str:
    """Non-streaming version — returns the full response string."""
    return "".join(chat_stream(messages, model))


def check_api_connection() -> dict:
    """
    Quick probe — returns ``{"ok": bool, "message": str}``.

    Uses a minimal chat completion (non-streaming) rather than
    ``models.list()`` because OpenRouter does not expose a standard
    models endpoint with the same auth semantics.
    """
    if not Config.OPENROUTER_API_KEY:
        return {"ok": False, "message": "API key not configured."}
    try:
        client = _get_client()
        # One-token probe: cheap and works with all OpenRouter models
        client.chat.completions.create(
            model=Config.OPENROUTER_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            stream=False,
        )
        return {"ok": True, "message": "Connected"}
    except AuthenticationError:
        return {"ok": False, "message": "Invalid API key."}
    except APIStatusError as exc:
        if exc.status_code == 402:
            return {"ok": False, "message": "Quota exhausted — add credits."}
        return {"ok": False, "message": f"Provider error ({exc.status_code})."}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


# ── Custom exception ──────────────────────────────────────────────────────────

class AIServiceError(Exception):
    def __init__(self, message: str, code: str = "ai_error"):
        super().__init__(message)
        self.code = code
        self.user_message = message
