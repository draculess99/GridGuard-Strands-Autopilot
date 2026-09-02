"""
Tool: retrieve_runbook

Looks up the relevant operational runbook for a given event type.
"""

from __future__ import annotations

from typing import Annotated, Any

from strands import tool

from gridguard.data.runbooks import get_runbook
from gridguard.logger import get_logger

log = get_logger(__name__)


@tool
def retrieve_runbook(
    event_type: Annotated[
        str,
        "The grid-risk event type. One of: SEVERE_WEATHER, HIGH_DEMAND, EQUIPMENT_RISK, OUTAGE_WARNING.",
    ],
) -> dict[str, Any]:
    """
    Retrieve the standard operational runbook for the specified event type.

    The runbook contains pre-conditions, ordered response steps, responsible
    roles, timeframes, and escalation criteria. All runbooks are SYNTHETIC
    examples and do not represent real utility operating procedures.
    """
    log.info("retrieve_runbook called", extra={"event_type": event_type})
    rb = get_runbook(event_type)
    log.info(
        "retrieve_runbook returned",
        extra={"runbook_id": rb.get("runbook_id"), "steps": len(rb.get("response_steps", []))},
    )
    return rb
