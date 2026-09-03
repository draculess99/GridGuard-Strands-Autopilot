"""
GridGuard Operations Autopilot — Strands Agent Definition

This module defines the agent and a mock workflow runner that executes
the full end-to-end pipeline without consuming any cloud tokens.

Architecture
------------
In MOCK_MODE (default):
    run_mock_workflow() calls each tool function directly in the correct
    order, returning a structured WorkflowResult. No LLM or API calls.

In live mode (MOCK_MODE=false):
    build_live_agent() constructs a Strands Agent with the tool registry
    and the system prompt. Invoke it with agent(event_prompt) to have the
    LLM orchestrate the tools autonomously.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from gridguard.config import settings
from gridguard.data.synthetic_events import build_event
from gridguard.logger import get_logger
from gridguard.tools import (
    assess_risk,
    draft_work_order,
    forecast_demand_xgboost,
    generate_mitigation_steps,
    get_grid_snapshot,
    record_audit_event,
    request_human_approval,
    retrieve_runbook,
)

log = get_logger(__name__)

# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are GridGuard Operations Autopilot, an autonomous agent that assists
grid and utility operations teams by triaging risk signals, checking
operational runbooks, generating mitigation recommendations, and preparing
work orders for human review.

Your workflow for every grid-risk event:
1. Call get_grid_snapshot to retrieve current grid telemetry and state.
2. Call forecast_demand_xgboost to run a 24-hour demand forecast and reserve margin projection.
3. Call retrieve_runbook to get the relevant operating procedure.
4. Call assess_risk to score severity, urgency, and priority using telemetry and the forecast.
5. Call generate_mitigation_steps to produce an ordered action plan.
6. Call draft_work_order to format a structured work order.
7. Call request_human_approval — MANDATORY before any action becomes active.
8. Call record_audit_event to log each significant step.

Critical constraints:
- You operate on SYNTHETIC / SIMULATED data only. You do NOT control any
  real electric grid, generation asset, or transmission infrastructure.
- You MUST call request_human_approval before any work order is considered
  actionable. Never skip this step.
- All drafted actions are recommendations. A human operator makes the
  final decision.
- Be concise and professional. Use plain language that operations staff
  can act on immediately.
""".strip()


# ── Live Agent (requires LLM provider) ───────────────────────────────────────

def build_live_agent():
    """
    Build and return a Strands Agent configured for the active provider.

    Requires MOCK_MODE=false and valid provider credentials.
    Raises ImportError if strands is not installed.
    Raises RuntimeError if no provider credentials are configured.
    """
    try:
        from strands import Agent
        from strands.models import BedrockModel, AnthropicModel  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "strands-agents must be installed. Run: pip install strands-agents strands-agents-tools"
        ) from exc

    if settings.is_bedrock():
        model_kwargs: dict[str, Any] = {
            "model_id": settings.BEDROCK_MODEL_ID,
            "region_name": settings.AWS_REGION,
        }
        if settings.AWS_ACCESS_KEY_ID:
            import boto3
            session = boto3.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                aws_session_token=settings.AWS_SESSION_TOKEN or None,
                region_name=settings.AWS_REGION,
            )
            model_kwargs["boto_session"] = session
        from strands.models import BedrockModel
        model = BedrockModel(**model_kwargs)

    elif settings.is_anthropic():
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY must be set when STRANDS_PROVIDER=anthropic")
        from strands.models import AnthropicModel
        model = AnthropicModel(
            client_args={"api_key": settings.ANTHROPIC_API_KEY},
            model_id=settings.ANTHROPIC_MODEL,
        )
    else:
        raise RuntimeError(f"Unknown STRANDS_PROVIDER: {settings.STRANDS_PROVIDER!r}")

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            get_grid_snapshot,
            forecast_demand_xgboost,
            retrieve_runbook,
            assess_risk,
            generate_mitigation_steps,
            draft_work_order,
            request_human_approval,
            record_audit_event,
        ],
    )
    log.info("Live agent built", extra={"provider": settings.STRANDS_PROVIDER})
    return agent


# ── Mock Workflow Engine ──────────────────────────────────────────────────────

