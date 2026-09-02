"""
Tool: draft_work_order

Formats a structured work order document ready for operator review.
The work order is a DRAFT — it must be explicitly approved by a human
before any field action is initiated.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from strands import tool

from gridguard.logger import get_logger

log = get_logger(__name__)

_PRIORITY_RESPONSE_TIMES: dict[str, str] = {
    "P1": "Immediate (within 15 minutes)",
    "P2": "Urgent (within 1 hour)",
    "P3": "High (within 4 hours)",
    "P4": "Routine (within 24 hours)",
    "P5": "Low (within 5 business days)",
}


@tool
def draft_work_order(
    event_type: Annotated[str, "The grid-risk event type."],
    event_id: Annotated[str, "Unique identifier from the originating event."],
    region: Annotated[str, "Grid region identifier."],
    priority_tier: Annotated[str, "Priority tier from risk assessment: P1–P5."],
    severity_label: Annotated[str, "Urgency label: CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL."],
    plan_id: Annotated[str, "Mitigation plan ID to attach to this work order."],
    mitigation_steps: Annotated[list[dict], "Ordered list of mitigation steps from the plan."],
    affected_assets: Annotated[list[str], "Asset IDs that require field attention."] = [],
    notes: Annotated[str, "Optional additional notes from the agent."] = "",
) -> dict[str, Any]:
    """
    Draft a structured work order for operator review and approval.

    ⚠️ This work order is a DRAFT. No field action should be initiated
    until an authorised human operator has explicitly approved it.
    The approval gate is enforced by the request_human_approval tool.
    """
    log.info("draft_work_order called", extra={"event_id": event_id, "priority": priority_tier})

    wo_number = f"WO-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(tz=timezone.utc)

    work_order: dict[str, Any] = {
        "work_order_number": wo_number,
        "status": "DRAFT_PENDING_APPROVAL",
        "created_at": now.isoformat(),
        "created_by": "GridGuard-Strands-Autopilot (autonomous draft)",
        # ── Classification ─────────────────────────────────────────────
        "event_type": event_type,
        "event_id": event_id,
        "region": region,
        "priority_tier": priority_tier,
        "severity_label": severity_label,
        "required_response_time": _PRIORITY_RESPONSE_TIMES.get(priority_tier, "As appropriate"),
        # ── Scope ──────────────────────────────────────────────────────
        "mitigation_plan_id": plan_id,
        "affected_assets": affected_assets,
        "work_description": (
            f"Respond to {event_type.replace('_', ' ').title()} event in region {region}. "
            f"Execute {len(mitigation_steps)} mitigation step(s) per plan {plan_id}."
        ),
        "ordered_steps": mitigation_steps,
        "special_instructions": notes or "None",
        # ── Safety & Compliance ─────────────────────────────────────────
        "safety_notice": (
            "All field work must comply with OSHA 1910.269 and utility safety rules. "
            "Live-line work requires a separate Job Hazard Analysis (JHA)."
        ),
        "requires_human_approval": True,
        "approval_authority": "Shift Manager or designate",
        "approval_token": None,  # populated by request_human_approval
        # ── Metadata ───────────────────────────────────────────────────
        "data_source": "SYNTHETIC_DEMO",
    }

    log.info(
        "draft_work_order completed",
        extra={"wo_number": wo_number, "status": "DRAFT_PENDING_APPROVAL"},
    )
    return work_order
