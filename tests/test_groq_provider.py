"""
Tests for the guarded optional Groq provider.

All tests run in MOCK_MODE with no real LLM calls.
Validates gate logic, secret hygiene, and config selection.
"""

from __future__ import annotations

import pytest


# -- Helpers -------------------------------------------------------------------

def _patch_for_groq(monkeypatch, *, mock_mode=False, live_llm_enabled=True,
                    groq_key="gsk_testkey123", groq_model="openai/gpt-oss-20b",
                    access_code="secret123"):
    """Patch settings to simulate a fully-configured Groq live-mode environment."""
    from gridguard import config as cfg
    monkeypatch.setattr(cfg.settings, "MOCK_MODE", mock_mode)
    monkeypatch.setattr(cfg.settings, "LIVE_LLM_ENABLED", live_llm_enabled)
    monkeypatch.setattr(cfg.settings, "STRANDS_PROVIDER", "groq")
    monkeypatch.setattr(cfg.settings, "GROQ_API_KEY", groq_key)
    monkeypatch.setattr(cfg.settings, "GROQ_MODEL_ID", groq_model)
    monkeypatch.setattr(cfg.settings, "LIVE_DEMO_ACCESS_CODE", access_code)


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
    from gridguard.safeguards import validate_live_demo_gate, LiveModeDemoGateError
    monkeypatch.setattr(cfg.settings, "MOCK_MODE", False)
    monkeypatch.setattr(cfg.settings, "LIVE_LLM_ENABLED", True)
    monkeypatch.setattr(cfg.settings, "STRANDS_PROVIDER", "groq")
    monkeypatch.setattr(cfg.settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(cfg.settings, "LIVE_DEMO_ACCESS_CODE", "secret")
    with pytest.raises(LiveModeDemoGateError) as exc_info:
        validate_live_demo_gate("secret")
    msg = str(exc_info.value)
    assert "locked" in msg.lower() or "synthetic mode active" in msg.lower()
    assert "gsk_" not in msg
    assert "secret" not in msg


# -- 3. Wrong/missing access code cannot enable live mode ---------------------

def test_gate_blocks_wrong_access_code(monkeypatch):
    _patch_for_groq(monkeypatch, access_code="correct_code")
    from gridguard.safeguards import validate_live_demo_gate, LiveModeDemoGateError
    with pytest.raises(LiveModeDemoGateError) as exc_info:
        validate_live_demo_gate("wrong_code")
    msg = str(exc_info.value)
    assert "locked" in msg.lower() or "synthetic mode active" in msg.lower()
    assert "wrong_code" not in msg
    assert "correct_code" not in msg


def test_gate_blocks_empty_access_code(monkeypatch):
    _patch_for_groq(monkeypatch, access_code="correct_code")
    from gridguard.safeguards import validate_live_demo_gate, LiveModeDemoGateError
    with pytest.raises(LiveModeDemoGateError):
        validate_live_demo_gate("")


def test_gate_blocks_when_server_code_not_configured(monkeypatch):
    _patch_for_groq(monkeypatch, access_code="")
    from gridguard.safeguards import validate_live_demo_gate, LiveModeDemoGateError
    with pytest.raises(LiveModeDemoGateError):
        validate_live_demo_gate("anything")


# -- 4. Gate passes only when every condition is satisfied --------------------

def test_gate_passes_with_all_conditions_met(monkeypatch):
    _patch_for_groq(monkeypatch, access_code="secret123")
    from gridguard.safeguards import validate_live_demo_gate
    validate_live_demo_gate("secret123")  # must not raise


def test_gate_blocks_when_mock_mode_true(monkeypatch):
    _patch_for_groq(monkeypatch, mock_mode=True, access_code="secret123")
    from gridguard.safeguards import validate_live_demo_gate, LiveModeDemoGateError
    with pytest.raises(LiveModeDemoGateError):
        validate_live_demo_gate("secret123")


def test_gate_blocks_when_live_llm_not_enabled(monkeypatch):
    _patch_for_groq(monkeypatch, live_llm_enabled=False, access_code="secret123")
    from gridguard.safeguards import validate_live_demo_gate, LiveModeDemoGateError
    with pytest.raises(LiveModeDemoGateError):
        validate_live_demo_gate("secret123")


def test_gate_blocks_when_provider_not_groq(monkeypatch):
    _patch_for_groq(monkeypatch, access_code="secret123")
    from gridguard import config as cfg
    monkeypatch.setattr(cfg.settings, "STRANDS_PROVIDER", "bedrock")
    from gridguard.safeguards import validate_live_demo_gate, LiveModeDemoGateError
    with pytest.raises(LiveModeDemoGateError):
        validate_live_demo_gate("secret123")


# -- 5. No secret appears in error messages or status text --------------------

def test_no_secret_in_gate_error_messages(monkeypatch):
    _patch_for_groq(monkeypatch, groq_key="gsk_supersecret9999", access_code="my_private_code")
    from gridguard.safeguards import validate_live_demo_gate, LiveModeDemoGateError
    with pytest.raises(LiveModeDemoGateError) as exc_info:
        validate_live_demo_gate("wrong_attempt")
    msg = str(exc_info.value)
    assert "gsk_supersecret9999" not in msg
    assert "my_private_code" not in msg
    assert "wrong_attempt" not in msg


def test_redact_secrets_covers_groq_key():
    from gridguard.safeguards import redact_secrets
    payload = {"groq_api_key": "gsk_realkey", "other": "visible"}
    result = redact_secrets(payload)
    assert result["groq_api_key"] == "[REDACTED]"
    assert result["other"] == "visible"


def test_redact_secrets_covers_live_demo_access_code():
    from gridguard.safeguards import redact_secrets
    payload = {"live_demo_access_code": "mycode", "provider": "groq"}
    result = redact_secrets(payload)
    assert result["live_demo_access_code"] == "[REDACTED]"
    assert result["provider"] == "groq"


# -- 6. Mock workflow is unaffected -------------------------------------------

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
