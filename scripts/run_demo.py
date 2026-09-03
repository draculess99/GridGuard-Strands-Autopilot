#!/usr/bin/env python3
"""
GridGuard Strands Autopilot — CLI Demo Runner

Run a full mock workflow from the command line and print a formatted summary.

Usage:
    python scripts/run_demo.py
    python scripts/run_demo.py --scenario HIGH_DEMAND
    python scripts/run_demo.py --scenario EQUIPMENT_RISK --approve
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from gridguard.agent import run_mock_workflow
from gridguard.data.synthetic_events import get_scenario_names
from gridguard.tools.human_approval import resolve_approval

console = Console(legacy_windows=False)


def print_step_table(steps: list[dict]) -> None:
    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold steel_blue")
    table.add_column("#", width=3)
    table.add_column("Step", min_width=20)
    table.add_column("Tool", style="dim")
    table.add_column("Status", width=8)
    table.add_column("ms", justify="right", width=8)
    for i, s in enumerate(steps, 1):
        status_color = {"DONE": "green", "ERROR": "red", "RUNNING": "yellow"}.get(s["status"], "dim")
        table.add_row(
            str(i),
            s["name"],
            s["tool_name"] + "()",
            f"[{status_color}]{s['status']}[/{status_color}]",
            f"{s['elapsed_ms']:.0f}" if s.get("elapsed_ms") else "—",
        )
    console.print(table)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GridGuard Strands Autopilot — CLI Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        choices=get_scenario_names(),
        default="SEVERE_WEATHER",
        help="Grid-risk scenario to simulate (default: SEVERE_WEATHER)",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Auto-approve the work order after workflow completes (demo shortcut)",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print raw workflow result as JSON",
    )
    args = parser.parse_args()

    console.rule("[bold steel_blue]GridGuard Strands Operations Autopilot[/]")
    console.print(f"\n[dim]Scenario:[/] [bold]{args.scenario}[/]  |  MOCK_MODE=ON\n")

    with console.status("[steel_blue]Running workflow…[/]"):
        result = run_mock_workflow(args.scenario)

    if args.json_output:
        console.print_json(json.dumps(result, default=str))
        return 0

    event = result["event"]
    assessment = result["assessment"]
    plan = result["plan"]
    work_order = result["work_order"]
    approval = result["approval_request"]

    # ── Event ─────────────────────────────────────────────────────────────────
    console.print(Panel(
        f"[bold]{event['title']}[/]\n"
        f"[dim]{event['description']}[/]\n\n"
        f"Event ID: {event['event_id']}  |  Region: {event['region']}",
        title="[bold]📥 Ingested Event[/]",
        border_style="steel_blue",
    ))

    # ── Forecast ──────────────────────────────────────────────────────────────
    forecast = result.get("forecast")
    if forecast:
        console.print(Panel(
            f"Predicted Peak: [bold]{forecast['predicted_peak_mw']:,.0f} MW[/]  |  "
            f"Available Capacity: [bold]{forecast['available_capacity_mw']:,.0f} MW[/]\n"
            f"Projected Reserve: [bold]{forecast['reserve_margin_pct']}%[/] ({forecast['reserve_margin_mw']:,.0f} MW)  |  "
            f"Horizon: [bold]{forecast['forecast_horizon_hours']}h[/]\n"
            f"Risk Category: [bold]{forecast['forecast_risk_level']}[/]  |  "
            f"High-Risk Hours: [bold]{forecast['high_risk_hours']}[/]\n\n"
            f"{forecast['headline']}",
            title="[bold]📈 XGBoost Demand Forecast (Synthetic Demo)[/]",
            border_style="cyan",
        ))

    # ── Workflow timeline ──────────────────────────────────────────────────────
    console.print("\n[bold]📋 Workflow Timeline[/]")
    print_step_table(result["steps"])

    # ── Risk assessment ────────────────────────────────────────────────────────
    sev_color = {
        "CRITICAL": "red", "HIGH": "yellow", "MEDIUM": "blue",
        "LOW": "dim", "INFORMATIONAL": "dim",
    }.get(assessment["severity_label"], "dim")

    console.print(Panel(
        f"Severity: [{sev_color}]{assessment['severity_label']}[/{sev_color}] "
        f"({assessment['severity_score']}/5)  |  Priority: {assessment['priority_tier']}\n"
        f"Reserve margin: {assessment['reserve_margin_pct']}%  |  "
        f"Load factor: {assessment['load_factor_pct']}%\n\n"
        f"{assessment['risk_summary']}",
        title="[bold]📊 Risk Assessment[/]",
        border_style=sev_color,
    ))

    # ── Mitigation plan ────────────────────────────────────────────────────────
    console.print(f"\n[bold]🛠️  Mitigation Plan[/] ({plan['step_count']} steps)")
    for s in plan["steps"]:
        console.print(f"  [{s.get('step','?')}] {s['action']}")
        console.print(f"      [dim]👤 {s.get('responsible','?')} | ⏱ {s.get('timeframe','?')}[/]")

    # ── Work order ─────────────────────────────────────────────────────────────
    console.print(Panel(
        f"Number: [bold]{work_order['work_order_number']}[/]  |  "
        f"Status: [yellow]{work_order['status']}[/]\n"
        f"Priority: {work_order['priority_tier']}  |  "
        f"Response: {work_order['required_response_time']}\n\n"
        f"{work_order['work_description']}",
        title="[bold]📋 Work Order Draft[/]",
        border_style="yellow",
    ))

    # ── HITL Gate ──────────────────────────────────────────────────────────────
    console.print(Panel(
        f"[bold yellow]⚠️  HUMAN APPROVAL REQUIRED[/]\n\n"
        f"Token: [dim]{approval['approval_token']}[/]\n\n"
        f"{approval['summary_for_approver']}\n\n"
        f"[dim]{approval['instruction']}[/]",
        title="[bold]🔐 Human Approval Gate[/]",
        border_style="yellow",
    ))

    if args.approve:
        console.print("\n[dim]--approve flag set: auto-approving for demo…[/]")
        resolve_approval(
            token=approval["approval_token"],
            decision="APPROVED",
            approver="CLI-Demo-Operator",
            rationale="Auto-approved via --approve flag for demonstration.",
        )
        from gridguard.tools.audit import record_audit_event
        record_audit_event(
            action="APPROVED",
            actor="OPERATOR:CLI-Demo-Operator",
            event_type=event["event_type"],
            event_id=event["event_id"],
            work_order_number=work_order["work_order_number"],
            outcome=f"Work order {work_order['work_order_number']} APPROVED via CLI demo.",
            details={"token": approval["approval_token"]},
        )
        console.print("[green]✅ Work order APPROVED. Audit record written.[/]")
    else:
        console.print(
            "\n[dim]Tip: run with [bold]--approve[/bold] to auto-approve the work order "
            "for a self-contained demo, or use the Streamlit dashboard.[/]"
        )

    console.rule()
    console.print(f"[dim]Audit log: data/audit_log.jsonl[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
