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
            "max_tokens": settings.LIVE_MAX_OUTPUT_TOKENS,
            "temperature": settings.LIVE_TEMPERATURE,
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
        else:
            model_kwargs["region_name"] = settings.AWS_REGION
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


# ── Bounded Live Operator Briefing (Amazon Bedrock via Strands) ───────────────

BRIEFING_SYSTEM_PROMPT = """
You are GridGuard Operations Autopilot, an expert grid operations advisory agent.
Your role is to produce a concise, professional, evidence-grounded Operator Briefing for the shift supervisor.

Safety Boundaries:
- You operate strictly on SYNTHETIC / SIMULATED demo data. Do not claim to monitor or control any real physical grid.
- All numbers, risk scores, and mitigation steps in the evidence are authoritative and computed deterministically. Do NOT alter, hallucinate, or recalculate them.
- All drafted actions are strictly recommendations. The plan is a DRAFT and requires explicit human operator review and sign-off before execution.

Format your briefing concisely using these exact sections:
1. INCIDENT SUMMARY: High-level situation assessment.
2. EVIDENCE & UNCERTAINTY: Telemetry data, XGBoost 24-hour peak demand/capacity constraint, and model uncertainty bounds.
3. OPERATIONAL RATIONALE: Why the proposed mitigation steps address this specific risk profile.
4. GOVERNANCE NOTICE: Explicit statement that this operational plan is DRAFT_PENDING_APPROVAL and requires human operator approval via the HITL gate.
""".strip()


def format_evidence_prompt(
    event: dict[str, Any],
    snapshot: dict[str, Any],
    forecast: dict[str, Any],
    assessment: dict[str, Any],
    runbook: dict[str, Any],
    plan: dict[str, Any],
) -> str:
    """Format structured evidence into a clear, bounded prompt for the live Bedrock agent."""
    steps_lines = [
        f"- Step {s.get('step')}: {s.get('action')} [Role: {s.get('responsible')}, Time: {s.get('timeframe')}]"
        for s in plan.get("steps", [])
    ]
    return f"""
EVIDENCE PACKAGE (Synthetic Grid Operations Telemetry):

[INCIDENT EVENT]
- Title: {event.get('title')}
- Event Type: {event.get('event_type')} (ID: {event.get('event_id')})
- Region: {event.get('region')}
- Description: {event.get('description')}
- Affected Assets: {', '.join(event.get('affected_assets', []))}

[REGIONAL TELEMETRY SNAPSHOT]
- Current Demand: {snapshot.get('demand_mw'):,.0f} MW
- Available Capacity: {snapshot.get('available_capacity_mw'):,.0f} MW
- Contingency Reserve: {snapshot.get('contingency_reserve_mw'):,.0f} MW
- Frequency: {snapshot.get('frequency_hz')} Hz
- Alert Level: {snapshot.get('alert_level')}

[XGBOOST 24-HOUR DEMAND & RESERVE FORECAST]
- Forecast Peak Demand: {forecast.get('predicted_peak_mw'):,.1f} MW
- Available Generation Capacity: {forecast.get('available_capacity_mw'):,.1f} MW
- Projected Reserve Margin: {forecast.get('reserve_margin_pct')}% ({forecast.get('reserve_margin_mw'):,.1f} MW)
- High-Risk Hours (>=92% utilization): {forecast.get('high_risk_hours')}
- Forecast Risk Category: {forecast.get('forecast_risk_level')}
- Headline: {forecast.get('headline')}

[DETERMINISTIC RISK ASSESSMENT]
- Severity Score: {assessment.get('severity_score')}/5 ({assessment.get('severity_label')})
- Priority Tier: {assessment.get('priority_tier')}
- Forecast Impact: {assessment.get('forecast_impact_explanation')}
- Risk Summary: {assessment.get('risk_summary')}

[OPERATING RUNBOOK]
- ID: {runbook.get('runbook_id')} — {runbook.get('title')}

[PROPOSED MITIGATION PLAN ({plan.get('step_count')} Steps)]
{chr(10).join(steps_lines)}

INSTRUCTION:
Generate a concise Operator Briefing (maximum 300-400 words) based strictly on this evidence package.
Include the 4 required sections: Incident Summary, Evidence & Uncertainty, Operational Rationale, and Governance Notice.
""".strip()


