"""
Configuration module — reads all settings from environment variables.
Never put secrets in this file directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── OpenRouter ────────────────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openrouter/auto")

    # Free-tier models shown in the UI model selector.
    # These are the only options exposed to users — no paid models selectable.
    FREE_MODELS: list[str] = [
        "openrouter/auto",
        "openrouter/free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "google/gemma-3-27b-it:free",
        "deepseek/deepseek-r1:free",
        "qwen/qwen3-235b-a22b:free",
    ]

    # Full allowed model list — includes paid models that can be configured
    # via OPENROUTER_MODEL env var but are NOT exposed in the UI selector.
    ALLOWED_MODELS: list[str] = FREE_MODELS + [
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
        "anthropic/claude-3.5-sonnet",
    ]

    # ── Conversation context ──────────────────────────────────────────────────
    MAX_CONTEXT_MESSAGES: int = int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))
    MAX_MESSAGE_LENGTH: int = int(os.getenv("MAX_MESSAGE_LENGTH", "4000"))

    # ── Flask ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", os.urandom(32).hex())
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # ── Database ──────────────────────────────────────────────────────────────
    DB_PATH: str = os.getenv("DB_PATH", "chatbot.db")

    # ── Rate limiting (requests per minute per IP) ────────────────────────────
    RATE_LIMIT: int = int(os.getenv("RATE_LIMIT", "30"))

    @classmethod
    def validate(cls) -> list[str]:
        """Return a list of configuration warnings."""
        warnings: list[str] = []
        if not cls.OPENROUTER_API_KEY:
            warnings.append("OPENROUTER_API_KEY is not set — AI responses will not work.")
        if cls.OPENROUTER_MODEL not in cls.ALLOWED_MODELS:
            warnings.append(
                f"OPENROUTER_MODEL '{cls.OPENROUTER_MODEL}' is not in the allowed list. "
                f"Falling back to openrouter/auto."
            )
            cls.OPENROUTER_MODEL = "openrouter/auto"
        # Re-read the env var in case it was set after import (e.g. dotenv reload)
        env_model = os.getenv("OPENROUTER_MODEL", "")
        if env_model and env_model in cls.ALLOWED_MODELS:
            cls.OPENROUTER_MODEL = env_model
        return warnings
