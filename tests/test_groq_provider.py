"""
Tests for the guarded optional Groq provider.

All tests run in MOCK_MODE with no real LLM calls.
Validates gate logic, secret hygiene, and config selection.
"""

from __future__ import annotations

import pytest


# -- Helpers -------------------------------------------------------------------

def _patch_for_groq(monkeypatch, *, mock_mode=False, live_llm_enabled=True,
                    groq_key="gsk_testkey123", groq_model="openai/gpt-oss-20b"):
    """Patch settings to simulate a fully-configured Groq live-mode environment."""
    from gridguard import config as cfg
    monkeypatch.setattr(cfg.settings, "MOCK_MODE", mock_mode)
    monkeypatch.setattr(cfg.settings, "LIVE_LLM_ENABLED", live_llm_enabled)
    monkeypatch.setattr(cfg.settings, "STRANDS_PROVIDER", "groq")
    monkeypatch.setattr(cfg.settings, "GROQ_API_KEY", groq_key)
    monkeypatch.setattr(cfg.settings, "GROQ_MODEL_ID", groq_model)


# -- 1. Default settings remain mock mode -------------------------------------

def test_default_mock_mode_is_true():
    from gridguard.config import Settings
    fresh = Settings()
    assert fresh.MOCK_MODE is True


def test_default_live_llm_enabled_is_false():
    from gridguard.config import Settings
    fresh = Settings()
    assert fresh.LIVE_LLM_ENABLED is False


def test_default_groq_api_key_is_empty(monkeypatch):
    # Clear both env file and OS env var so we test only the coded default.
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from gridguard.config import Settings
    fresh = Settings(_env_file=None)
    assert fresh.GROQ_API_KEY == ""


def test_is_groq_false_by_default():
    from gridguard.config import Settings
    fresh = Settings()
    assert fresh.is_groq() is False


def test_is_groq_true_when_provider_set(monkeypatch):
    from gridguard import config as cfg
    monkeypatch.setattr(cfg.settings, "STRANDS_PROVIDER", "groq")
    assert cfg.settings.is_groq() is True


# -- 2. Missing key cannot enable live mode -----------------------------------

def test_gate_blocks_when_groq_key_missing(monkeypatch):
    from gridguard import config as cfg
    from gridguard.safeguards import validate_groq_live_gate
    monkeypatch.setattr(cfg.settings, "MOCK_MODE", False)
    monkeypatch.setattr(cfg.settings, "LIVE_LLM_ENABLED", True)
    monkeypatch.setattr(cfg.settings, "STRANDS_PROVIDER", "groq")
    monkeypatch.setattr(cfg.settings, "GROQ_API_KEY", "")
    with pytest.raises(RuntimeError) as exc_info:
        validate_groq_live_gate()
    msg = str(exc_info.value)
    assert "GROQ_API_KEY is not configured" in msg
    assert "gsk_" not in msg


# -- 3. Gate passes only when every condition is satisfied --------------------

def test_gate_passes_with_all_conditions_met(monkeypatch):
    _patch_for_groq(monkeypatch)
    from gridguard.safeguards import validate_groq_live_gate
    validate_groq_live_gate()  # must not raise


def test_gate_blocks_when_mock_mode_true(monkeypatch):
    _patch_for_groq(monkeypatch, mock_mode=True)
    from gridguard.safeguards import validate_groq_live_gate
    with pytest.raises(RuntimeError) as exc_info:
        validate_groq_live_gate()
    assert "MOCK_MODE is on" in str(exc_info.value)


def test_gate_blocks_when_live_llm_not_enabled(monkeypatch):
    _patch_for_groq(monkeypatch, live_llm_enabled=False)
    from gridguard.safeguards import validate_groq_live_gate
    with pytest.raises(RuntimeError) as exc_info:
        validate_groq_live_gate()
    assert "LIVE_LLM_ENABLED is false" in str(exc_info.value)


