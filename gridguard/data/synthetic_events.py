"""
Synthetic grid-risk event generator.

These events are entirely fabricated for demonstration purposes.
They do not represent any real grid, operator, or infrastructure state.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Literal

# ── Canonical event schema ────────────────────────────────────────────────────

EventType = Literal["SEVERE_WEATHER", "HIGH_DEMAND", "EQUIPMENT_RISK", "OUTAGE_WARNING"]

REGIONS = ["ISNE", "PJM-EAST", "MISO-CENTRAL", "ERCOT-NORTH", "CAISO-SOUTH"]

# ── Pre-built scenario catalogue ──────────────────────────────────────────────

_SCENARIOS: dict[str, dict[str, Any]] = {
    "SEVERE_WEATHER": {
        "event_type": "SEVERE_WEATHER",
        "title": "Arctic Ice Storm & Generation Constraint Stress Condition",
        "description": (
            "SYNTHETIC DEMO STRESS SCENARIO: NWS has issued an Extreme Winter Ice Storm Warning "
            "with freezing rain and sub-zero wind chills (-36°F temperature anomaly driving +14% heating surge). "
            "Heavy ice accumulation has tripped 345 kV corridor line LINE-N12, and water intake icing has "
            "derated regional thermal generation by 4,500 MW, reducing available capacity to 24,000 MW. "
            "Operating contingency reserves have dropped to 650 MW (below the 700 MW emergency threshold)."
        ),
        "region": "ISNE",
        "severity_hint": 4,
        "demand_mw": 23_100,
        "capacity_mw": 24_000,
        "contingency_reserve_mw": 650,
        "weather": {
            "condition": "EXTREME_ICE_STORM",
            "temperature_f": 14,
            "wind_mph": 42,
            "ice_accumulation_in": 1.1,
            "temperature_delta_f": -36.0,
            "demand_shock_pct": 14.0,
            "capacity_derate_mw": 4_500,
        },
        "affected_assets": ["TX-N-447", "LINE-N12", "SS-BURLINGTON-3"],
        "source": "SYNTHETIC_DEMO",
    },
    "HIGH_DEMAND": {
        "event_type": "HIGH_DEMAND",
        "title": "Load Approaching N-1 Contingency Threshold",
        "description": (
            "Current demand is tracking 96.4 % of installed capacity. "
            "N-1 contingency margin has dropped below the 1,000 MW mandatory "
            "floor. Heat advisory is in effect until 21:00 local. "
            "Industrial curtailment contracts have not been activated."
        ),
        "region": "PJM-EAST",
        "severity_hint": 3,
        "demand_mw": 34_100,
        "capacity_mw": 35_400,
        "contingency_reserve_mw": 820,
        "weather": {
            "condition": "HEAT_ADVISORY",
            "temperature_f": 97,
            "wind_mph": 5,
            "ice_accumulation_in": 0.0,
        },
        "affected_assets": ["GEN-PEAKER-7", "GEN-PEAKER-11"],
        "source": "SYNTHETIC_DEMO",
    },
    "EQUIPMENT_RISK": {
        "event_type": "EQUIPMENT_RISK",
        "title": "Transformer Health Index Below Operational Threshold",
        "description": (
            "Dissolved-gas analysis (DGA) on unit TX-W-229 shows elevated "
            "acetylene (48 ppm) and hydrogen (310 ppm). Health Index score "
            "has declined from 0.72 to 0.58 over the past 30 days. "
            "Unit is energised on a 345 kV interconnect serving 280,000 customers."
        ),
        "region": "MISO-CENTRAL",
        "severity_hint": 3,
        "demand_mw": 18_700,
        "capacity_mw": 22_000,
        "contingency_reserve_mw": 2_100,
        "weather": {
            "condition": "CLEAR",
            "temperature_f": 68,
            "wind_mph": 12,
            "ice_accumulation_in": 0.0,
        },
        "affected_assets": ["TX-W-229"],
        "source": "SYNTHETIC_DEMO",
    },
    "OUTAGE_WARNING": {
        "event_type": "OUTAGE_WARNING",
        "title": "Scheduled Maintenance Conflict — Reliability Risk Detected",
        "description": (
            "Outage coordinator flagged a scheduling conflict: "
            "LINE-S-88 (230 kV) is planned out for conductor repair at 06:00, "
            "but DMS shows SS-AMARILLO-1 protection relay is also in bypass "
            "for calibration. Simultaneous outages would violate N-1 policy "
            "on the southern radial feed."
        ),
        "region": "ERCOT-NORTH",
        "severity_hint": 2,
        "demand_mw": 9_400,
        "capacity_mw": 14_200,
        "contingency_reserve_mw": 3_500,
        "weather": {
            "condition": "PARTLY_CLOUDY",
            "temperature_f": 74,
            "wind_mph": 9,
            "ice_accumulation_in": 0.0,
        },
        "affected_assets": ["LINE-S-88", "SS-AMARILLO-1"],
        "source": "SYNTHETIC_DEMO",
    },
}


def get_scenario_names() -> list[str]:
    """Return the list of available scenario keys."""
    return list(_SCENARIOS.keys())


def build_event(event_type: EventType, *, randomise: bool = False) -> dict[str, Any]:
    """
    Return a canonical grid-risk event dict for *event_type*.

    Parameters
    ----------
    event_type:
        One of the four supported event types.
    randomise:
        If True, jitter numeric fields slightly so repeated runs look
        distinct without changing the risk profile.
    """
    base = dict(_SCENARIOS[event_type])
    base["event_id"] = f"EVT-{event_type[:3]}-{random.randint(10000, 99999)}"
    base["timestamp"] = datetime.now(tz=timezone.utc).isoformat()

    if randomise:
        jitter = random.uniform(0.97, 1.03)
        base["demand_mw"] = round(base["demand_mw"] * jitter)
        base["contingency_reserve_mw"] = round(
            base["contingency_reserve_mw"] * random.uniform(0.90, 1.10)
        )

    return base
