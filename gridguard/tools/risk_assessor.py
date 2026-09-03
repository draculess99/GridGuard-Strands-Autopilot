"""
Tool: assess_risk

Scores the severity and urgency of a grid-risk event from the snapshot
and event metadata. Uses a deterministic rule engine — no LLM needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from strands import tool

from gridguard.logger import get_logger

log = get_logger(__name__)

# ── Risk scoring constants ────────────────────────────────────────────────────

# Severity 1–5 (1 = informational, 5 = imminent grid emergency)
_RESERVE_THRESHOLDS = [
    (700, 5),
    (1_000, 4),
    (1_500, 3),
    (2_500, 2),
    (float("inf"), 1),
]

_URGENCY_MAP = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "INFORMATIONAL"}

_PRIORITY_MAP = {
    "CRITICAL": "P1",
    "HIGH": "P2",
    "MEDIUM": "P3",
    "LOW": "P4",
    "INFORMATIONAL": "P5",
}

_EVENT_BASE_SEVERITY: dict[str, int] = {
    "SEVERE_WEATHER": 3,
    "HIGH_DEMAND": 3,
    "EQUIPMENT_RISK": 2,
    "OUTAGE_WARNING": 2,
}


def _score_reserve(reserve_mw: float) -> int:
    for threshold, score in _RESERVE_THRESHOLDS:
        if reserve_mw < threshold:
            return score
    return 1


def _combine_severity(event_base: int, reserve_score: int, hint: int) -> int:
    """Combine event type, reserve, and hint into a final 1-5 score."""
    raw = round((event_base + reserve_score + hint) / 3)
    return max(1, min(5, raw))


@tool
def assess_risk(
    event_type: Annotated[str, "The grid-risk event type (e.g. SEVERE_WEATHER)."],
    region: Annotated[str, "Grid region identifier."],
    demand_mw: Annotated[float, "Current demand in megawatts."],
    capacity_mw: Annotated[float, "Available capacity in megawatts."],
    contingency_reserve_mw: Annotated[float, "Current contingency reserve in megawatts."],
    severity_hint: Annotated[int, "Operator or event-metadata severity hint (1–5)."] = 3,
    affected_assets: Annotated[list[str], "List of affected asset IDs."] = [],
    forecast_peak_mw: Annotated[float | None, "XGBoost forecasted peak demand in megawatts."] = None,
    forecast_reserve_margin_pct: Annotated[float | None, "XGBoost forecasted peak reserve margin percentage."] = None,
    high_risk_hours: Annotated[int, "Number of hours where forecasted demand exceeds 92% capacity."] = 0,
) -> dict[str, Any]:
    """
    Assess and score the operational risk level for a grid event.

    Combines current grid snapshot, event type, operator hints, and the XGBoost
    demand forecast into a structured risk assessment with severity score (1–5),
    urgency label, priority tier, and explicit forecast impact explanation.
    Uses a deterministic rule engine — reproducible without LLM calls.
    """
    log.info("assess_risk called", extra={"event_type": event_type, "region": region})

    reserve_score = _score_reserve(contingency_reserve_mw)
    event_base = _EVENT_BASE_SEVERITY.get(event_type, 2)
    raw_severity = _combine_severity(event_base, reserve_score, severity_hint)
    severity = raw_severity

    # Evaluate XGBoost forecast impact on severity
    if forecast_reserve_margin_pct is not None:
        if forecast_reserve_margin_pct < 0 or high_risk_hours >= 4:
            severity = min(5, raw_severity + 1)
            forecast_impact = (
                f"CRITICAL FORECAST IMPACT: XGBoost projects negative reserve margin ({forecast_reserve_margin_pct}%) "
                f"with {high_risk_hours} hours exceeding 92% capacity. Severity escalated from {raw_severity} to {severity}."
            )
        elif forecast_reserve_margin_pct < 5 or high_risk_hours >= 2:
            severity = min(5, max(raw_severity, 4))
            forecast_impact = (
                f"ELEVATED FORECAST IMPACT: XGBoost projects thin reserve margin ({forecast_reserve_margin_pct}%) "
                f"with {high_risk_hours} peak hours near capacity. Severity set to {severity}."
            )
        elif forecast_reserve_margin_pct < 12 or high_risk_hours >= 1:
            forecast_impact = (
                f"WATCH FORECAST IMPACT: XGBoost projects {forecast_reserve_margin_pct}% reserve margin "
                f"with {high_risk_hours} peak hour near threshold."
            )
        else:
            forecast_impact = (
                f"NORMAL FORECAST IMPACT: XGBoost projects healthy reserve margin of {forecast_reserve_margin_pct}%. "
                "Current telemetry dominates severity."
            )
    else:
        forecast_impact = "No XGBoost forecast supplied; evaluated on snapshot telemetry only."

    urgency = _URGENCY_MAP[severity]
    priority = _PRIORITY_MAP[urgency]

    reserve_margin_pct = round((capacity_mw - demand_mw) / capacity_mw * 100, 1) if capacity_mw else 0.0
    load_factor_pct = round(demand_mw / capacity_mw * 100, 1) if capacity_mw else 0.0

    # Build plain-language risk summary
    summary_lines = [
        f"Event type: {event_type} in region {region}.",
        f"Current load factor: {load_factor_pct}% of available capacity.",
        f"Contingency reserve: {contingency_reserve_mw:,.0f} MW ({reserve_score}/5 reserve risk).",
        forecast_impact,
    ]
    if severity >= 4:
        summary_lines.append("⚠️ IMMEDIATE OPERATOR ATTENTION REQUIRED.")
    if affected_assets:
        summary_lines.append(f"Affected assets: {', '.join(affected_assets)}.")

    assessment: dict[str, Any] = {
        "event_type": event_type,
        "region": region,
        "assessed_at": datetime.now(tz=timezone.utc).isoformat(),
        "severity_score": severity,        # 1–5
        "severity_label": urgency,         # INFORMATIONAL … CRITICAL
        "priority_tier": priority,         # P1 … P5
        "reserve_margin_pct": reserve_margin_pct,
        "load_factor_pct": load_factor_pct,
        "contingency_reserve_mw": contingency_reserve_mw,
        "affected_assets": affected_assets,
        "forecast_peak_mw": forecast_peak_mw,
        "forecast_reserve_margin_pct": forecast_reserve_margin_pct,
        "forecast_high_risk_hours": high_risk_hours,
        "forecast_impact_explanation": forecast_impact,
        "requires_immediate_action": severity >= 4,
        "requires_human_approval": severity >= 2,  # any non-informational event
        "risk_summary": " ".join(summary_lines),
        "scoring_method": "DETERMINISTIC_RULES_v2_XGBOOST",
    }

    log.info(
        "assess_risk completed",
        extra={"severity": severity, "urgency": urgency, "priority": priority},
    )
    return assessment
