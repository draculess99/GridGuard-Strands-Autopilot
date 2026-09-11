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
        description="Active LLM provider: 'bedrock', 'anthropic', or 'groq'.",
    )

    # ── AWS / Bedrock ─────────────────────────────────────────────────────
    AWS_REGION: str = Field(default="us-east-1")
    AWS_ACCESS_KEY_ID: str = Field(default="")
    AWS_SECRET_ACCESS_KEY: str = Field(default="")
    AWS_SESSION_TOKEN: str = Field(default="")
    BEDROCK_MODEL_ID: str = Field(
        default="amazon.nova-lite-v1:0",
        description="Bedrock model ID (default: amazon.nova-lite-v1:0, AWS-native and cost-conscious).",
    )
    BEDROCK_FALLBACK_MODEL_ID: str = Field(
        default="amazon.nova-micro-v1:0",
        description="Fallback Bedrock model ID if the primary model fails (default: amazon.nova-micro-v1:0).",
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

    # ── Groq (optional live demo provider) ───────────────────────────────────
    # Requires MOCK_MODE=false, LIVE_LLM_ENABLED=true, STRANDS_PROVIDER=groq,
    # and a non-empty GROQ_API_KEY.
    GROQ_API_KEY: str = Field(
        default="",
        description="Groq API key. Never printed, logged, or committed.",
    )
    GROQ_MODEL_ID: str = Field(
        default="openai/gpt-oss-20b",
        description="Groq model ID for the optional live demo briefing.",
    )

    # ── Live Demo Gate ────────────────────────────────────────────────────
    LIVE_LLM_ENABLED: bool = Field(
        default=False,
        description=(
            "Master switch for any live LLM path (Groq or Bedrock). "
            "Must be True together with MOCK_MODE=false, the correct provider, "
            "and provider credentials."
        ),
    )

    # ── Application ───────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO")
    AUDIT_LOG_PATH: Path = Field(default=Path("data/audit_log.jsonl"))

    def is_bedrock(self) -> bool:
        return self.STRANDS_PROVIDER.lower() == "bedrock"

    def is_anthropic(self) -> bool:
        return self.STRANDS_PROVIDER.lower() == "anthropic"

    def is_groq(self) -> bool:
        return self.STRANDS_PROVIDER.lower() == "groq"


# Singleton — import this everywhere instead of constructing new instances.
settings = Settings()

# Ensure runtime data directory exists
settings.AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
