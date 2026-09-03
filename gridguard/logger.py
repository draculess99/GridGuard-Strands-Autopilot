"""
Structured JSON logger for GridGuard Autopilot.
Outputs one JSON object per line — easy to parse, grep, and ship to CloudWatch.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from gridguard.config import settings
from gridguard.safeguards import redact_secrets


class _JSONFormatter(logging.Formatter):
    """Format every log record as a single JSON line with sensitive secrets redacted."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        raw_msg = record.getMessage()
        payload: dict[str, Any] = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_secrets(raw_msg),
        }
        if record.exc_info:
            payload["exc"] = redact_secrets(self.formatException(record.exc_info))
        if hasattr(record, "extra"):
            payload.update(redact_secrets(record.extra))
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return a structured JSON logger for *name*."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
