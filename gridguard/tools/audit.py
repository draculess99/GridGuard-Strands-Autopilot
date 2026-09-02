"""
Tool: record_audit_event

Writes an immutable, append-only audit record to the JSONL audit log.
Every significant action in the workflow — tool calls, approvals,
rejections — must produce an audit entry.

Design principles:
- Records are append-only (never updated or deleted).
- Each record has a unique event_id and a SHA-256 hash of its content
  to support tamper-detection in post-incident reviews.
- The log format is JSONL: one JSON object per line, easy to ship to
  CloudWatch Logs, S3, or any SIEM.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from strands import tool

from gridguard.config import settings
from gridguard.logger import get_logger

log = get_logger(__name__)


def _hash_record(record: dict[str, Any]) -> str:
    """Return a SHA-256 hex digest of the record (excluding the hash field itself)."""
    payload = {k: v for k, v in record.items() if k != "record_hash"}
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _write_record(record: dict[str, Any], path: Path) -> None:
    """Append *record* as a single JSON line to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def read_audit_log(path: Path | None = None) -> list[dict[str, Any]]:
    """Read and return all records from the audit log (for dashboard display)."""
    target = path or settings.AUDIT_LOG_PATH
    if not target.exists():
        return []
    records = []
    with target.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # skip malformed lines
    return records


@tool
def record_audit_event(
    action: Annotated[str, "Short action label, e.g. 'RISK_ASSESSED', 'WORK_ORDER_DRAFTED', 'APPROVAL_REQUESTED', 'APPROVED', 'REJECTED'."],
    actor: Annotated[str, "Who performed the action: 'AGENT', 'OPERATOR:<name>', 'SYSTEM'."],
    event_type: Annotated[str, "The originating grid-risk event type."],
    event_id: Annotated[str, "The originating event ID."],
    work_order_number: Annotated[str, "Associated work order number, or 'N/A'."],
    outcome: Annotated[str, "Outcome description, e.g. 'Severity P2 assessed', 'WO-XXXX drafted', 'Approved by Jane Smith'."],
    details: Annotated[dict, "Any additional structured context to persist."] = {},
) -> dict[str, Any]:
    """
    Write an immutable audit record to the append-only event log.

    Every tool invocation in the workflow should produce one audit record.
    Approval decisions (APPROVED / REJECTED) must always be audited.
    Records include a content hash to support tamper-detection.
    """
    log.info(
        "record_audit_event called",
        extra={"action": action, "actor": actor, "outcome": outcome},
    )

    record: dict[str, Any] = {
        "audit_event_id": f"AUD-{uuid.uuid4().hex[:12].upper()}",
        "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
        "action": action,
        "actor": actor,
        "event_type": event_type,
        "event_id": event_id,
        "work_order_number": work_order_number,
        "outcome": outcome,
        "details": details,
        "data_source": "SYNTHETIC_DEMO",
    }
    record["record_hash"] = _hash_record(record)

    try:
        _write_record(record, settings.AUDIT_LOG_PATH)
        record["persisted"] = True
        log.info(
            "Audit record written",
            extra={"audit_id": record["audit_event_id"], "path": str(settings.AUDIT_LOG_PATH)},
        )
    except OSError as exc:
        record["persisted"] = False
        record["persist_error"] = str(exc)
        log.error("Failed to write audit record", extra={"error": str(exc)})

    return record
