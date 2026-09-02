"""
Tool: request_human_approval

The mandatory human-in-the-loop gate.

In MOCK_MODE (default) this tool records a PENDING approval request
and returns immediately with a token. The Streamlit dashboard resolves
the token when the operator clicks Approve or Reject.

In live mode this tool could block or integrate with an external
approval system (PagerDuty, ServiceNow, Slack, etc.).

The agent must NEVER skip this gate for any action with
requires_human_approval=True in the risk assessment.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from strands import tool

from gridguard.config import settings
from gridguard.logger import get_logger

log = get_logger(__name__)

# In-process store for pending approval tokens (used by dashboard and tests).
# In a production deployment this would be a durable queue (SQS, DynamoDB, etc.).
_PENDING_APPROVALS: dict[str, dict[str, Any]] = {}


def get_pending_approval(token: str) -> dict[str, Any] | None:
    """Return the approval record for *token*, or None if not found."""
    return _PENDING_APPROVALS.get(token)


def resolve_approval(token: str, decision: str, approver: str, rationale: str = "") -> bool:
    """
    Resolve a pending approval token.

    Parameters
    ----------
    token:    Approval token returned by request_human_approval.
    decision: 'APPROVED' or 'REJECTED'.
    approver: Name/ID of the human who made the decision.
    rationale: Optional free-text rationale.

    Returns True if the token was found and resolved.
    """
    record = _PENDING_APPROVALS.get(token)
    if record is None:
        return False
    record["decision"] = decision.upper()
    record["approver"] = approver
    record["rationale"] = rationale
    record["resolved_at"] = datetime.now(tz=timezone.utc).isoformat()
    record["status"] = "RESOLVED"
    log.info(
        "Approval resolved",
        extra={"token": token, "decision": decision, "approver": approver},
    )
    return True


def get_all_pending() -> dict[str, dict[str, Any]]:
    """Return all pending (unresolved) approval requests."""
    return {k: v for k, v in _PENDING_APPROVALS.items() if v.get("status") == "PENDING"}


@tool
def request_human_approval(
    work_order_number: Annotated[str, "The work order number requiring approval."],
    event_type: Annotated[str, "The originating event type."],
    region: Annotated[str, "Grid region affected."],
    severity_label: Annotated[str, "Urgency label of the event."],
    priority_tier: Annotated[str, "Priority tier P1–P5."],
    summary: Annotated[str, "Plain-language summary of proposed actions for the approver."],
) -> dict[str, Any]:
    """
    Request explicit human approval before executing any disruptive grid action.

    ⚠️ This is the mandatory Human-in-the-Loop (HITL) gate.

    The agent MUST call this tool before any work order is considered active.
    The returned approval_token must be presented to an authorised operator.
    No field action may proceed until the token is resolved as APPROVED.

    In MOCK_MODE the token is recorded in memory; the dashboard resolves it
    interactively. In live mode this would integrate with an external
    approval workflow system.
    """
    log.info(
        "request_human_approval called",
        extra={"wo": work_order_number, "severity": severity_label},
    )

    token = f"APPR-{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(tz=timezone.utc).isoformat()

    approval_request: dict[str, Any] = {
        "approval_token": token,
        "work_order_number": work_order_number,
        "event_type": event_type,
        "region": region,
        "severity_label": severity_label,
        "priority_tier": priority_tier,
        "summary_for_approver": summary,
        "requested_at": now,
        "status": "PENDING",
        "decision": None,
        "approver": None,
        "rationale": None,
        "resolved_at": None,
        "mock_mode": settings.MOCK_MODE,
        "instruction": (
            "An authorised operator MUST review the work order and either APPROVE "
            "or REJECT before any field action is initiated. "
            "Use the dashboard Approve / Reject buttons to resolve this token."
        ),
    }

    _PENDING_APPROVALS[token] = approval_request
    log.info(
        "Approval request registered",
        extra={"token": token, "wo": work_order_number},
    )
    return approval_request
