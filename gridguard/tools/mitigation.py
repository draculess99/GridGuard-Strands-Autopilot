"""
Tool: generate_mitigation_steps

Produces a prioritised, ordered list of mitigation actions for a given
event type and risk assessment. Steps are derived from runbook data
plus risk-level overrides — no LLM call required.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from strands import tool

from gridguard.logger import get_logger

log = get_logger(__name__)

# Urgency → additional advisory header
_URGENCY_HEADERS: dict[str, str] = {
    "CRITICAL": (
        "🚨 CRITICAL — All steps below must begin IMMEDIATELY. "
        "Shift Manager must be on bridge. Do not defer any action."
    ),
    "HIGH": (
        "⚠️ HIGH — Begin steps within the timeframes shown. "
        "Shift Manager must be notified before Step 1."
    ),
    "MEDIUM": (
        "📋 MEDIUM — Execute steps in order within stated timeframes. "
        "Monitor for escalation triggers."
    ),
    "LOW": (
        "ℹ️ LOW — Routine response. Follow standard procedures."
    ),
    "INFORMATIONAL": (
        "ℹ️ INFORMATIONAL — Monitor and document. No immediate action required."
    ),
}

# Per-event-type base mitigation catalogue
_MITIGATION_CATALOGUE: dict[str, list[dict[str, Any]]] = {
    "SEVERE_WEATHER": [
        {"step": 1, "action": "Activate Storm Level staffing and open Storm Bridge line.", "timeframe": "Immediate", "responsible": "Shift Manager"},
        {"step": 2, "action": "Assess contingency reserve — if < 1,500 MW initiate emergency capacity procurement and call up fast-start reserves.", "timeframe": "< 30 min", "responsible": "System Operator"},
        {"step": 3, "action": "Defer or reschedule all non-critical planned outages in storm path.", "timeframe": "< 1 hour", "responsible": "Outage Coordinator"},
        {"step": 4, "action": "Pre-position field restoration crews at strategic depots and confirm mutual aid agreements.", "timeframe": "T-12 hours", "responsible": "Field Ops Manager"},
        {"step": 5, "action": "Dispatch emergency patrol crews to inspect icing and structural loading on line LINE-N12 and substation SS-BURLINGTON-3.", "timeframe": "< 2 hours", "responsible": "Field Ops Supervisor"},
        {"step": 6, "action": "Issue Demand Response notification to enrolled participants to initiate peak load curtailment.", "timeframe": "T-6 hours", "responsible": "Customer Operations"},
        {"step": 7, "action": "Issue 2-hourly situation reports to all stakeholders until event clears.", "timeframe": "Ongoing", "responsible": "Operations Centre"},
    ],
    "HIGH_DEMAND": [
        {"step": 1, "action": "Verify SCADA telemetry against backup metering to confirm reserve deficiency.", "timeframe": "Immediate", "responsible": "System Operator"},
        {"step": 2, "action": "Activate Tier-1 Demand Response curtailment signals to interruptible participants.", "timeframe": "< 15 min", "responsible": "DR Coordinator"},
        {"step": 3, "action": "Contact neighbouring BAs for emergency energy purchases; call up spinning reserves.", "timeframe": "< 30 min", "responsible": "System Operator"},
        {"step": 4, "action": "Notify ISO/RTO per tariff requirements. Log call time and reference number.", "timeframe": "< 30 min", "responsible": "Shift Manager"},
        {"step": 5, "action": "Pre-stage rotating outage blocks if reserve < 500 MW — DO NOT execute without Shift Manager authorisation.", "timeframe": "Conditional", "responsible": "Shift Manager"},
    ],
    "EQUIPMENT_RISK": [
        {"step": 1, "action": "Cross-reference DGA alert with previous samples; dispatch substation technician for visual inspection.", "timeframe": "< 4 hours", "responsible": "Asset Engineer"},
        {"step": 2, "action": "Run N-1 contingency analysis for affected asset; identify backup switching paths.", "timeframe": "< 2 hours", "responsible": "System Operator"},
        {"step": 3, "action": "Create high-priority work order for DGA oil sampling, thermal imaging, and bushing power-factor test within 72 hours.", "timeframe": "< 8 hours", "responsible": "Maintenance Planning"},
        {"step": 4, "action": "If Health Index < 0.50 or acetylene > 100 ppm: prepare switching order to de-energise unit. Requires Shift Manager approval.", "timeframe": "Conditional", "responsible": "Shift Manager"},
    ],
    "OUTAGE_WARNING": [
        {"step": 1, "action": "Place HOLD flag on all conflicting OMS outage tickets; notify field crews and planners immediately.", "timeframe": "Immediate", "responsible": "Outage Coordinator"},
        {"step": 2, "action": "Run N-1 power-flow contingency study for all conflicting outage permutations.", "timeframe": "< 2 hours", "responsible": "Planning Engineer"},
        {"step": 3, "action": "Negotiate reschedule of lower-priority outage; update OMS and notify all affected parties.", "timeframe": "< 4 hours", "responsible": "Outage Coordinator"},
        {"step": 4, "action": "Document conflict root cause and corrective action in OMS for process improvement review.", "timeframe": "< 24 hours", "responsible": "Shift Manager"},
    ],
}


@tool
def generate_mitigation_steps(
    event_type: Annotated[str, "The grid-risk event type."],
    severity_label: Annotated[str, "Urgency label from risk assessment: CRITICAL, HIGH, MEDIUM, LOW, or INFORMATIONAL."],
    severity_score: Annotated[int, "Numeric severity score 1–5."],
    region: Annotated[str, "Grid region identifier."],
    affected_assets: Annotated[list[str], "List of affected asset IDs."] = [],
) -> dict[str, Any]:
    """
    Generate a prioritised list of operational mitigation steps for the event.

    Steps are selected from the runbook catalogue and adjusted based on
    the severity level. Returns an ordered MitigationPlan ready for
    operator review and work-order drafting.
    """
    log.info(
        "generate_mitigation_steps called",
        extra={"event_type": event_type, "severity": severity_score},
    )

    steps = _MITIGATION_CATALOGUE.get(event_type, [
        {"step": 1, "action": "Assess situation and notify Shift Manager.", "timeframe": "Immediate", "responsible": "Shift Manager"},
        {"step": 2, "action": "Document event and monitor for changes.", "timeframe": "Ongoing", "responsible": "System Operator"},
    ])

    # For CRITICAL events, add a mandatory immediate escalation step
    if severity_score >= 5:
        steps = [
            {
                "step": 0,
                "action": "🚨 IMMEDIATE ESCALATION — Notify VP Operations and ISO/RTO duty officer NOW.",
                "timeframe": "Immediate",
                "responsible": "Shift Manager",
            }
        ] + steps

    plan: dict[str, Any] = {
        "plan_id": f"PLAN-{uuid.uuid4().hex[:8].upper()}",
        "event_type": event_type,
        "region": region,
        "severity_score": severity_score,
        "severity_label": severity_label,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "advisory_header": _URGENCY_HEADERS.get(severity_label, "Follow standard procedures."),
        "steps": steps,
        "step_count": len(steps),
        "affected_assets": affected_assets,
        "source": "DETERMINISTIC_RUNBOOK_ENGINE",
    }

    log.info(
        "generate_mitigation_steps completed",
        extra={"plan_id": plan["plan_id"], "step_count": plan["step_count"]},
    )
    return plan
