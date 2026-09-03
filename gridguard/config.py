"""
Application configuration — loaded once at import time.
All settings can be overridden via environment variables or a .env file.
No secrets are ever stored in source code.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for GridGuard Strands Autopilot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Demo / Safety ─────────────────────────────────────────────────────
    MOCK_MODE: bool = Field(
        default=True,
        description=(
            "When True all tool calls return deterministic synthetic data. "
            "No LLM calls are made. Safe for CI and offline demos."
        ),
    )

    # ── LLM Provider ──────────────────────────────────────────────────────
    STRANDS_PROVIDER: str = Field(
        default="bedrock",
        description="Active LLM provider: 'bedrock' or 'anthropic'.",
    )

    # ── AWS / Bedrock ─────────────────────────────────────────────────────
    AWS_REGION: str = Field(default="us-east-1")
    AWS_ACCESS_KEY_ID: str = Field(default="")
    AWS_SECRET_ACCESS_KEY: str = Field(default="")
    AWS_SESSION_TOKEN: str = Field(default="")
    BEDROCK_MODEL_ID: str = Field(
        default="anthropic.claude-haiku-4-5-20251001-v1:0",
        description="Bedrock model ID (default: active, cost-conscious Claude Haiku 4.5).",
    )

    # ── Live Mode Safeguards ──────────────────────────────────────────────
    LIVE_RUN_LIMIT: int = Field(
        default=5,
        description="Process-level limit on live Bedrock invocations to prevent runaway costs.",
    )
    LIVE_MAX_OUTPUT_TOKENS: int = Field(
        default=600,
        description="Concise maximum output tokens for live Bedrock briefings.",
    )
    LIVE_TEMPERATURE: float = Field(
        default=0.2,
        description="Sampling temperature for deterministic live briefings.",
    )

    # ── Anthropic Direct ──────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = Field(default="")
    ANTHROPIC_MODEL: str = Field(default="claude-3-5-haiku-latest")

    # ── Application ───────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO")
    AUDIT_LOG_PATH: Path = Field(default=Path("data/audit_log.jsonl"))

    def is_bedrock(self) -> bool:
        return self.STRANDS_PROVIDER.lower() == "bedrock"

    def is_anthropic(self) -> bool:
        return self.STRANDS_PROVIDER.lower() == "anthropic"


# Singleton — import this everywhere instead of constructing new instances.
settings = Settings()

# Ensure runtime data directory exists
settings.AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