def test_gate_blocks_when_provider_not_groq(monkeypatch):
    _patch_for_groq(monkeypatch)
    from gridguard import config as cfg
    monkeypatch.setattr(cfg.settings, "STRANDS_PROVIDER", "bedrock")
    from gridguard.safeguards import validate_groq_live_gate
    with pytest.raises(RuntimeError) as exc_info:
        validate_groq_live_gate()
    assert "STRANDS_PROVIDER is 'bedrock'" in str(exc_info.value)


# -- 4. No secret appears in error messages or status text --------------------

def test_no_secret_in_gate_error_messages(monkeypatch):
    _patch_for_groq(monkeypatch, groq_key="gsk_supersecret9999", live_llm_enabled=False)
    from gridguard.safeguards import validate_groq_live_gate
    with pytest.raises(RuntimeError) as exc_info:
        validate_groq_live_gate()
    msg = str(exc_info.value)
    assert "gsk_supersecret9999" not in msg


def test_redact_secrets_covers_groq_key():
    from gridguard.safeguards import redact_secrets
    payload = {"groq_api_key": "gsk_realkey", "other": "visible"}
    result = redact_secrets(payload)
    assert result["groq_api_key"] == "[REDACTED]"
    assert result["other"] == "visible"


# -- 5. Mock workflow is unaffected -------------------------------------------

def test_mock_workflow_unaffected_by_groq_config(monkeypatch):
    from gridguard import config as cfg
    from gridguard.agent import run_mock_workflow
    monkeypatch.setattr(cfg.settings, "MOCK_MODE", True)
    monkeypatch.setattr(cfg.settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(cfg.settings, "LIVE_LLM_ENABLED", False)
    result = run_mock_workflow("SEVERE_WEATHER")
    assert result["mock_mode"] is True
    assert result["overall_status"] == "AWAITING_HUMAN_APPROVAL"
    assert result["operator_briefing"] is None


# -- 6. Groq-specific Prompt and Configuration ----------------------------------

def test_groq_system_prompt_is_concise():
    from gridguard.agent import GROQ_BRIEFING_SYSTEM_PROMPT
    assert "150 words" in GROQ_BRIEFING_SYSTEM_PROMPT
    assert "chain-of-thought" in GROQ_BRIEFING_SYSTEM_PROMPT
    assert "DRAFT_PENDING_APPROVAL" in GROQ_BRIEFING_SYSTEM_PROMPT


def test_groq_model_configured_with_low_reasoning_effort(monkeypatch):
    _patch_for_groq(monkeypatch)
    from gridguard import agent
    import strands.models.openai
    import strands
    
    # We want to capture the model kwargs without invoking Groq
    captured_kwargs = {}
    
    class CaptureModel:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            
    # Mock the Agent to just return a dummy string instead of calling an LLM
    class DummyAgentResult:
        def __str__(self): return "test briefing"

    monkeypatch.setattr(strands.models.openai, "OpenAIModel", CaptureModel)
    monkeypatch.setattr(strands, "Agent", lambda **kw: lambda *a, **k: DummyAgentResult())
    
    from gridguard import safeguards
    monkeypatch.setattr(safeguards, "validate_groq_live_gate", lambda: None)
    monkeypatch.setattr(safeguards, "increment_and_check_live_run_limit", lambda: None)

    event = {"title": "A", "event_type": "B", "event_id": "C", "region": "D", "description": "E"}
    snapshot = {"demand_mw": 0, "available_capacity_mw": 0, "contingency_reserve_mw": 0, "frequency_hz": 60, "alert_level": "None"}
    forecast = {"predicted_peak_mw": 0, "available_capacity_mw": 0, "reserve_margin_pct": 0, "reserve_margin_mw": 0, "high_risk_hours": 0, "forecast_risk_level": "A", "headline": "B"}
    assessment = {"severity_score": 1, "severity_label": "C", "priority_tier": 1, "forecast_impact_explanation": "D", "risk_summary": "E"}
    
    agent.generate_groq_briefing(event, snapshot, forecast, assessment, {}, {})
    
    assert "params" in captured_kwargs
    params = captured_kwargs["params"]
    assert params.get("reasoning_effort") == "low"
    assert "max_tokens" in params