class WorkflowStep:
    """Represents one step in the workflow timeline."""

    def __init__(self, name: str, tool_name: str):
        self.name = name
        self.tool_name = tool_name
        self.status: str = "PENDING"  # PENDING | RUNNING | DONE | ERROR
        self.started_at: str | None = None
        self.completed_at: str | None = None
        self.elapsed_ms: float | None = None
        self.result: dict[str, Any] | None = None
        self.error: str | None = None

    def start(self) -> None:
        self.status = "RUNNING"
        self.started_at = datetime.now(tz=timezone.utc).isoformat()
        self._t0 = time.perf_counter()

    def finish(self, result: dict[str, Any]) -> None:
        self.status = "DONE"
        self.result = result
        self.completed_at = datetime.now(tz=timezone.utc).isoformat()
        self.elapsed_ms = round((time.perf_counter() - self._t0) * 1000, 1)

    def fail(self, error: str) -> None:
        self.status = "ERROR"
        self.error = error
        self.completed_at = datetime.now(tz=timezone.utc).isoformat()
        self.elapsed_ms = round((time.perf_counter() - self._t0) * 1000, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tool_name": self.tool_name,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_ms": self.elapsed_ms,
            "result": self.result,
            "error": self.error,
        }


def run_mock_workflow(
    event_type: str,
    *,
    on_step: Any = None,
) -> dict[str, Any]:
    """
    Execute the full GridGuard workflow without any LLM calls.

    Parameters
    ----------
    event_type:
        One of: SEVERE_WEATHER, HIGH_DEMAND, EQUIPMENT_RISK, OUTAGE_WARNING.
    on_step:
        Optional callback(step: WorkflowStep) called after each step completes.
        Used by the dashboard to push live updates.

    Returns
    -------
    dict with keys: event, steps, snapshot, runbook, assessment, plan,
    work_order, approval_request, audit_records, overall_status.
    """
    log.info("run_mock_workflow started", extra={"event_type": event_type})

    # Build a canonical event
    event = build_event(event_type, randomise=True)
    event_id = event["event_id"]
    region = event["region"]

    steps: list[WorkflowStep] = []
    audit_records: list[dict] = []

    def _unwrap(fn):
        """
        Return the underlying callable, handling Strands @tool wrapper objects.
        Strands may wrap decorated functions in a ToolUse or similar object.
        We try common attribute names and fall back to calling fn directly.
        """
        for attr in ("func", "__wrapped__", "_func"):
            if hasattr(fn, attr):
                return getattr(fn, attr)
        return fn

    def _run_step(step: WorkflowStep, fn, **kwargs) -> dict[str, Any]:
        step.start()
        steps.append(step)
        try:
            # Unwrap and call the underlying Python function for mock mode
            result = _unwrap(fn)(**kwargs)
            step.finish(result)
            if on_step:
                on_step(step)
            return result
        except Exception as exc:
            step.fail(str(exc))
            if on_step:
                on_step(step)
            log.error("Step failed", extra={"step": step.name, "error": str(exc)})
            raise

    # ── Step 1: Grid Snapshot ─────────────────────────────────────────────────
    snapshot = _run_step(
        WorkflowStep("Grid Snapshot", "get_grid_snapshot"),
        get_grid_snapshot,
        region=region,
        event_type=event_type,
    )

    # ── Step 2: Demand Forecast (XGBoost) ─────────────────────────────────────
    weather_info = event.get("weather", {})
    temp_delta = float(event.get("temperature_delta_f", weather_info.get("temperature_delta_f", 0.0)))
    demand_shock = float(event.get("demand_shock_pct", weather_info.get("demand_shock_pct", 0.0)))

    if not temp_delta and not demand_shock:
        if event_type == "SEVERE_WEATHER":
            temp_delta = -36.0
            demand_shock = 14.0
        elif event_type == "HIGH_DEMAND":
            temp_delta = 14.0
            demand_shock = 10.0
        elif event_type == "EQUIPMENT_RISK":
            demand_shock = 0.0
        elif event_type == "OUTAGE_WARNING":
            demand_shock = 0.0

    forecast = _run_step(
        WorkflowStep("Demand Forecast", "forecast_demand_xgboost"),
        forecast_demand_xgboost,
        region=region,
        available_capacity_mw=float(snapshot["available_capacity_mw"]),
        horizon_hours=24,
        temperature_delta_f=temp_delta,
        demand_shock_pct=demand_shock,
    )

    # ── Step 3: Retrieve Runbook ──────────────────────────────────────────────
    runbook = _run_step(
        WorkflowStep("Retrieve Runbook", "retrieve_runbook"),
        retrieve_runbook,
        event_type=event_type,
    )

    # ── Step 4: Assess Risk ───────────────────────────────────────────────────
    assessment = _run_step(
        WorkflowStep("Risk Assessment", "assess_risk"),
        assess_risk,
        event_type=event_type,
        region=region,
        demand_mw=float(event.get("demand_mw", snapshot["demand_mw"])),
        capacity_mw=float(event.get("capacity_mw", snapshot["available_capacity_mw"])),
        contingency_reserve_mw=float(event.get("contingency_reserve_mw", snapshot["contingency_reserve_mw"])),
        severity_hint=int(event.get("severity_hint", 3)),
        affected_assets=event.get("affected_assets", []),
        forecast_peak_mw=float(forecast["predicted_peak_mw"]),
        forecast_reserve_margin_pct=float(forecast["reserve_margin_pct"]),
        high_risk_hours=int(forecast["high_risk_hours"]),
    )

    # ── Step 5: Generate Mitigation ───────────────────────────────────────────
    plan = _run_step(
        WorkflowStep("Mitigation Plan", "generate_mitigation_steps"),
        generate_mitigation_steps,
        event_type=event_type,
        severity_label=assessment["severity_label"],
        severity_score=int(assessment["severity_score"]),
        region=region,
        affected_assets=event.get("affected_assets", []),
    )

    # ── Step 6: Draft Work Order ──────────────────────────────────────────────
    work_order = _run_step(
        WorkflowStep("Draft Work Order", "draft_work_order"),
        draft_work_order,
        event_type=event_type,
        event_id=event_id,
        region=region,
        priority_tier=assessment["priority_tier"],
        severity_label=assessment["severity_label"],
        plan_id=plan["plan_id"],
        mitigation_steps=plan["steps"],
        affected_assets=event.get("affected_assets", []),
        notes=f"Auto-drafted by GridGuard Autopilot. Severity score: {assessment['severity_score']}/5.",
    )

    # ── Step 7: Request Human Approval ────────────────────────────────────────
    approval_request = _run_step(
        WorkflowStep("Human Approval Gate", "request_human_approval"),
        request_human_approval,
        work_order_number=work_order["work_order_number"],
        event_type=event_type,
        region=region,
        severity_label=assessment["severity_label"],
        priority_tier=assessment["priority_tier"],
        summary=(
            f"{event['title']}. "
            f"Risk: {assessment['severity_label']} (score {assessment['severity_score']}/5). "
            f"Reserve: {assessment['contingency_reserve_mw']:,.0f} MW. "
            f"Proposed: {plan['step_count']} mitigation steps. "
            f"Work order {work_order['work_order_number']} requires your approval."
        ),
    )

    # ── Step 8: Audit — Workflow Initiated ────────────────────────────────────
    audit_rec = _run_step(
        WorkflowStep("Audit Record", "record_audit_event"),
        record_audit_event,
        action="WORKFLOW_COMPLETED",
        actor="AGENT",
        event_type=event_type,
        event_id=event_id,
        work_order_number=work_order["work_order_number"],
        outcome=(
            f"Full workflow completed. WO {work_order['work_order_number']} drafted. "
            f"Approval token {approval_request['approval_token']} is PENDING."
        ),
        details={
            "severity_score": assessment["severity_score"],
            "priority_tier": assessment["priority_tier"],
            "plan_id": plan["plan_id"],
            "approval_token": approval_request["approval_token"],
        },
    )
    audit_records.append(audit_rec)

    result = {
        "event": event,
        "steps": [s.to_dict() for s in steps],
        "snapshot": snapshot,
        "forecast": forecast,
        "runbook": runbook,
        "assessment": assessment,
        "plan": plan,
        "work_order": work_order,
        "approval_request": approval_request,
        "audit_records": audit_records,
        "overall_status": "AWAITING_HUMAN_APPROVAL",
        "completed_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    log.info(
        "run_mock_workflow completed",
        extra={
            "event_id": event_id,
            "wo": work_order["work_order_number"],
            "token": approval_request["approval_token"],
        },
    )
    return result
