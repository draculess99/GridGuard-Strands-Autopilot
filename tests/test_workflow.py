"""
Integration tests for the full GridGuard mock workflow.
Verifies that run_mock_workflow() produces a valid, complete result
for all four scenario types — no LLM or cloud calls needed.
"""

from __future__ import annotations

import pytest


SCENARIOS = ["SEVERE_WEATHER", "HIGH_DEMAND", "EQUIPMENT_RISK", "OUTAGE_WARNING"]


class TestMockWorkflow:

    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_workflow_completes_for_all_scenarios(self, scenario):
        from gridguard.agent import run_mock_workflow
        result = run_mock_workflow(scenario)
        assert result["overall_status"] == "AWAITING_HUMAN_APPROVAL"
        assert "event" in result
        assert "assessment" in result
        assert "plan" in result
        assert "work_order" in result
        assert "approval_request" in result

    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_all_eight_steps_present(self, scenario):
        from gridguard.agent import run_mock_workflow
        result = run_mock_workflow(scenario)
        steps = result["steps"]
        assert len(steps) == 8
        tool_names = [s["tool_name"] for s in steps]
        assert "get_grid_snapshot" in tool_names
        assert "forecast_demand_xgboost" in tool_names
        assert "retrieve_runbook" in tool_names
        assert "assess_risk" in tool_names
        assert "generate_mitigation_steps" in tool_names
        assert "draft_work_order" in tool_names
        assert "request_human_approval" in tool_names
        assert "record_audit_event" in tool_names

    def test_xgboost_forecast_runs_second_and_risk_consumes_output(self):
        from gridguard.agent import run_mock_workflow
        result = run_mock_workflow("SEVERE_WEATHER")
        steps = result["steps"]
        assert steps[1]["tool_name"] == "forecast_demand_xgboost"
        assert steps[1]["status"] == "DONE"
        assert "forecast" in result
        forecast = result["forecast"]
        assert forecast["predicted_peak_mw"] > 0
        assert forecast["forecast_horizon_hours"] == 24
        # Verify risk assessment consumed forecast peak and reserve margin
        assessment = result["assessment"]
        assert assessment["forecast_peak_mw"] == forecast["predicted_peak_mw"]
        assert assessment["forecast_reserve_margin_pct"] == forecast["reserve_margin_pct"]
        assert "forecast_impact_explanation" in assessment
        assert len(assessment["forecast_impact_explanation"]) > 0

    def test_severe_weather_stress_condition_produces_critical_risk(self):
        from gridguard.agent import run_mock_workflow
        result = run_mock_workflow("SEVERE_WEATHER")
        fc = result["forecast"]
        assessment = result["assessment"]
        plan = result["plan"]

        # Constrained reserve margin from scenario inputs and XGBoost model output
        assert fc["predicted_peak_mw"] > 23000.0
        assert fc["available_capacity_mw"] <= 25000.0
        assert fc["reserve_margin_pct"] < 5.0
        assert fc["forecast_risk_level"] in ("CRITICAL", "ELEVATED")
        assert fc["high_risk_hours"] >= 4

        # Risk assessment reflects computed evidence
        assert assessment["severity_score"] >= 4
        assert assessment["severity_label"] in ("CRITICAL", "HIGH")
        assert assessment["priority_tier"] in ("P1", "P2")
        assert "CRITICAL FORECAST IMPACT" in assessment["forecast_impact_explanation"]

        # Mitigation plan contains required operational actions
        actions = " ".join(s["action"] for s in plan["steps"]).lower()
        assert "reserve" in actions or "procurement" in actions
        assert "crew" in actions or "restoration" in actions
        assert "inspect" in actions or "patrol" in actions
        assert "escalation" in actions or "notify" in actions

    def test_normal_scenario_produces_healthy_reserve_margin(self):
        from gridguard.agent import run_mock_workflow
        result = run_mock_workflow("OUTAGE_WARNING")
        fc = result["forecast"]
        assessment = result["assessment"]

        # Verifies healthy reserve behavior in a normal scenario
        assert fc["forecast_risk_level"] == "NORMAL"
        assert fc["reserve_margin_pct"] >= 15.0
        assert fc["high_risk_hours"] == 0
        assert assessment["severity_score"] <= 3
        assert assessment["severity_label"] in ("LOW", "MEDIUM", "INFORMATIONAL")

    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_all_steps_complete_without_error(self, scenario):
        from gridguard.agent import run_mock_workflow
        result = run_mock_workflow(scenario)
        for step in result["steps"]:
            assert step["status"] == "DONE", (
                f"Step {step['name']} has status {step['status']}: {step.get('error')}"
            )

    def test_approval_token_is_pending(self):
        from gridguard.agent import run_mock_workflow
        from gridguard.tools.human_approval import get_pending_approval
        result = run_mock_workflow("SEVERE_WEATHER")
        token = result["approval_request"]["approval_token"]
        assert token.startswith("APPR-")
        stored = get_pending_approval(token)
        assert stored is not None
        assert stored["status"] == "PENDING"

    def test_work_order_is_draft_status(self):
        from gridguard.agent import run_mock_workflow
        result = run_mock_workflow("HIGH_DEMAND")
        assert result["work_order"]["status"] == "DRAFT_PENDING_APPROVAL"
        assert result["work_order"]["requires_human_approval"] is True

    def test_audit_record_written_to_log(self, tmp_path):
        from pathlib import Path
        from gridguard.config import settings
        settings.AUDIT_LOG_PATH = tmp_path / "workflow_test_audit.jsonl"
        settings.AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

        from gridguard.agent import run_mock_workflow
        from gridguard.tools.audit import read_audit_log
        result = run_mock_workflow("EQUIPMENT_RISK")
        records = read_audit_log(settings.AUDIT_LOG_PATH)
        assert len(records) >= 1
        actions = [r["action"] for r in records]
        assert "WORKFLOW_COMPLETED" in actions

    def test_event_id_in_work_order(self):
        from gridguard.agent import run_mock_workflow
        result = run_mock_workflow("OUTAGE_WARNING")
        event_id = result["event"]["event_id"]
        assert result["work_order"]["event_id"] == event_id

    def test_assessment_risk_score_within_bounds(self):
        from gridguard.agent import run_mock_workflow
        for scenario in SCENARIOS:
            result = run_mock_workflow(scenario)
            score = result["assessment"]["severity_score"]
            assert 1 <= score <= 5, f"Score {score} out of bounds for {scenario}"

    def test_mitigation_plan_has_steps(self):
        from gridguard.agent import run_mock_workflow
        result = run_mock_workflow("SEVERE_WEATHER")
        assert result["plan"]["step_count"] >= 3
        for step in result["plan"]["steps"]:
            assert "action" in step
            assert "step" in step

    def test_on_step_callback_called(self):
        from gridguard.agent import run_mock_workflow
        called = []
        def callback(step):
            called.append(step.tool_name)
        run_mock_workflow("HIGH_DEMAND", on_step=callback)
        assert len(called) == 8
        assert "get_grid_snapshot" in called
        assert "forecast_demand_xgboost" in called
        assert "record_audit_event" in called
