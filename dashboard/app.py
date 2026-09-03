"""
GridGuard Strands Operations Autopilot — Streamlit Dashboard

Launch with:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Make the project root importable when running from anywhere
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from gridguard.agent import run_mock_workflow
from gridguard.config import settings
from gridguard.data.synthetic_events import get_scenario_names
from gridguard.tools.audit import read_audit_log
from gridguard.tools.human_approval import get_pending_approval, resolve_approval

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GridGuard Strands Autopilot",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS Design System ─────────────────────────────────────────────────────────
# Professional, accessible palette: navy primary, steel-blue accents,
# amber warnings, crimson critical. No excessive purple/green/orange.
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Background ── */
    .stApp {
        background: #0d1117;
        color: #e6edf3;
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: #161b22;
        border-right: 1px solid #21262d;
    }

    /* ── Cards ── */
    .gg-card {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 10px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
    }
    .gg-card-critical { border-left: 4px solid #dc2626; }
    .gg-card-high     { border-left: 4px solid #d97706; }
    .gg-card-medium   { border-left: 4px solid #4a7fc1; }
    .gg-card-low      { border-left: 4px solid #4b5563; }
    .gg-card-info     { border-left: 4px solid #374151; }

    /* ── Status badges ── */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .badge-critical  { background: #7f1d1d; color: #fca5a5; }
    .badge-high      { background: #78350f; color: #fde68a; }
    .badge-medium    { background: #1e3a5f; color: #93c5fd; }
    .badge-low       { background: #1f2937; color: #9ca3af; }
    .badge-pending   { background: #78350f; color: #fde68a; }
    .badge-approved  { background: #14532d; color: #86efac; }
    .badge-rejected  { background: #7f1d1d; color: #fca5a5; }
    .badge-done      { background: #14532d; color: #86efac; }
    .badge-running   { background: #1e3a5f; color: #93c5fd; }
    .badge-error     { background: #7f1d1d; color: #fca5a5; }

    /* ── Section headers ── */
    .section-header {
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #6e7681;
        border-bottom: 1px solid #21262d;
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }

    /* ── Step timeline ── */
    .step-row {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.6rem 0;
        border-bottom: 1px solid #21262d;
    }
    .step-number {
        width: 1.75rem;
        height: 1.75rem;
        border-radius: 50%;
        background: #21262d;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        font-weight: 700;
        flex-shrink: 0;
        color: #8b949e;
    }
    .step-number-done { background: #14532d; color: #86efac; }
    .step-name { flex: 1; font-size: 0.9rem; font-weight: 500; }
    .step-tool { font-size: 0.75rem; color: #6e7681; font-family: 'JetBrains Mono', monospace; }
    .step-time { font-size: 0.72rem; color: #6e7681; }

    /* ── Work order ── */
    .wo-field { margin-bottom: 0.5rem; }
    .wo-label { font-size: 0.72rem; color: #6e7681; text-transform: uppercase; letter-spacing: 0.05em; }
    .wo-value { font-size: 0.9rem; color: #e6edf3; font-weight: 500; }

    /* ── Audit table ── */
    .audit-row {
        font-size: 0.78rem;
        font-family: 'JetBrains Mono', monospace;
        padding: 0.3rem 0;
        border-bottom: 1px solid #21262d;
        color: #8b949e;
    }

    /* ── Hero ── */
    .hero-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: #e6edf3;
        letter-spacing: -0.02em;
    }
    .hero-subtitle {
        font-size: 0.9rem;
        color: #8b949e;
        margin-top: 0.25rem;
    }

    /* ── Severity gauge ── */
    .severity-bar-outer {
        background: #21262d;
        border-radius: 9999px;
        height: 8px;
        margin-top: 0.5rem;
    }
    .severity-bar-inner {
        border-radius: 9999px;
        height: 8px;
        transition: width 0.5s ease;
    }

    /* ── Safety notice ── */
    .safety-notice {
        background: #161b22;
        border: 1px solid #30363d;
        border-left: 4px solid #4a7fc1;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        font-size: 0.78rem;
        color: #8b949e;
    }

    /* Streamlit override: hide default menu/footer for demo */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state init ────────────────────────────────────────────────────────

def _init_state() -> None:
    defaults = {
        "workflow_result": None,
        "run_error": None,
        "approval_token": None,
        "approval_status": "NONE",  # NONE | PENDING | APPROVED | REJECTED
        "approver_name": "Operator",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()

# ── Helper: severity colours ──────────────────────────────────────────────────

def _severity_color(label: str) -> str:
    return {
        "CRITICAL": "#dc2626",
        "HIGH": "#d97706",
        "MEDIUM": "#4a7fc1",
        "LOW": "#6b7280",
        "INFORMATIONAL": "#374151",
    }.get(label, "#6b7280")


def _severity_class(label: str) -> str:
    return {
        "CRITICAL": "critical",
        "HIGH": "high",
        "MEDIUM": "medium",
        "LOW": "low",
        "INFORMATIONAL": "info",
    }.get(label, "low")


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        '<p style="font-size:1.3rem;font-weight:700;color:#e6edf3;">⚡ GridGuard</p>'
        '<p style="font-size:0.8rem;color:#8b949e;margin-top:-0.5rem;">Strands Operations Autopilot</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown('<div class="section-header">Event Ingestion</div>', unsafe_allow_html=True)
    scenario = st.selectbox(
        "Select Grid-Risk Scenario",
        options=get_scenario_names(),
        format_func=lambda s: {
            "SEVERE_WEATHER": "🌨️ Severe Weather",
            "HIGH_DEMAND": "🔥 High Demand",
            "EQUIPMENT_RISK": "⚠️ Equipment Risk",
            "OUTAGE_WARNING": "🚧 Outage Warning",
        }.get(s, s),
        index=0,
        key="scenario_select",
    )

    st.markdown('<div class="section-header" style="margin-top:1rem;">Approver Identity</div>', unsafe_allow_html=True)
    approver_name = st.text_input("Your name (for audit)", value="Shift Manager", key="approver_name_input")

    st.divider()
    run_btn = st.button(
        "▶ Run Agent Workflow",
        use_container_width=True,
        type="primary",
    )

    st.divider()
    st.markdown(
        '<div class="safety-notice">'
        "⚠️ <strong>Safety Notice</strong><br>"
        "This system operates on <em>synthetic data only</em>. "
        "It does not connect to, monitor, or control any real electric grid."
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="margin-top:1rem;font-size:0.72rem;color:#6e7681;">'
        f"MOCK_MODE: {'ON ✓' if settings.MOCK_MODE else 'OFF — live LLM'}"
        "</div>",
        unsafe_allow_html=True,
    )

# ── Main area header ─────────────────────────────────────────────────────────

st.markdown(
    '<div class="hero-title">GridGuard Strands Operations Autopilot</div>'
    '<div class="hero-subtitle">Autonomous grid-risk triage · Human-governed decisions · Immutable audit trail</div>',
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Execute workflow synchronously ───────────────────────────────────────────

if run_btn:
    st.session_state.run_error = None
    with st.spinner("Agent is running the workflow… (MOCK_MODE — no API calls)"):
        try:
            result = run_mock_workflow(scenario)
            st.session_state.workflow_result = result
            st.session_state.approval_token = result["approval_request"]["approval_token"]
            st.session_state.approval_status = "PENDING"
        except Exception as exc:
            st.session_state.run_error = str(exc)
            st.session_state.workflow_result = None

# ── Error display ─────────────────────────────────────────────────────────────

if st.session_state.run_error:
    st.error(f"Workflow error: {st.session_state.run_error}")

# ── Empty state ───────────────────────────────────────────────────────────────

if st.session_state.workflow_result is None:
    st.markdown(
        '<div class="gg-card" style="text-align:center;padding:3rem;">'
        '<div style="font-size:3rem;">⚡</div>'
        '<div style="font-size:1.1rem;font-weight:600;margin-top:0.5rem;color:#e6edf3;">Ready to run</div>'
        '<div style="color:#8b949e;margin-top:0.5rem;">'
        "Select a scenario in the sidebar and click <strong>Run Agent Workflow</strong>."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

# ── Render workflow result ────────────────────────────────────────────────────

result: dict[str, Any] = st.session_state.workflow_result
event = result["event"]
assessment = result["assessment"]
plan = result["plan"]
work_order = result["work_order"]
approval = result["approval_request"]
snapshot = result["snapshot"]
runbook = result["runbook"]
steps_data = result["steps"]

sev_label = assessment["severity_label"]
sev_score = assessment["severity_score"]
sev_class = _severity_class(sev_label)
sev_color = _severity_color(sev_label)

# ── Event banner ──────────────────────────────────────────────────────────────

st.markdown(
    f'<div class="gg-card gg-card-{sev_class}">'
    f'<div style="display:flex;align-items:center;gap:1rem;">'
    f'<div style="flex:1;">'
    f'<div class="section-header">Ingested Event</div>'
    f'<div style="font-size:1.1rem;font-weight:600;color:#e6edf3;">{event["title"]}</div>'
    f'<div style="font-size:0.85rem;color:#8b949e;margin-top:0.35rem;">{event["description"]}</div>'
    f'</div>'
    f'<div style="text-align:right;flex-shrink:0;">'
    f'<span class="badge badge-{sev_class}">{sev_label}</span><br>'
    f'<span style="font-size:0.75rem;color:#6e7681;">{event["event_id"]}</span>'
    f'</div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Three column layout ───────────────────────────────────────────────────────

col_timeline, col_detail = st.columns([1, 2], gap="large")

# ── Left: Workflow Timeline ───────────────────────────────────────────────────

with col_timeline:
    st.markdown('<div class="section-header">Workflow Timeline</div>', unsafe_allow_html=True)
    step_icons = ["📡", "📖", "📊", "🛠️", "📋", "🔐", "📝"]
    for i, step in enumerate(steps_data):
        icon = step_icons[i] if i < len(step_icons) else "•"
        status = step["status"]
        badge_cls = "badge-" + {"DONE": "done", "RUNNING": "running", "ERROR": "error", "PENDING": "low"}.get(status, "low")
        elapsed = f"{step['elapsed_ms']:.0f} ms" if step.get("elapsed_ms") else ""
        num_cls = "step-number-done" if status == "DONE" else ""
        st.markdown(
            f'<div class="step-row">'
            f'<div class="step-number {num_cls}">{i+1}</div>'
            f'<div style="flex:1;">'
            f'<div class="step-name">{icon} {step["name"]}</div>'
            f'<div class="step-tool">{step["tool_name"]}()</div>'
            f'</div>'
            f'<div style="text-align:right;">'
            f'<span class="badge {badge_cls}">{status}</span><br>'
            f'<span class="step-time">{elapsed}</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Overall status
    appr_status = st.session_state.approval_status
    overall_cls = {
        "APPROVED": "badge-approved",
        "REJECTED": "badge-rejected",
        "PENDING": "badge-pending",
        "NONE": "badge-low",
    }.get(appr_status, "badge-low")
    st.markdown(
        f'<div style="margin-top:1rem;text-align:center;">'
        f'<span class="badge {overall_cls}" style="font-size:0.85rem;padding:0.4rem 1rem;">'
        f'Overall: {appr_status}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Right: Tabs ───────────────────────────────────────────────────────────────

with col_detail:
    tab_risk, tab_grid, tab_plan, tab_wo, tab_runbook = st.tabs(
        ["📊 Risk", "📡 Grid Snapshot", "🛠️ Mitigation Plan", "📋 Work Order", "📖 Runbook"]
    )

    # ── Risk Tab ──────────────────────────────────────────────────────────────
    with tab_risk:
        st.markdown('<div class="section-header">Risk Assessment</div>', unsafe_allow_html=True)

        # Severity gauge
        bar_pct = sev_score * 20  # 1–5 → 20–100
        st.markdown(
            f'<div class="gg-card gg-card-{sev_class}">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div><span style="font-size:2rem;font-weight:700;color:{sev_color};">{sev_score}</span>'
            f'<span style="color:#6e7681;font-size:1rem;"> / 5</span></div>'
            f'<span class="badge badge-{sev_class}" style="font-size:0.9rem;padding:0.3rem 0.9rem;">{sev_label}</span>'
            f'</div>'
            f'<div class="severity-bar-outer"><div class="severity-bar-inner" '
            f'style="width:{bar_pct}%;background:{sev_color};"></div></div>'
            f'<div style="margin-top:0.75rem;font-size:0.85rem;color:#8b949e;">{assessment["risk_summary"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Metrics row
        m1, m2, m3 = st.columns(3)
        m1.metric("Priority Tier", assessment["priority_tier"])
        m2.metric("Reserve Margin", f"{assessment['reserve_margin_pct']}%")
        m3.metric("Load Factor", f"{assessment['load_factor_pct']}%")

        m4, m5 = st.columns(2)
        m4.metric("Contingency Reserve", f"{assessment['contingency_reserve_mw']:,.0f} MW")
        m5.metric("Immediate Action?", "Yes" if assessment["requires_immediate_action"] else "No")

        if assessment["affected_assets"]:
            st.markdown(
                f'<div style="margin-top:0.5rem;font-size:0.82rem;color:#8b949e;">'
                f'Affected assets: <code>{", ".join(assessment["affected_assets"])}</code></div>',
                unsafe_allow_html=True,
            )

    # ── Grid Snapshot Tab ─────────────────────────────────────────────────────
    with tab_grid:
        st.markdown('<div class="section-header">Live Grid Snapshot (Synthetic)</div>', unsafe_allow_html=True)
        sg1, sg2 = st.columns(2)
        sg1.metric("Region", snapshot["region"])
        sg2.metric("Alert Level", snapshot["alert_level"])
        sg3, sg4, sg5 = st.columns(3)
        sg3.metric("Demand", f"{snapshot['demand_mw']:,} MW")
        sg4.metric("Available Capacity", f"{snapshot['available_capacity_mw']:,} MW")
        sg5.metric("Reserve", f"{snapshot['contingency_reserve_mw']:,} MW")
        sg6, sg7, sg8 = st.columns(3)
        sg6.metric("Frequency", f"{snapshot['frequency_hz']} Hz")
        sg7.metric("Interchange", f"{snapshot['interchange_mw']:+,} MW")
        sg8.metric("Voltage Profile", snapshot["voltage_profile"])
        st.caption(f"As of: {snapshot['as_of']} | Source: {snapshot['data_source']}")

    # ── Mitigation Plan Tab ───────────────────────────────────────────────────
    with tab_plan:
        st.markdown('<div class="section-header">Mitigation Plan</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="gg-card" style="background:#1c2128;margin-bottom:1rem;">'
            f'<div style="font-size:0.78rem;color:#8b949e;">{plan["advisory_header"]}</div>'
            f'<div style="font-size:0.72rem;color:#6e7681;margin-top:0.5rem;">Plan ID: {plan["plan_id"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        for step in plan["steps"]:
            step_num = step.get("step", "?")
            responsible = step.get("responsible", "TBD")
            timeframe = step.get("timeframe", "")
            st.markdown(
                f'<div class="gg-card" style="padding:0.9rem 1.1rem;margin-bottom:0.5rem;">'
                f'<div style="display:flex;gap:0.75rem;align-items:flex-start;">'
                f'<div class="step-number step-number-done" style="margin-top:0.1rem;">{step_num}</div>'
                f'<div>'
                f'<div style="font-size:0.88rem;font-weight:500;">{step["action"]}</div>'
                f'<div style="font-size:0.75rem;color:#8b949e;margin-top:0.2rem;">'
                f'👤 {responsible} &nbsp;|&nbsp; ⏱ {timeframe}</div>'
                f'</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Work Order Tab ────────────────────────────────────────────────────────
    with tab_wo:
        st.markdown('<div class="section-header">Work Order Draft</div>', unsafe_allow_html=True)

        wo = work_order
        # Status banner
        if st.session_state.approval_status == "APPROVED":
            wo_status_html = '<span class="badge badge-approved" style="font-size:0.9rem;">✅ APPROVED</span>'
        elif st.session_state.approval_status == "REJECTED":
            wo_status_html = '<span class="badge badge-rejected" style="font-size:0.9rem;">❌ REJECTED</span>'
        else:
            wo_status_html = '<span class="badge badge-pending" style="font-size:0.9rem;">⏳ PENDING APPROVAL</span>'

        st.markdown(
            f'<div class="gg-card gg-card-{sev_class}">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div class="wo-value" style="font-size:1.1rem;">{wo["work_order_number"]}</div>'
            f'{wo_status_html}'
            f'</div>'
            f'<div style="margin-top:0.75rem;display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;">'
            f'<div><div class="wo-label">Event Type</div><div class="wo-value">{wo["event_type"]}</div></div>'
            f'<div><div class="wo-label">Region</div><div class="wo-value">{wo["region"]}</div></div>'
            f'<div><div class="wo-label">Priority</div><div class="wo-value">{wo["priority_tier"]}</div></div>'
            f'<div><div class="wo-label">Response Time</div><div class="wo-value">{wo["required_response_time"]}</div></div>'
            f'<div><div class="wo-label">Mitigation Plan</div><div class="wo-value">{wo["mitigation_plan_id"]}</div></div>'
            f'<div><div class="wo-label">Approval Authority</div><div class="wo-value">{wo["approval_authority"]}</div></div>'
            f'</div>'
            f'<div style="margin-top:0.75rem;padding:0.75rem;background:#0d1117;border-radius:6px;font-size:0.82rem;color:#8b949e;">'
            f'{wo["work_description"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Safety notice
        st.markdown(
            f'<div class="safety-notice">{wo["safety_notice"]}</div>',
            unsafe_allow_html=True,
        )

        # ── HITL Approval Gate ─────────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div class="section-header">⚠️ Human Approval Gate</div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:0.85rem;color:#8b949e;margin-bottom:0.75rem;">'
            "This work order requires your explicit approval before any field action. "
            "Review all steps above, then click Approve or Reject."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="font-size:0.75rem;color:#6e7681;margin-bottom:0.75rem;">'
            f'Approval token: <code>{approval["approval_token"]}</code>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if st.session_state.approval_status == "PENDING":
            rationale = st.text_area(
                "Rationale (optional)",
                placeholder="Enter your decision rationale...",
                height=80,
                key="approval_rationale",
            )
            col_approve, col_reject = st.columns(2)
            with col_approve:
                if st.button("✅ Approve Work Order", use_container_width=True, type="primary", key="btn_approve"):
                    resolve_approval(
                        token=st.session_state.approval_token,
                        decision="APPROVED",
                        approver=approver_name or "Operator",
                        rationale=rationale,
                    )
                    # Write audit record for the decision
                    from gridguard.tools.audit import record_audit_event
                    record_audit_event(
                        action="APPROVED",
                        actor=f"OPERATOR:{approver_name or 'Operator'}",
                        event_type=event["event_type"],
                        event_id=event["event_id"],
                        work_order_number=wo["work_order_number"],
                        outcome=f"Work order {wo['work_order_number']} APPROVED by {approver_name}.",
                        details={"token": st.session_state.approval_token, "rationale": rationale},
                    )
                    st.session_state.approval_status = "APPROVED"
                    st.rerun()
            with col_reject:
                if st.button("❌ Reject Work Order", use_container_width=True, key="btn_reject"):
                    resolve_approval(
                        token=st.session_state.approval_token,
                        decision="REJECTED",
                        approver=approver_name or "Operator",
                        rationale=rationale,
                    )
                    from gridguard.tools.audit import record_audit_event
                    record_audit_event(
                        action="REJECTED",
                        actor=f"OPERATOR:{approver_name or 'Operator'}",
                        event_type=event["event_type"],
                        event_id=event["event_id"],
                        work_order_number=wo["work_order_number"],
                        outcome=f"Work order {wo['work_order_number']} REJECTED by {approver_name}.",
                        details={"token": st.session_state.approval_token, "rationale": rationale},
                    )
                    st.session_state.approval_status = "REJECTED"
                    st.rerun()

        elif st.session_state.approval_status == "APPROVED":
            st.success(f"✅ Work order approved by **{approver_name}**. Audit record written.")
        elif st.session_state.approval_status == "REJECTED":
            st.error(f"❌ Work order rejected by **{approver_name}**. Audit record written.")

    # ── Runbook Tab ───────────────────────────────────────────────────────────
    with tab_runbook:
        st.markdown('<div class="section-header">Operational Runbook (Synthetic)</div>', unsafe_allow_html=True)
        rb = runbook
        st.markdown(
            f'<div class="gg-card">'
            f'<div style="font-size:1rem;font-weight:600;">{rb.get("title","")}</div>'
            f'<div style="font-size:0.75rem;color:#6e7681;">ID: {rb.get("runbook_id","")} &nbsp;|&nbsp; Version: {rb.get("version","")}</div>'
            f'<div style="font-size:0.82rem;color:#8b949e;margin-top:0.5rem;"><strong>Scope:</strong> {rb.get("scope","")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if rb.get("pre_conditions"):
            st.markdown("**Pre-conditions:**")
            for pc in rb["pre_conditions"]:
                st.markdown(f"- {pc}")

        st.markdown("**Response Steps:**")
        for s in rb.get("response_steps", []):
            st.markdown(
                f'<div class="gg-card" style="padding:0.75rem;margin-bottom:0.5rem;">'
                f'<strong>Step {s["step"]}: {s["action"]}</strong><br>'
                f'<span style="font-size:0.82rem;color:#8b949e;">{s["detail"]}</span><br>'
                f'<span style="font-size:0.72rem;color:#6e7681;">👤 {s["responsible"]} &nbsp;|&nbsp; ⏱ {s["timeframe"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if rb.get("escalation_criteria"):
            st.markdown("**Escalation Criteria:**")
            for ec in rb["escalation_criteria"]:
                st.markdown(f"- {ec}")

# ── Audit Trail ───────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown('<div class="section-header">Immutable Audit Trail</div>', unsafe_allow_html=True)

audit_records = read_audit_log()
if not audit_records:
    st.caption("No audit records yet. Run a workflow to populate the audit log.")
else:
    # Most recent first
    audit_records = list(reversed(audit_records))
    for rec in audit_records[:25]:  # cap display at 25
        action = rec.get("action", "")
        actor = rec.get("actor", "")
        ts = rec.get("recorded_at", "")[:19].replace("T", " ")
        outcome = rec.get("outcome", "")
        wo = rec.get("work_order_number", "")
        hash_short = rec.get("record_hash", "")[:12]
        st.markdown(
            f'<div class="audit-row">'
            f'<code>{ts}</code> &nbsp;|&nbsp; '
            f'<strong>{action}</strong> &nbsp;|&nbsp; '
            f'{actor} &nbsp;|&nbsp; '
            f'{outcome} &nbsp;|&nbsp; '
            f'<span style="color:#30363d;">#{hash_short}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if len(audit_records) > 25:
        st.caption(f"Showing 25 of {len(audit_records)} records.")
