# gridguard/tools/__init__.py
"""
Strands tool functions for the GridGuard Operations Autopilot agent.

Each function is decorated with @tool so Strands can use it autonomously.
Import all tools from here to keep the agent definition clean.
"""

from gridguard.tools.grid_snapshot import get_grid_snapshot
from gridguard.tools.runbook import retrieve_runbook
from gridguard.tools.risk_assessor import assess_risk
from gridguard.tools.mitigation import generate_mitigation_steps
from gridguard.tools.work_order import draft_work_order
from gridguard.tools.human_approval import request_human_approval
from gridguard.tools.audit import record_audit_event

__all__ = [
    "get_grid_snapshot",
    "retrieve_runbook",
    "assess_risk",
    "generate_mitigation_steps",
    "draft_work_order",
    "request_human_approval",
    "record_audit_event",
]
