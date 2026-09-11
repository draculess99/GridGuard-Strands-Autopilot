"""
GridGuard Safeguards — Cost Control, Run Limits, and Secret Redaction.

Protects against unintended cloud spend and credential leaks in live mode.
"""

from __future__ import annotations

import re
import threading
from typing import Any

from gridguard.config import settings


class LiveRunLimitExceededError(RuntimeError):
    """Raised when the process-level live run limit has been reached."""


class LiveModeCredentialsError(RuntimeError):
    """Raised when AWS credentials cannot be found or resolved."""


class LiveModeModelAccessError(RuntimeError):
    """Raised when the specified model is not enabled or access is denied."""


# ── Process-level Live Run Counter ────────────────────────────────────────────

_counter_lock = threading.Lock()
_live_run_counter: int = 0


def get_live_run_count() -> int:
    """Return the number of live Bedrock calls made in this process session."""
    with _counter_lock:
        return _live_run_counter


def reset_live_run_counter() -> None:
    """Reset the process-level live run counter (used in tests)."""
    global _live_run_counter
    with _counter_lock:
        _live_run_counter = 0


def increment_and_check_live_run_limit() -> int:
    """
    Increment the process live-run counter.

    Raises
    ------
    LiveRunLimitExceededError
        If the incremented count exceeds settings.LIVE_RUN_LIMIT.
    """
    global _live_run_counter
    with _counter_lock:
        if _live_run_counter >= settings.LIVE_RUN_LIMIT:
            raise LiveRunLimitExceededError(
                f"Process live run limit reached ({_live_run_counter}/{settings.LIVE_RUN_LIMIT}). "
                "To protect against unexpected cloud charges, no further live Bedrock calls will be made. "
                "Restart the application or increase LIVE_RUN_LIMIT in .env."
            )
        _live_run_counter += 1
        return _live_run_counter


# ── Secret Redaction ──────────────────────────────────────────────────────────

_SECRET_PATTERNS = [
    # AWS Secret Access Key pattern (40 characters base64)
    re.compile(r"(?i)(aws_secret_access_key|secret_key|secret_access_key)\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{30,45})['\"]?"),
    # AWS Access Key ID pattern (starts with AKIA or ASIA)
    re.compile(r"(?i)(aws_access_key_id|access_key_id)\s*[:=]\s*['\"]?(A[SK]IA[0-9A-Z]{16})['\"]?"),
    # Anthropic API Key pattern
    re.compile(r"(?i)(anthropic_api_key|api_key)\s*[:=]\s*['\"]?(sk-ant-[a-zA-Z0-9_-]{20,})['\"]?"),
    # Generic bearer / session token patterns
    re.compile(r"(?i)(aws_session_token|session_token|bearer\s+token)\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40,})['\"]?"),
]

_SENSITIVE_KEY_NAMES = {
    "aws_secret_access_key",
    "aws_session_token",
    "anthropic_api_key",
    "groq_api_key",
    "api_key",
    "secret_key",
    "secret",
    "password",
}


def redact_secrets(obj: Any) -> Any:
    """
    Recursively redact known secrets and sensitive keys from strings, dicts, or lists.
    Preserves non-secret operational identifiers (e.g. approval tokens APPR-...).
    """
    if isinstance(obj, str):
        redacted = obj
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub(r"\1: [REDACTED]", redacted)
        return redacted

    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if str(k).lower() in _SENSITIVE_KEY_NAMES:
                out[k] = "[REDACTED]"
            else:
                out[k] = redact_secrets(v)
        return out

    if isinstance(obj, list):
        return [redact_secrets(item) for item in obj]

    return obj


def validate_groq_live_gate() -> None:
    """
    Enforce every required condition before allowing a live Groq briefing.

    Raises RuntimeError with a clear, provider-accurate message if any
    condition is not satisfied.

    Gate conditions (all must be True):
        1. settings.MOCK_MODE is False
        2. settings.LIVE_LLM_ENABLED is True
        3. settings.STRANDS_PROVIDER == 'groq'
        4. settings.GROQ_API_KEY is non-empty
    """
    if settings.MOCK_MODE:
        raise RuntimeError(
            "Groq live briefing unavailable — MOCK_MODE is on. Set MOCK_MODE=false to enable."
        )
    if not settings.LIVE_LLM_ENABLED:
        raise RuntimeError(
            "Groq live briefing unavailable — LIVE_LLM_ENABLED is false. "
            "Set LIVE_LLM_ENABLED=true in .env to enable."
        )
    if not settings.is_groq():
        raise RuntimeError(
            f"Groq live briefing unavailable — STRANDS_PROVIDER is '{settings.STRANDS_PROVIDER}'. "
            "Set STRANDS_PROVIDER=groq to enable."
        )
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "Groq live briefing unavailable — GROQ_API_KEY is not configured."
        )
