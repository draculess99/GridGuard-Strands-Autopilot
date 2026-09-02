"""
Audit trail specific tests.
Verifies append-only semantics, content hash integrity, and
read/write behaviour of the audit log.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestAuditLog:

    def test_read_empty_log(self, tmp_path):
        from gridguard.tools.audit import read_audit_log
        records = read_audit_log(tmp_path / "nonexistent.jsonl")
        assert records == []

    def test_append_only_semantics(self, tmp_path):
        """Records must only ever be appended — existing lines must not change."""
        from gridguard.tools.audit import record_audit_event, read_audit_log
        from gridguard.config import settings
        path = tmp_path / "append_test.jsonl"
        settings.AUDIT_LOG_PATH = path

        record_audit_event(
            action="FIRST_ACTION", actor="AGENT", event_type="SEVERE_WEATHER",
            event_id="EVT-A", work_order_number="WO-A", outcome="First."
        )
        # Read after first write
        records_1 = read_audit_log(path)
        assert len(records_1) == 1
        first_hash = records_1[0]["record_hash"]

        record_audit_event(
            action="SECOND_ACTION", actor="AGENT", event_type="HIGH_DEMAND",
            event_id="EVT-B", work_order_number="WO-B", outcome="Second."
        )
        records_2 = read_audit_log(path)
        assert len(records_2) == 2
        # First record must be unchanged
        assert records_2[0]["record_hash"] == first_hash

    def test_record_hash_changes_on_different_content(self, tmp_path):
        from gridguard.tools.audit import _hash_record
        record_a = {
            "audit_event_id": "AUD-001", "action": "ACTION_A",
            "actor": "AGENT", "outcome": "Result A",
        }
        record_b = dict(record_a)
        record_b["outcome"] = "Result B"
        assert _hash_record(record_a) != _hash_record(record_b)

    def test_hash_is_deterministic(self):
        from gridguard.tools.audit import _hash_record
        record = {
            "audit_event_id": "AUD-DET",
            "action": "TEST",
            "actor": "AGENT",
            "outcome": "Deterministic",
        }
        h1 = _hash_record(record)
        h2 = _hash_record(record)
        assert h1 == h2

    def test_malformed_line_skipped_gracefully(self, tmp_path):
        from gridguard.tools.audit import read_audit_log
        path = tmp_path / "malformed.jsonl"
        path.write_text(
            '{"valid": true}\n'
            'NOT_JSON_AT_ALL\n'
            '{"second": true}\n',
            encoding="utf-8",
        )
        records = read_audit_log(path)
        assert len(records) == 2  # malformed line skipped

    def test_all_required_fields_present(self, tmp_path):
        from gridguard.tools.audit import record_audit_event, read_audit_log
        from gridguard.config import settings
        path = tmp_path / "fields_test.jsonl"
        settings.AUDIT_LOG_PATH = path

        record_audit_event(
            action="FIELD_CHECK", actor="SYSTEM", event_type="OUTAGE_WARNING",
            event_id="EVT-F", work_order_number="WO-F", outcome="All fields test.",
        )
        records = read_audit_log(path)
        rec = records[0]
        required_fields = [
            "audit_event_id", "recorded_at", "action", "actor",
            "event_type", "event_id", "work_order_number", "outcome",
            "record_hash",
        ]
        for field in required_fields:
            assert field in rec, f"Missing field: {field}"

    def test_approval_decision_persisted(self, tmp_path):
        from gridguard.tools.audit import record_audit_event, read_audit_log
        from gridguard.config import settings
        path = tmp_path / "approval_test.jsonl"
        settings.AUDIT_LOG_PATH = path

        record_audit_event(
            action="APPROVED",
            actor="OPERATOR:Jane Smith",
            event_type="HIGH_DEMAND",
            event_id="EVT-APPR",
            work_order_number="WO-APPR-001",
            outcome="Work order WO-APPR-001 APPROVED by Jane Smith.",
            details={"token": "APPR-ABCDEF123456", "rationale": "Reviewed and safe."},
        )
        records = read_audit_log(path)
        rec = records[0]
        assert rec["action"] == "APPROVED"
        assert rec["actor"] == "OPERATOR:Jane Smith"
        assert rec["details"]["token"] == "APPR-ABCDEF123456"
