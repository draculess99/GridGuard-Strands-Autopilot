"""
Static operational runbook store.

Runbooks are representative industry-style procedures, written here as
synthetic examples only. They are NOT real utility operating procedures.
"""

from __future__ import annotations

from typing import Any

# Each runbook is keyed by event type and contains structured response guidance.
_RUNBOOKS: dict[str, dict[str, Any]] = {
    "SEVERE_WEATHER": {
        "runbook_id": "RB-SW-001",
        "title": "Severe Weather — Grid Preparation and Storm Response",
        "version": "3.2",
        "scope": "All events where NWS issues a Warning or Watch affecting the service territory.",
        "pre_conditions": [
            "Weather Advisory, Watch, or Warning has been issued by NWS.",
            "Meteorology team has confirmed storm path and timing.",
            "Operations Centre is staffed at Storm Level (minimum 3 dispatchers).",
        ],
        "response_steps": [
            {
                "step": 1,
                "action": "Activate Storm Watch Protocol",
                "detail": (
                    "Notify Shift Manager and escalate to Storm Level staffing. "
                    "Open Storm Bridge phone line. Log activation time in SCADA event log."
                ),
                "responsible": "Shift Manager",
                "timeframe": "Immediate",
            },
            {
                "step": 2,
                "action": "Assess Reserve Margin",
                "detail": (
                    "Review current contingency reserve. If reserve < 1,500 MW, "
                    "initiate emergency capacity procurement from neighbouring BAs."
                ),
                "responsible": "System Operator",
                "timeframe": "< 30 min",
            },
            {
                "step": 3,
                "action": "Defer non-critical maintenance outages",
                "detail": (
                    "Coordinate with Outage Management to reschedule any planned "
                    "outages on transmission assets in the storm path."
                ),
                "responsible": "Outage Coordinator",
                "timeframe": "< 1 hour",
            },
            {
                "step": 4,
                "action": "Pre-position field restoration crews",
                "detail": (
                    "Alert and stage Distribution line crews at strategic depots. "
                    "Confirm mutual aid agreements with neighbouring utilities."
                ),
                "responsible": "Field Operations Manager",
                "timeframe": "T-12 hours",
            },
            {
                "step": 5,
                "action": "Issue public load-reduction advisory",
                "detail": (
                    "Coordinate with Customer Operations to send Demand Response "
                    "notifications to enrolled participants. "
                    "Post advisory on utility website and social channels."
                ),
                "responsible": "Customer Operations",
                "timeframe": "T-6 hours",
            },
            {
                "step": 6,
                "action": "Monitor and update every 2 hours",
                "detail": (
                    "Operations Centre issues a 2-hourly situation report to all "
                    "stakeholders. Update storm track and revise actions as needed."
                ),
                "responsible": "Operations Centre",
                "timeframe": "Ongoing",
            },
        ],
        "escalation_criteria": [
            "Reserve margin falls below 700 MW.",
            "Storm path shifts to affect additional sub-stations not in original forecast.",
            "Any transmission element trips unexpectedly.",
        ],
        "source": "SYNTHETIC_RUNBOOK",
    },
    "HIGH_DEMAND": {
        "runbook_id": "RB-HD-001",
        "title": "High-Demand Emergency — Reserve Deficiency Response",
        "version": "2.7",
        "scope": "Events where load exceeds 95 % of installed capacity or contingency reserve < 1,000 MW.",
        "pre_conditions": [
            "Demand forecast or real-time telemetry confirms reserve deficiency.",
            "Heat advisory or other demand-driving condition is confirmed active.",
        ],
        "response_steps": [
            {
                "step": 1,
                "action": "Verify telemetry accuracy",
                "detail": (
                    "Confirm SCADA readings against back-up metering. "
                    "Rule out telemetry faults before activating emergency measures."
                ),
                "responsible": "System Operator",
                "timeframe": "Immediate",
            },
            {
                "step": 2,
                "action": "Activate Demand Response curtailment",
                "detail": (
                    "Issue automated curtailment signals to all interruptible "
                    "industrial and large-commercial DR participants (Tier 1)."
                ),
                "responsible": "DR Coordinator",
                "timeframe": "< 15 min",
            },
            {
                "step": 3,
                "action": "Procure emergency capacity",
                "detail": (
                    "Contact neighbouring BA operators for emergency energy purchases. "
                    "Activate spinning reserve call-up for any uncommitted peakers."
                ),
                "responsible": "System Operator",
                "timeframe": "< 30 min",
            },
            {
                "step": 4,
                "action": "Prepare rotating outage plan",
                "detail": (
                    "If reserve does not improve within 30 minutes, pre-stage "
                    "rotating distribution outage blocks per approved load-shed plan. "
                    "Do NOT execute without explicit Shift Manager authorisation."
                ),
                "responsible": "Shift Manager",
                "timeframe": "Conditional",
            },
            {
                "step": 5,
                "action": "Notify ISO / RTO",
                "detail": (
                    "Report event to Regional Transmission Organisation "
                    "per tariff requirements. Log call time and reference number."
                ),
                "responsible": "Shift Manager",
                "timeframe": "< 30 min",
            },
        ],
        "escalation_criteria": [
            "Reserve falls below 500 MW.",
            "Demand Response activation does not reduce load within 15 minutes.",
            "Any generation unit trips during the high-demand period.",
        ],
        "source": "SYNTHETIC_RUNBOOK",
    },
    "EQUIPMENT_RISK": {
        "runbook_id": "RB-EQ-001",
        "title": "Equipment Health Alert — High-Value Asset Monitoring",
        "version": "1.9",
        "scope": "Any transmission or substation asset with Health Index < 0.65 or DGA exceedance.",
        "pre_conditions": [
            "DGA or Health Index alert has been received from asset management system.",
            "Asset is currently energised and serving load.",
        ],
        "response_steps": [
            {
                "step": 1,
                "action": "Confirm and validate alert",
                "detail": (
                    "Cross-reference DGA result with previous samples. "
                    "Consult substation technician for on-site visual inspection."
                ),
                "responsible": "Asset Engineer",
                "timeframe": "< 4 hours",
            },
            {
                "step": 2,
                "action": "Assess N-1 impact",
                "detail": (
                    "Run contingency analysis: determine load served by affected "
                    "asset and identify backup switching paths."
                ),
                "responsible": "System Operator",
                "timeframe": "< 2 hours",
            },
            {
                "step": 3,
                "action": "Schedule accelerated inspection",
                "detail": (
                    "Create high-priority work order for dissolved-gas oil sampling, "
                    "thermal imaging, and bushing PF test within 72 hours."
                ),
                "responsible": "Maintenance Planning",
                "timeframe": "< 8 hours",
            },
            {
                "step": 4,
                "action": "Evaluate early de-energisation",
                "detail": (
                    "If Health Index < 0.50 or acetylene > 100 ppm, prepare "
                    "switching order to transfer load and take unit out of service. "
                    "Requires Shift Manager approval."
                ),
                "responsible": "Shift Manager",
                "timeframe": "Conditional",
            },
        ],
        "escalation_criteria": [
            "Health Index drops below 0.50.",
            "Acetylene exceeds 100 ppm.",
            "Unusual audible or visual signs from the unit (arcing, discolouration).",
        ],
        "source": "SYNTHETIC_RUNBOOK",
    },
    "OUTAGE_WARNING": {
        "runbook_id": "RB-OW-001",
        "title": "Maintenance Conflict — N-1 Policy Compliance Review",
        "version": "2.1",
        "scope": "Scheduled outage requests that, when combined, violate N-1 contingency policy.",
        "pre_conditions": [
            "Outage Management System (OMS) or manual review has flagged a conflict.",
            "At least two planned outages overlap on the same radial or contingency path.",
        ],
        "response_steps": [
            {
                "step": 1,
                "action": "Hold all conflicting outage tickets",
                "detail": (
                    "Place a HOLD flag on each conflicting OMS ticket. "
                    "Notify field crews and planners immediately."
                ),
                "responsible": "Outage Coordinator",
                "timeframe": "Immediate",
            },
            {
                "step": 2,
                "action": "Run N-1 power-flow study",
                "detail": (
                    "Perform a contingency study for all permutations of the "
                    "conflicting outages. Identify which combination is least risky."
                ),
                "responsible": "Planning Engineer",
                "timeframe": "< 2 hours",
            },
            {
                "step": 3,
                "action": "Reschedule lower-priority outage",
                "detail": (
                    "Negotiate with the lower-priority crew to reschedule work. "
                    "Update OMS and notify all affected parties."
                ),
                "responsible": "Outage Coordinator",
                "timeframe": "< 4 hours",
            },
            {
                "step": 4,
                "action": "Document conflict and resolution",
                "detail": (
                    "Write conflict report in OMS with root cause and corrective "
                    "action. Flag for process improvement review."
                ),
                "responsible": "Shift Manager",
                "timeframe": "< 24 hours",
            },
        ],
        "escalation_criteria": [
            "Field crew has already begun work on a held outage.",
            "N-1 study shows cascading risk beyond the immediate area.",
            "Conflicting outages involve critical protection or communications equipment.",
        ],
        "source": "SYNTHETIC_RUNBOOK",
    },
}


def get_runbook(event_type: str) -> dict:
    """Return the runbook for *event_type*, or a generic fallback."""
    return _RUNBOOKS.get(
        event_type,
        {
            "runbook_id": "RB-GEN-001",
            "title": "General Operational Event Response",
            "response_steps": [
                {"step": 1, "action": "Assess situation", "detail": "Gather facts."},
                {"step": 2, "action": "Notify Shift Manager", "detail": "Escalate as needed."},
            ],
            "source": "SYNTHETIC_RUNBOOK",
        },
    )


def list_runbook_ids() -> list[str]:
    return list(_RUNBOOKS.keys())
