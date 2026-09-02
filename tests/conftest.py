"""
pytest conftest — shared fixtures for GridGuard test suite.
All tests run in MOCK_MODE with a temporary audit log.
No LLM calls, no cloud credentials required.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def mock_mode_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Force MOCK_MODE=true and redirect the audit log to a temp directory
    for every test. Prevents any accidental LLM calls and keeps test
    runs isolated.

    Directly patches the settings singleton that all tool modules import.
    """
    audit_path = tmp_path / "audit_log.jsonl"

    # Patch the singleton settings object directly — this is the most reliable
    # approach since tools import `settings` from gridguard.config at module load time.
    from gridguard import config as cfg
    monkeypatch.setattr(cfg.settings, "MOCK_MODE", True)
    monkeypatch.setattr(cfg.settings, "AUDIT_LOG_PATH", audit_path)

    yield


@pytest.fixture()
def sample_event():
    from gridguard.data.synthetic_events import build_event
    return build_event("SEVERE_WEATHER")


@pytest.fixture()
def sample_assessment():
    return {
        "event_type": "SEVERE_WEATHER",
        "region": "ISNE",
        "severity_score": 4,
        "severity_label": "HIGH",
        "priority_tier": "P2",
        "reserve_margin_pct": 8.1,
        "load_factor_pct": 91.9,
        "contingency_reserve_mw": 1200,
        "affected_assets": ["TX-N-447", "LINE-N12"],
        "requires_immediate_action": True,
        "requires_human_approval": True,
        "risk_summary": "Event type: SEVERE_WEATHER in region ISNE.",
    }