def generate_live_briefing(
    event: dict[str, Any],
    snapshot: dict[str, Any],
    forecast: dict[str, Any],
    assessment: dict[str, Any],
    runbook: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate an evidence-grounded Operator Briefing using a real Strands Agent
    backed by Amazon Bedrock.

    Guarantees:
    - Bounded single invocation (turns=1, output_tokens=LIVE_MAX_OUTPUT_TOKENS, max_attempts=1, no retries, no loops).
    - Receives only structured telemetry and deterministic tool evidence.
    - Process-level run count ceiling enforced via increment_and_check_live_run_limit().
    """
    from gridguard.safeguards import (
        increment_and_check_live_run_limit,
        LiveModeCredentialsError,
        LiveModeModelAccessError,
        redact_secrets,
    )

    # 1. Enforce process-level live-run ceiling
    increment_and_check_live_run_limit()

    try:
        from strands import Agent, ModelRetryStrategy
        from strands.models.bedrock import BedrockModel
        from strands.types.agent import Limits
    except ImportError as exc:
        raise ImportError("strands-agents must be installed for live mode.") from exc

    import boto3
    import botocore.exceptions

    boto_session = None
    if settings.AWS_ACCESS_KEY_ID:
        boto_session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            aws_session_token=settings.AWS_SESSION_TOKEN or None,
            region_name=settings.AWS_REGION,
        )

    model_kwargs: dict[str, Any] = {
        "model_id": settings.BEDROCK_MODEL_ID,
        "max_tokens": settings.LIVE_MAX_OUTPUT_TOKENS,
        "temperature": settings.LIVE_TEMPERATURE,
    }
    if boto_session:
        model_kwargs["boto_session"] = boto_session
    else:
        model_kwargs["region_name"] = settings.AWS_REGION

    def attempt_briefing(model_id: str) -> dict[str, Any]:
        mk = dict(model_kwargs)
        mk["model_id"] = model_id
        bedrock_model = BedrockModel(**mk)
        briefing_agent = Agent(
            model=bedrock_model,
            system_prompt=BRIEFING_SYSTEM_PROMPT,
            retry_strategy=ModelRetryStrategy(max_attempts=1),  # strictly no retries
        )

        evidence_prompt = format_evidence_prompt(
            event=event,
            snapshot=snapshot,
            forecast=forecast,
            assessment=assessment,
            runbook=runbook,
            plan=plan,
        )

        agent_result = briefing_agent(
            evidence_prompt,
            limits=Limits(turns=1, output_tokens=settings.LIVE_MAX_OUTPUT_TOKENS),
        )

        briefing_text = str(agent_result).strip()

        return {
            "source": "AMAZON_BEDROCK",
            "model_id": model_id,
            "region": settings.AWS_REGION,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "briefing_text": briefing_text,
            "label": "Bedrock-generated operator briefing — synthetic demo only.",
            "status": "SUCCESS",
        }

    try:
        try:
            return attempt_briefing(settings.BEDROCK_MODEL_ID)
        except Exception as exc:
            if getattr(settings, "BEDROCK_FALLBACK_MODEL_ID", None) and settings.BEDROCK_MODEL_ID != settings.BEDROCK_FALLBACK_MODEL_ID:
                log.warning(f"Primary model {settings.BEDROCK_MODEL_ID} failed: {exc}. Trying fallback model {settings.BEDROCK_FALLBACK_MODEL_ID}.")
                return attempt_briefing(settings.BEDROCK_FALLBACK_MODEL_ID)
            raise


    except botocore.exceptions.NoCredentialsError as exc:
        log.error("AWS credentials not found for live Bedrock mode")
        raise LiveModeCredentialsError(
            "AWS credentials not found. Configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY "
            "or AWS_PROFILE in .env before running live mode."
        ) from exc

    except botocore.exceptions.ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        msg = exc.response.get("Error", {}).get("Message", str(exc))
        log.error("Bedrock client error", extra={"code": code, "error_msg": redact_secrets(msg)})
        if code in ("AccessDeniedException", "ValidationException", "ResourceNotFoundException"):
            raise LiveModeModelAccessError(
                f"Bedrock access error ({code}): {msg}. "
                f"Ensure model access is enabled for {settings.BEDROCK_MODEL_ID} in {settings.AWS_REGION} "
                "in the AWS Bedrock Console."
            ) from exc
        raise


# ── Groq Briefing (optional live demo via Strands OpenAIModel) ────────────────

GROQ_BRIEFING_SYSTEM_PROMPT = """
You are GridGuard Operations Autopilot.
Generate ONE concise final operator briefing of NO MORE THAN 150 words based strictly on the evidence.

Include exactly:
1. Current risk.
2. Recommended mitigation.
3. The required human approval (state explicitly that this is DRAFT_PENDING_APPROVAL and requires sign-off).

Do not ask for chain-of-thought, tool use, internal reasoning, a long report, or follow-up questions.
Operate strictly on the synthetic demo data. Do not alter numbers or risk scores.
""".strip()

def generate_groq_briefing(
    event: dict[str, Any],
    snapshot: dict[str, Any],
    forecast: dict[str, Any],
    assessment: dict[str, Any],
    runbook: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate an evidence-grounded Operator Briefing using Groq via Strands OpenAIModel.

    All conditions must be satisfied before any API call is made:
      - MOCK_MODE=false
      - LIVE_LLM_ENABLED=true
      - STRANDS_PROVIDER=groq
      - GROQ_API_KEY non-empty

    This is a bounded single invocation (turns=1). It does not control any real grid.
    Groq is not Bedrock, AgentCore, or an AWS-hosted model.
    """
    from gridguard.safeguards import (
        increment_and_check_live_run_limit,
        validate_groq_live_gate,
    )

    # 1. Enforce gate (raises RuntimeError with safe message if blocked)
    validate_groq_live_gate()

    # 2. Enforce process-level live-run ceiling
    increment_and_check_live_run_limit()

    try:
        from strands import Agent, ModelRetryStrategy
        from strands.models.openai import OpenAIModel
        from strands.types.agent import Limits
    except ImportError as exc:
        raise ImportError("strands-agents must be installed for Groq live mode.") from exc

    groq_model = OpenAIModel(
        client_args={
            "api_key": settings.GROQ_API_KEY,
            "base_url": "https://api.groq.com/openai/v1",
        },
        model_id=settings.GROQ_MODEL_ID,
        params={
            "max_tokens": settings.LIVE_MAX_OUTPUT_TOKENS,
            "reasoning_effort": "low",
        },
    )

    briefing_agent = Agent(
        model=groq_model,
        system_prompt=GROQ_BRIEFING_SYSTEM_PROMPT,
        retry_strategy=ModelRetryStrategy(max_attempts=1),
    )

    evidence_prompt = format_evidence_prompt(
        event=event,
        snapshot=snapshot,
        forecast=forecast,
        assessment=assessment,
        runbook=runbook,
        plan=plan,
    )

    agent_result = briefing_agent(
        evidence_prompt,
        limits=Limits(turns=1, output_tokens=settings.LIVE_MAX_OUTPUT_TOKENS),
    )

    briefing_text = str(agent_result).strip()

    return {
        "source": "GROQ",
        "model_id": settings.GROQ_MODEL_ID,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "briefing_text": briefing_text,
        "label": (
            "Groq-generated operator briefing — optional live demo only. "
            "Not Bedrock, not AgentCore. Does not control a real electrical grid."
        ),
        "status": "SUCCESS",
    }


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


def run_workflow(
    event_type: str = "SEVERE_WEATHER",
    *,
    on_step: Any = None,
    mock_mode: bool | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Execute the full GridGuard operations workflow.

    Parameters
    ----------
    event_type:
        One of: SEVERE_WEATHER, HIGH_DEMAND, EQUIPMENT_RISK, OUTAGE_WARNING.
    on_step:
        Optional callback(step: WorkflowStep) called after each step completes.
    mock_mode:
        If True (or None when settings.MOCK_MODE=True): runs purely deterministically with zero cloud calls.
        If False: runs deterministic tools and calls Amazon Bedrock once via Strands
        to produce an Operator Briefing.

    Returns
    -------
    dict with keys: event, steps, snapshot, forecast, runbook, assessment, plan,
    operator_briefing, work_order, approval_request, audit_records, overall_status, mock_mode.
    """
    if mock_mode is None:
        mock_mode = settings.MOCK_MODE

    log.info("run_workflow started", extra={"event_type": event_type, "mock_mode": mock_mode})

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

    # ── Step 5b: Live Operator Briefing (Groq or Amazon Bedrock via Strands) ─────
    operator_briefing = None
    if not mock_mode:
        try:
            if settings.is_groq():
                operator_briefing = generate_groq_briefing(
                    event=event,
                    snapshot=snapshot,
                    forecast=forecast,
                    assessment=assessment,
                    runbook=runbook,
                    plan=plan,
                )
            else:
                operator_briefing = generate_live_briefing(
                    event=event,
                    snapshot=snapshot,
                    forecast=forecast,
                    assessment=assessment,
                    runbook=runbook,
                    plan=plan,
                )
        except Exception as exc:
            log.error("Live briefing failed; continuing deterministic governance", extra={"error": str(exc)})
            model_id = settings.GROQ_MODEL_ID if settings.is_groq() else settings.BEDROCK_MODEL_ID
            source = "GROQ" if settings.is_groq() else "AMAZON_BEDROCK"
            provider_name = "Groq" if settings.is_groq() else "Bedrock"
            operator_briefing = {
                "source": source,
                "model_id": model_id,
                "region": settings.AWS_REGION if not settings.is_groq() else None,
                "generated_at": datetime.now(tz=timezone.utc).isoformat(),
                "briefing_text": f"Live {provider_name} briefing unavailable: {str(exc)}",
                "label": f"{provider_name} briefing failed — fallback to deterministic runbook.",
                "status": "FAILED",
                "error": str(exc),
            }

    # ── Step 6: Draft Work Order ──────────────────────────────────────────────
    wo_notes = f"Auto-drafted by GridGuard Autopilot. Severity score: {assessment['severity_score']}/5."
    if operator_briefing and operator_briefing.get("status") == "SUCCESS":
        wo_notes += " Includes Bedrock-generated Operator Briefing."

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
        notes=wo_notes,
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
    audit_details: dict[str, Any] = {
        "severity_score": assessment["severity_score"],
        "priority_tier": assessment["priority_tier"],
        "plan_id": plan["plan_id"],
        "approval_token": approval_request["approval_token"],
        "mock_mode": mock_mode,
    }
    if operator_briefing:
        audit_details["briefing_status"] = operator_briefing.get("status", "UNKNOWN")
        audit_details["briefing_source"] = operator_briefing.get("source", "UNKNOWN")

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
        details=audit_details,
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
        "operator_briefing": operator_briefing,
        "work_order": work_order,
        "approval_request": approval_request,
        "audit_records": audit_records,
        "overall_status": "AWAITING_HUMAN_APPROVAL",
        "mock_mode": mock_mode,
        "completed_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    log.info(
        "run_workflow completed",
        extra={
            "event_id": event_id,
            "wo": work_order["work_order_number"],
            "token": approval_request["approval_token"],
            "mock_mode": mock_mode,
        },
    )
    return result


def run_mock_workflow(
    event_type: str = "SEVERE_WEATHER",
    *,
    on_step: Any = None,
) -> dict[str, Any]:
    """
    Execute the full GridGuard mock workflow deterministically (zero cloud tokens).
    Preserves backwards compatibility for all existing tests and callers.
    """
    return run_workflow(event_type=event_type, on_step=on_step, mock_mode=True)


def run_live_workflow(
    event_type: str = "SEVERE_WEATHER",
    *,
    on_step: Any = None,
) -> dict[str, Any]:
    """
    Execute the GridGuard live workflow with Amazon Bedrock operator briefing.
    """
    return run_workflow(event_type=event_type, on_step=on_step, mock_mode=False)
