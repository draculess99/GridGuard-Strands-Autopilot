"""
Tests for Safe, Bounded Live Amazon Bedrock Mode in GridGuard Autopilot.

All tests use strictly mocked Bedrock / Strands SDK interfaces.
NO REAL AWS OR CLOUD CALLS ARE MADE.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
import botocore.exceptions

from gridguard.config import settings
from gridguard.agent import (
    generate_live_briefing,
    run_workflow,
    format_evidence_prompt,
    BRIEFING_SYSTEM_PROMPT,
)
from gridguard.safeguards import (
    get_live_run_count,
    reset_live_run_counter,
    increment_and_check_live_run_limit,
    LiveRunLimitExceededError,
    LiveModeCredentialsError,
    LiveModeModelAccessError,
    redact_secrets,
)
from gridguard.logger import _JSONFormatter


@pytest.fixture(autouse=True)
def reset_counter_before_each_test():
    """Ensure process-level counter is reset for every test."""
    reset_live_run_counter()
    yield
    reset_live_run_counter()


class TestMockModeZeroCloudCalls:
    """Requirement 1: Preserve MOCK_MODE=true exactly with zero AWS initialization or calls."""

    def test_mock_mode_never_initializes_or_invokes_aws(self):
        with patch("boto3.Session") as mock_boto, \
             patch("strands.models.bedrock.BedrockModel") as mock_bedrock:

            result = run_workflow("SEVERE_WEATHER", mock_mode=True)

            mock_boto.assert_not_called()
            mock_bedrock.assert_not_called()
            assert result["operator_briefing"] is None
            assert result["mock_mode"] is True
            assert result["overall_status"] == "AWAITING_HUMAN_APPROVAL"
            assert result["approval_request"]["status"] == "PENDING"
            assert len(result["steps"]) == 8
            assert get_live_run_count() == 0


class TestBoundedLiveBedrockMode:
    """Requirement 2, 3, 4: Bounded single invocation, structured evidence, deterministic safety."""

    @patch("boto3.Session")
    @patch("strands.models.bedrock.BedrockModel")
    @patch("strands.Agent")
    def test_live_mode_creates_exactly_one_bounded_briefing_call(
        self, mock_agent_cls, mock_bedrock_cls, mock_boto_cls
    ):
        mock_briefing_text = (
            "1. INCIDENT SUMMARY: Severe arctic blast in ISNE region.\n"
            "2. EVIDENCE & UNCERTAINTY: XGBoost predicts peak load 24,028 MW vs 24,000 MW capacity.\n"
            "3. OPERATIONAL RATIONALE: Step 2 capacity procurement and Step 5 equipment inspection mitigate N-1 line trip.\n"
            "4. GOVERNANCE NOTICE: This mitigation plan is DRAFT and requires explicit human operator review."
        )

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.__str__.return_value = mock_briefing_text
        mock_agent_instance.return_value = mock_result
        mock_agent_cls.return_value = mock_agent_instance

        result = run_workflow("SEVERE_WEATHER", mock_mode=False)

        # 1. Exactly one bounded briefing invocation
        assert mock_agent_instance.call_count == 1
        _, kwargs = mock_agent_instance.call_args
        limits = kwargs.get("limits")
        assert limits is not None
        assert limits["turns"] == 1
        assert limits["output_tokens"] == settings.LIVE_MAX_OUTPUT_TOKENS

        # 2. Briefing result verification
        briefing = result["operator_briefing"]
        assert briefing is not None
        assert briefing["status"] == "SUCCESS"
        assert briefing["source"] == "AMAZON_BEDROCK"
        assert briefing["label"] == "Bedrock-generated operator briefing — synthetic demo only."
        assert mock_briefing_text in briefing["briefing_text"]

        # 3. Model cannot alter deterministic risk or forecast values
        assert result["forecast"]["predicted_peak_mw"] > 23000.0
        assert result["assessment"]["severity_score"] == 5
        assert result["assessment"]["severity_label"] == "CRITICAL"

        # 4. Deterministic governance preserved
        assert result["work_order"]["status"] == "DRAFT_PENDING_APPROVAL"
        assert result["approval_request"]["status"] == "PENDING"
        assert result["overall_status"] == "AWAITING_HUMAN_APPROVAL"

        # 5. Audit record includes live mode details and valid SHA-256 hash
        audit_rec = result["audit_records"][-1]
        assert audit_rec["details"]["mock_mode"] is False
        assert audit_rec["details"]["briefing_status"] == "SUCCESS"
        assert len(audit_rec["record_hash"]) == 64

        # 6. Process-level counter incremented
        assert get_live_run_count() == 1

    @patch("boto3.Session")
    @patch("strands.models.bedrock.BedrockModel")
    @patch("strands.Agent")
    def test_failed_live_call_does_not_bypass_approval_or_corrupt_audit(
        self, mock_agent_cls, mock_bedrock_cls, mock_boto_cls
    ):
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = RuntimeError("Amazon Bedrock service unavailable")
        mock_agent_cls.return_value = mock_agent_instance

        result = run_workflow("SEVERE_WEATHER", mock_mode=False)

        # Briefing records failure cleanly
        briefing = result["operator_briefing"]
        assert briefing is not None
        assert briefing["status"] == "FAILED"
        assert "Bedrock briefing failed" in briefing["label"]
        assert "Amazon Bedrock service unavailable" in briefing["error"]

        # CRITICAL SAFETY: Human approval is NOT bypassed
        assert result["overall_status"] == "AWAITING_HUMAN_APPROVAL"
        assert result["work_order"]["status"] == "DRAFT_PENDING_APPROVAL"
        assert result["approval_request"]["status"] == "PENDING"

        # CRITICAL SAFETY: Audit record is intact with valid SHA-256 hash
        audit_rec = result["audit_records"][-1]
        assert audit_rec["action"] == "WORKFLOW_COMPLETED"
        assert len(audit_rec["record_hash"]) == 64
        assert audit_rec["details"]["briefing_status"] == "FAILED"


class TestSafeguardsAndCostControl:
    """Requirement 5: Run limits, credentials validation, and secret redaction."""

    def test_live_run_limit_exceeded_safeguard(self):
        reset_live_run_counter()
        original_limit = settings.LIVE_RUN_LIMIT
        try:
            # Set artificial limit of 2 runs
            settings.LIVE_RUN_LIMIT = 2

            with patch("strands.Agent") as mock_agent_cls, \
                 patch("strands.models.bedrock.BedrockModel"), \
                 patch("boto3.Session"):

                mock_agent = MagicMock()
                mock_agent.return_value = "Briefing text"
                mock_agent_cls.return_value = mock_agent

                # 1st run: OK
                run_workflow("SEVERE_WEATHER", mock_mode=False)
                assert get_live_run_count() == 1

                # 2nd run: OK
                run_workflow("SEVERE_WEATHER", mock_mode=False)
                assert get_live_run_count() == 2

                # 3rd run: Exceeds limit -> caught gracefully by run_workflow
                result = run_workflow("SEVERE_WEATHER", mock_mode=False)
                assert result["operator_briefing"]["status"] == "FAILED"
                assert "Process live run limit reached" in result["operator_briefing"]["error"]
                # Approval still intact
                assert result["approval_request"]["status"] == "PENDING"
        finally:
            settings.LIVE_RUN_LIMIT = original_limit

    @patch("boto3.Session")
    @patch("strands.models.bedrock.BedrockModel")
    def test_missing_credentials_raises_live_mode_credentials_error(
        self, mock_bedrock, mock_boto
    ):
        mock_bedrock.side_effect = botocore.exceptions.NoCredentialsError()
        with pytest.raises(LiveModeCredentialsError) as exc_info:
            generate_live_briefing(
                event={"title": "Test", "event_type": "SEVERE_WEATHER", "event_id": "EVT-1", "region": "ISNE"},
                snapshot={"demand_mw": 20000, "available_capacity_mw": 24000, "contingency_reserve_mw": 700, "frequency_hz": 60.0, "alert_level": "WATCH"},
                forecast={"predicted_peak_mw": 23500, "available_capacity_mw": 24000, "reserve_margin_pct": 2.1, "reserve_margin_mw": 500, "high_risk_hours": 8, "forecast_risk_level": "CRITICAL", "headline": "Stress"},
                assessment={"severity_score": 5, "severity_label": "CRITICAL", "priority_tier": "P1", "forecast_impact_explanation": "Critical", "risk_summary": "Summary"},
                runbook={"runbook_id": "RB-01", "title": "Runbook"},
                plan={"step_count": 1, "steps": [{"step": 1, "action": "Act", "responsible": "Ops", "timeframe": "Now"}]},
            )
        assert "AWS credentials not found" in str(exc_info.value)

    @patch("boto3.Session")
    @patch("strands.models.bedrock.BedrockModel")
    def test_model_access_denied_raises_live_mode_model_access_error(
        self, mock_bedrock, mock_boto
    ):
        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "Model access is not enabled."}}
        mock_bedrock.side_effect = botocore.exceptions.ClientError(error_response, "Converse")

        with pytest.raises(LiveModeModelAccessError) as exc_info:
            generate_live_briefing(
                event={"title": "Test", "event_type": "SEVERE_WEATHER", "event_id": "EVT-1", "region": "ISNE"},
                snapshot={"demand_mw": 20000, "available_capacity_mw": 24000, "contingency_reserve_mw": 700, "frequency_hz": 60.0, "alert_level": "WATCH"},
                forecast={"predicted_peak_mw": 23500, "available_capacity_mw": 24000, "reserve_margin_pct": 2.1, "reserve_margin_mw": 500, "high_risk_hours": 8, "forecast_risk_level": "CRITICAL", "headline": "Stress"},
                assessment={"severity_score": 5, "severity_label": "CRITICAL", "priority_tier": "P1", "forecast_impact_explanation": "Critical", "risk_summary": "Summary"},
                runbook={"runbook_id": "RB-01", "title": "Runbook"},
                plan={"step_count": 1, "steps": [{"step": 1, "action": "Act", "responsible": "Ops", "timeframe": "Now"}]},
            )
        assert "Ensure model access is enabled" in str(exc_info.value)

    def test_secret_redaction(self):
        raw = "Error: AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY failed"
        redacted = redact_secrets(raw)
        assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in redacted
        assert "[REDACTED]" in redacted

        # Preserves operational tokens
        token = "APPR-5C8B30803D40"
        assert redact_secrets(token) == token

    def test_logger_formatter_redacts_secrets(self):
        formatter = _JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg="Connecting with aws_secret_access_key: secretKey12345678901234567890123456",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        data = json.loads(formatted)
        assert "secretKey" not in data["msg"]
        assert "[REDACTED]" in data["msg"]
