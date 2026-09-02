# DEVPOST Draft — GridGuard Strands Operations Autopilot

> **Status**: Draft for review — do not submit without author approval.

---

## Project Title
GridGuard Strands Operations Autopilot

## Tagline
Autonomous grid-operations triage with human-governed decisions and an immutable audit trail — built with the AWS Strands Agents SDK.

---

## Inspiration

Grid and utility operations teams face a relentless stream of risk signals: severe weather approaching, demand spikes, equipment health alerts, maintenance scheduling conflicts. Much of the initial triage work is structured and repeatable — check the runbook, score the risk, draft the mitigation, prepare the work order. Yet this work still falls on human operators, consuming time that could be spent on higher-level judgment.

GridGuard Strands Operations Autopilot automates that structured, repeatable triage work — while keeping humans firmly in control of every decision that matters.

---

## What It Does

GridGuard Strands Autopilot is an autonomous operations agent that:

1. **Ingests** a simulated grid-risk event (severe weather, high demand, equipment risk, or outage warning).
2. **Runs a structured Strands workflow** through seven purpose-built tool functions:
   - `get_grid_snapshot` — retrieves the current synthetic grid state
   - `retrieve_runbook` — fetches the relevant standard operating procedure
   - `assess_risk` — scores severity (1–5), urgency, and priority tier using deterministic rules
   - `generate_mitigation_steps` — produces an ordered, role-assigned action plan
   - `draft_work_order` — formats a structured draft work order document
   - `request_human_approval` — **the mandatory HITL gate** — the agent cannot proceed without operator sign-off
   - `record_audit_event` — writes an immutable, SHA-256-hashed record to the audit log
3. **Displays the full workflow** in a Streamlit dashboard: timeline, risk gauge, mitigation steps, work order, HITL approval buttons, and audit trail.
4. **Requires explicit human approval** before any work order is considered actionable.
5. **Writes an immutable audit trail** of every action and decision.

---

## Features

- **Genuine Strands tool orchestration** — seven `@tool`-decorated Python functions; the agent reasons about and calls them autonomously in live mode.
- **Mandatory HITL gate** — `request_human_approval` creates a pending token that the dashboard resolves via Approve/Reject buttons. The agent never auto-approves.
- **MOCK_MODE** — full end-to-end workflow with zero API calls. Ideal for CI, demos, and offline development.
- **Deterministic risk scoring** — rule-based engine: reserve margin thresholds, event type weights, and operator hints combined into a 1–5 severity score. Reproducible, auditable.
- **Four realistic scenarios** — Severe Weather, High Demand, Equipment Risk, Outage Warning — each with full synthetic event data and a matching runbook.
- **Immutable audit trail** — JSONL append-only log with SHA-256 content hashing for tamper detection.
- **Structured JSON logging** — CloudWatch-compatible, one JSON object per line.
- **25+ tests** — all pass with zero cloud credentials; covers all tools, all scenarios, and audit trail integrity.
- **Clean architecture** — ready for optional Amazon Bedrock AgentCore deployment without blocking the local MVP.

---

## Architecture Summary

```
Grid Operator
    │
    ▼ selects scenario
Streamlit Dashboard
    │
    ▼ triggers
GridGuard Agent (Strands SDK)
    │
    ├─► get_grid_snapshot   → Regional telemetry
    ├─► retrieve_runbook    → Operating procedure
    ├─► assess_risk         → Severity 1–5 · Priority P1–P5
    ├─► generate_mitigation_steps → Ordered action plan
    ├─► draft_work_order    → Structured DRAFT document
    ├─► request_human_approval ← ⚠️ MANDATORY HITL GATE
    │         │
    │    Operator: APPROVE / REJECT (dashboard buttons)
    │
    └─► record_audit_event  → audit_log.jsonl (immutable)
```

---

## How I Built It

- **Strands Agents SDK** (`strands-agents`, `strands-agents-tools`) as the central orchestration layer.
- **Python 3.11** with `pydantic-settings` for configuration, `rich` for CLI output.
- **Streamlit** for the dashboard — dark professional design with Inter font, Navy/steel-blue palette.
- **Deterministic rule engine** for risk scoring — no LLM dependency for the core workflow, making it fully testable offline.
- **MOCK_MODE** architecture — all tool functions work without any cloud provider, enabling zero-cost local development and CI.
- **SHA-256 content hashing** on every audit record for tamper-detection.

---

## Challenges

- Designing a clean separation between the Strands agent's autonomous tool calls and the synchronous mock workflow used for MOCK_MODE, so that both paths exercise the same tool functions.
- Making the HITL gate genuinely non-skippable while still allowing the dashboard to resolve it interactively without blocking the agent thread.
- Writing deterministic risk scoring that feels realistic but is fully reproducible for tests.

---

## Accomplishments

- Full end-to-end workflow running locally with `MOCK_MODE=true` — zero API keys, zero cost.
- 7 Strands tool functions, each with typed signatures, structured return types, and structured logging.
- 25+ tests covering all tools, all scenarios, and audit trail integrity — all green.
- Clean live-mode path for Bedrock or Anthropic by setting two env vars.

---

## What I Learned

- The Strands SDK's `@tool` decorator makes it straightforward to build purpose-built agentic tools that the LLM can reason about autonomously.
- Designing for MOCK_MODE from day one significantly accelerates development and testing.
- Human-in-the-loop gates are most effective when they are structurally non-skippable — not just a convention but an architectural constraint.

---

## What's Next

- Amazon Bedrock AgentCore deployment
- PostgreSQL persistence for the audit trail
- Real EIA API integration for live demand data
- Slack / PagerDuty integration for the HITL approval gate
- Multi-agent debate mode: risk analyst + compliance reviewer + chief dispatcher

---

## Originality Statement

This project was built during the Agents for Humans Hackathon submission period. It is a new Strands-based autonomous workflow inspired by domain concepts from my earlier GridGuard AI project. The Strands orchestration, tool layer, background workflow, human-approval controls, interface, tests, and hackathon-specific implementation were developed for this submission.

---

## Built With

- AWS Strands Agents SDK
- Python 3.11
- Streamlit
- Pydantic / pydantic-settings
- Rich
- pytest

---

## Try It Out

- **GitHub**: https://github.com/draculess99/GridGuard-Strands-Autopilot
- **Local demo**: `streamlit run dashboard/app.py` (after `pip install -e ".[dev]"`)
- **CLI demo**: `python scripts/run_demo.py --scenario SEVERE_WEATHER`
