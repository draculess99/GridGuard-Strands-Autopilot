"""
Tool: get_grid_snapshot

Returns the current simulated grid state for a given region.
All data is SYNTHETIC and does not reflect any real grid.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from strands import tool

from gridguard.logger import get_logger

log = get_logger(__name__)


@tool
def get_grid_snapshot(
    region: Annotated[str, "The grid region identifier, e.g. 'ISNE', 'PJM-EAST', 'MISO-CENTRAL'."],
    event_type: Annotated[str, "The event type driving this query, e.g. 'SEVERE_WEATHER'."],
) -> dict[str, Any]:
    """
    Retrieve the current operational snapshot for the specified grid region.

    Returns real-time (simulated) metrics including demand, capacity, reserve margin,
    and asset health indicators. This is SYNTHETIC data for demonstration purposes only.
    It does not reflect any real electric grid state.
    """
    log.info("get_grid_snapshot called", extra={"region": region, "event_type": event_type})

    # Synthetic snapshot values keyed by region
    _SNAPSHOTS: dict[str, dict[str, Any]] = {
        "ISNE": {
            "demand_mw": 24_800,
            "installed_capacity_mw": 28_500,
            "available_capacity_mw": 27_100,
            "contingency_reserve_mw": 1_200,
            "reserve_margin_pct": round((27_100 - 24_800) / 27_100 * 100, 1),
            "frequency_hz": 60.01,
            "interchange_mw": -320,  # net import
            "voltage_profile": "NORMAL",
            "alert_level": "WATCH",
        },
        "PJM-EAST": {
            "demand_mw": 34_100,
            "installed_capacity_mw": 35_400,
            "available_capacity_mw": 35_200,
            "contingency_reserve_mw": 820,
            "reserve_margin_pct": round((35_200 - 34_100) / 35_200 * 100, 1),
            "frequency_hz": 59.98,
            "interchange_mw": 140,  # net export
            "voltage_profile": "MARGINAL",
            "alert_level": "ALERT",
        },
        "MISO-CENTRAL": {
            "demand_mw": 18_700,
            "installed_capacity_mw": 22_000,
            "available_capacity_mw": 21_800,
            "contingency_reserve_mw": 2_100,
            "reserve_margin_pct": round((21_800 - 18_700) / 21_800 * 100, 1),
            "frequency_hz": 60.00,
            "interchange_mw": 0,
            "voltage_profile": "NORMAL",
            "alert_level": "ADVISORY",
        },
        "ERCOT-NORTH": {
            "demand_mw": 9_400,
            "installed_capacity_mw": 14_200,
            "available_capacity_mw": 13_900,
            "contingency_reserve_mw": 3_500,
            "reserve_margin_pct": round((13_900 - 9_400) / 13_900 * 100, 1),
            "frequency_hz": 60.00,
            "interchange_mw": 0,
            "voltage_profile": "NORMAL",
            "alert_level": "NORMAL",
        },
        "CAISO-SOUTH": {
            "demand_mw": 22_400,
            "installed_capacity_mw": 28_000,
            "available_capacity_mw": 27_200,
            "contingency_reserve_mw": 2_800,
            "reserve_margin_pct": round((27_200 - 22_400) / 27_200 * 100, 1),
            "frequency_hz": 60.01,
            "interchange_mw": 450,
            "voltage_profile": "NORMAL",
            "alert_level": "NORMAL",
        },
    }

    snapshot = _SNAPSHOTS.get(
        region,
        {
            "demand_mw": 15_000,
            "installed_capacity_mw": 18_000,
            "available_capacity_mw": 17_500,
            "contingency_reserve_mw": 1_500,
            "reserve_margin_pct": 14.3,
            "frequency_hz": 60.00,
            "interchange_mw": 0,
            "voltage_profile": "NORMAL",
            "alert_level": "NORMAL",
        },
    )

    # Documented synthetic SEVERE_WEATHER stress condition:
    # Heavy icing forces a 4,500 MW generation derate and compresses contingency reserves below 700 MW
    if event_type == "SEVERE_WEATHER":
        if region == "ISNE":
            snapshot = {
                "demand_mw": 23_100,
                "installed_capacity_mw": 28_500,
                "available_capacity_mw": 24_000,
                "contingency_reserve_mw": 650,
                "reserve_margin_pct": round((24_000 - 23_100) / 24_000 * 100, 1),
                "frequency_hz": 59.95,
                "interchange_mw": -1_500,
                "voltage_profile": "DEGRADED",
                "alert_level": "EMERGENCY_WATCH",
                "storm_stress_condition": (
                    "SYNTHETIC DEMO STRESS SCENARIO: 4,500 MW thermal generation derated "
                    "from intake icing; LINE-N12 tripped by heavy ice accretion."
                ),
            }
        else:
            base_cap = float(snapshot.get("available_capacity_mw", 25_000))
            derated_cap = round(base_cap * 0.85)
            snapshot = dict(snapshot)
            snapshot["available_capacity_mw"] = derated_cap
            snapshot["contingency_reserve_mw"] = 650
            snapshot["reserve_margin_pct"] = round(
                (derated_cap - float(snapshot["demand_mw"])) / derated_cap * 100, 1
            )
            snapshot["alert_level"] = "EMERGENCY_WATCH"

    result = {
        "region": region,
        "event_type": event_type,
        "as_of": datetime.now(tz=timezone.utc).isoformat(),
        "data_source": "SYNTHETIC_DEMO",
        "safety_notice": (
            "This snapshot is entirely simulated and does not reflect any real grid."
        ),
        **snapshot,
    }

    log.info("get_grid_snapshot returned", extra={"region": region, "alert_level": result["alert_level"]})
    return result
