"""
Tool: forecast_demand_xgboost

Runs a deterministic, local 24-hour demand forecast using an XGBoost regressor
trained on the verified GridGuard synthetic demand benchmark.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
from strands import tool

from gridguard.logger import get_logger

log = get_logger(__name__)

# ── Model Artifact Paths & Constants ──────────────────────────────────────────

DEFAULT_MODEL_PATH = Path(__file__).parent.parent / "models" / "xgboost_demand_model.json"

FEATURE_COLUMNS = [
    "lag_1",
    "lag_2",
    "lag_24",
    "lag_48",
    "lag_168",
    "rolling_mean_24",
    "rolling_std_24",
    "rolling_mean_168",
    "hour",
    "dayofweek",
    "month",
    "is_weekend",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "temperature_f",
    "temperature_sq",
    "is_holiday",
]


class ModelLoadError(RuntimeError):
    """Raised when the XGBoost model artifact cannot be found or loaded."""


# ── Feature Engineering Pipeline (Verified GridGuard_AI) ──────────────────────

def add_time_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add cyclical and calendar features to the dataframe."""
    result = frame.copy()
    timestamp = pd.to_datetime(result["timestamp"], utc=True)
    result["hour"] = timestamp.dt.hour
    result["dayofweek"] = timestamp.dt.dayofweek
    result["month"] = timestamp.dt.month
    result["is_weekend"] = (result["dayofweek"] >= 5).astype(int)
    result["hour_sin"] = np.sin(2 * np.pi * result["hour"] / 24)
    result["hour_cos"] = np.cos(2 * np.pi * result["hour"] / 24)
    result["dow_sin"] = np.sin(2 * np.pi * result["dayofweek"] / 7)
    result["dow_cos"] = np.cos(2 * np.pi * result["dayofweek"] / 7)
    result["temperature_sq"] = result["temperature_f"] ** 2
    return result


def build_training_frame(history: pd.DataFrame) -> pd.DataFrame:
    """Construct the 19 feature columns from raw hourly demand history."""
    frame = history.sort_values("timestamp").copy()
    demand = frame["demand_mw"]
    for lag in (1, 2, 24, 48, 168):
        frame[f"lag_{lag}"] = demand.shift(lag)
    frame["rolling_mean_24"] = demand.shift(1).rolling(24).mean()
    frame["rolling_std_24"] = demand.shift(1).rolling(24).std()
    frame["rolling_mean_168"] = demand.shift(1).rolling(168).mean()
    frame = add_time_features(frame)
    return frame.dropna(subset=FEATURE_COLUMNS + ["demand_mw"]).reset_index(drop=True)


def next_feature_row(
    history: pd.DataFrame,
    timestamp: pd.Timestamp,
    temperature_f: float,
    is_holiday: int = 0,
) -> pd.DataFrame:
    """Extract a single feature vector for recursive forecasting."""
    values = history["demand_mw"].astype(float).tolist()
    if len(values) < 168:
        raise ValueError(f"At least 168 hourly demand values required, got {len(values)}.")

    row = {
        "timestamp": pd.Timestamp(timestamp),
        "temperature_f": float(temperature_f),
        "is_holiday": int(is_holiday),
        "lag_1": values[-1],
        "lag_2": values[-2],
        "lag_24": values[-24],
        "lag_48": values[-48],
        "lag_168": values[-168],
        "rolling_mean_24": float(np.mean(values[-24:])),
        "rolling_std_24": float(np.std(values[-24:], ddof=1)),
        "rolling_mean_168": float(np.mean(values[-168:])),
    }
    return add_time_features(pd.DataFrame([row]))[FEATURE_COLUMNS]


# ── Synthetic Training Data Generator (Verified GridGuard_AI) ─────────────────

def generate_synthetic_demand_history(days: int = 90, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic hourly demand history using the verified GridGuard_AI generator.
    Produces realistic cyclical demand, temperature seasonality, and stress periods.
    """
    rng = np.random.default_rng(seed)
    periods = days * 24
    end = pd.Timestamp.now(tz="UTC").floor("h")
    timestamp = pd.date_range(end=end, periods=periods, freq="h")
    hour = timestamp.hour.to_numpy()
    dow = timestamp.dayofweek.to_numpy()
    day_index = np.arange(periods) / 24.0

    seasonal_temp = 62 + 18 * np.sin(2 * np.pi * (timestamp.dayofyear.to_numpy() - 172) / 365.25)
    daily_temp = 7 * np.sin(2 * np.pi * (hour - 14) / 24)
    temperature = seasonal_temp + daily_temp + rng.normal(0, 2.2, periods)

    morning = 1700 * np.exp(-((hour - 8) / 3.2) ** 2)
    evening = 2800 * np.exp(-((hour - 18) / 4.2) ** 2)
    overnight = -1300 * np.exp(-((hour - 3) / 3.5) ** 2)
    weekend = np.where(dow >= 5, -1200, 0)
    temp_effect = 28 * np.maximum(temperature - 72, 0) ** 1.35 + 19 * np.maximum(45 - temperature, 0) ** 1.25
    slow_trend = day_index * 3.0
    stress = np.zeros(periods)
    for _ in range(max(2, days // 30)):
        start = int(rng.integers(168, max(169, periods - 36)))
        width = int(rng.integers(8, 30))
        stress[start : min(periods, start + width)] += rng.uniform(900, 2400)

    demand = (
        14500
        + morning
        + evening
        + overnight
        + weekend
        + temp_effect
        + slow_trend
        + stress
        + rng.normal(0, 320, periods)
    )
    demand = np.maximum(demand, 7000)

    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "demand_mw": demand,
            "temperature_f": temperature,
            "is_holiday": 0,
            "source": "synthetic",
        }
    )


def train_and_save_model(output_path: Path | None = None, days: int = 90, seed: int = 42) -> Path:
    """
    Train an XGBoost demand regressor using the verified GridGuard_AI pipeline
    and save it as a JSON model artifact.
    """
    from xgboost import XGBRegressor

    target_path = Path(output_path or DEFAULT_MODEL_PATH)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("Training XGBoost demand model using verified GridGuard pipeline", extra={"days": days, "seed": seed})
    history = generate_synthetic_demand_history(days=days, seed=seed)
    training = build_training_frame(history)

    model = XGBRegressor(
        n_estimators=180,
        max_depth=5,
        learning_rate=0.04,
        subsample=0.9,
        colsample_bytree=0.9,
        min_child_weight=3,
        reg_alpha=0.05,
        reg_lambda=1.2,
        objective="reg:squarederror",
        eval_metric="mae",
        random_state=seed,
        n_jobs=2,
        tree_method="hist",
    )
    model.fit(training[FEATURE_COLUMNS], training["demand_mw"])
    model.save_model(str(target_path))
    log.info("XGBoost demand model successfully saved", extra={"path": str(target_path)})
    return target_path


def load_xgboost_model(model_path: Path | str | None = None) -> Any:
    """
    Load the XGBoost model from the specified or default path.
    Raises ModelLoadError if the artifact is missing or fails to load.
    """
    from xgboost import XGBRegressor

    path = Path(model_path or DEFAULT_MODEL_PATH)
    if not path.exists():
        raise ModelLoadError(
            f"XGBoost demand forecast model artifact not found at '{path}'. "
            "To generate the model artifact using the verified pipeline, run: "
            "python -m gridguard.tools.forecast --train"
        )
    try:
        model = XGBRegressor()
        model.load_model(str(path))
        return model
    except Exception as exc:
        raise ModelLoadError(
            f"Failed to load XGBoost model from '{path}': {exc}. "
            "Ensure the model artifact is a valid XGBoost JSON model."
        ) from exc


# ── Strands Tool: forecast_demand_xgboost ─────────────────────────────────────

@tool
def forecast_demand_xgboost(
    region: Annotated[str, "Grid region identifier (e.g. ISNE, PJM-EAST)."],
    available_capacity_mw: Annotated[float, "Current available generation capacity in megawatts."],
    horizon_hours: Annotated[int, "Forecast horizon in hours (default 24)."] = 24,
    temperature_delta_f: Annotated[float, "Temperature anomaly in degrees F from weather event."] = 0.0,
    demand_shock_pct: Annotated[float, "Anticipated demand shock percentage (e.g. 5.0 for heatwave)."] = 0.0,
    model_path: Annotated[str | None, "Optional custom path to the serialized XGBoost model."] = None,
) -> dict[str, Any]:
    """
    Generate a 24-hour deterministic demand forecast using a trained XGBoost regressor.

    Recursively forecasts hourly demand, computes projected peak demand, reserve margin,
    and identifies high-risk hours where forecasted load approaches or exceeds generation capacity.
    Operates entirely on synthetic demonstration data.
    """
    log.info("forecast_demand_xgboost called", extra={"region": region, "horizon": horizon_hours})

    # Load model (strictly enforces artifact availability; fails with actionable error if missing)
    model = load_xgboost_model(model_path)

    # Use verified deterministic baseline history for the recursive forecast
    base_history = generate_synthetic_demand_history(days=14, seed=42)
    last_timestamp = pd.Timestamp(base_history["timestamp"].max())
    recent_temp = base_history["temperature_f"].tail(168)

    working_history = base_history[["timestamp", "demand_mw", "temperature_f", "is_holiday"]].copy()
    hourly_records: list[dict[str, Any]] = []

    # Region scaling factors to match simulated regional capacity
    region_multipliers: dict[str, float] = {
        "ISNE": 1.15,
        "PJM-EAST": 1.45,
        "MISO-CENTRAL": 1.0,
        "MISO-C": 1.0,
        "ERCOT-NORTH": 0.55,
        "CAISO-SOUTH": 1.10,
        "NYISO-J": 0.85,
    }
    multiplier = region_multipliers.get(region, 1.0)

    for step in range(1, horizon_hours + 1):
        step_timestamp = last_timestamp + pd.Timedelta(hours=step)
        seasonal_temp = float(recent_temp.iloc[(step - 1) % len(recent_temp)] + temperature_delta_f)
        features = next_feature_row(working_history, timestamp=step_timestamp, temperature_f=seasonal_temp)

        pred_val = float(model.predict(features)[0])
        pred_val *= multiplier
        pred_val *= 1 + demand_shock_pct / 100.0
        pred_val = max(pred_val, 5000.0)

        utilization = (pred_val / available_capacity_mw * 100.0) if available_capacity_mw > 0 else 0.0

        hourly_records.append(
            {
                "hour": step,
                "timestamp": step_timestamp.isoformat(),
                "forecast_mw": round(pred_val, 1),
                "temperature_f": round(seasonal_temp, 1),
                "utilization_pct": round(utilization, 1),
                "high_risk": utilization >= 92.0,
            }
        )

        # Append to working history for autoregressive lag features
        working_history = pd.concat(
            [
                working_history,
                pd.DataFrame(
                    [
                        {
                            "timestamp": step_timestamp,
                            "demand_mw": pred_val,
                            "temperature_f": seasonal_temp,
                            "is_holiday": 0,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    forecast_values = [r["forecast_mw"] for r in hourly_records]
    peak_demand = max(forecast_values)
    mean_demand = float(np.mean(forecast_values))
    reserve_margin_mw = available_capacity_mw - peak_demand
    reserve_margin_pct = (
        round((available_capacity_mw - peak_demand) / peak_demand * 100.0, 1)
        if peak_demand > 0
        else 0.0
    )
    high_risk_hours = sum(1 for r in hourly_records if r["high_risk"])

    # Determine forecast risk category (matching verified GridGuard risk thresholds)
    if reserve_margin_pct < 0 or high_risk_hours >= 4:
        forecast_risk_level = "CRITICAL"
        headline = "Forecast demand severely challenges available generation capacity."
        recommendation = "Escalate to lead operator immediately. Dispatch peaker units and initiate demand-response protocol."
    elif reserve_margin_pct < 5 or high_risk_hours >= 2:
        forecast_risk_level = "ELEVATED"
        headline = "Thin reserve margin projected during upcoming peak hours."
        recommendation = "Alert standby generation units and stage voluntary load-reduction measures."
    elif reserve_margin_pct < 12 or high_risk_hours >= 1:
        forecast_risk_level = "WATCH"
        headline = "Upcoming peak load approaching contingency threshold."
        recommendation = "Maintain enhanced monitoring and prepare contingency reserves."
    else:
        forecast_risk_level = "NORMAL"
        headline = "Forecast demand remains comfortably within operating reserve margins."
        recommendation = "Continue standard dispatch schedules and periodic re-forecasting."

    result: dict[str, Any] = {
        "region": region,
        "forecast_horizon_hours": horizon_hours,
        "predicted_peak_mw": round(peak_demand, 1),
        "predicted_mean_mw": round(mean_demand, 1),
        "available_capacity_mw": round(available_capacity_mw, 1),
        "reserve_margin_mw": round(reserve_margin_mw, 1),
        "reserve_margin_pct": reserve_margin_pct,
        "high_risk_hours": high_risk_hours,
        "forecast_risk_level": forecast_risk_level,
        "headline": headline,
        "recommendation": recommendation,
        "hourly_forecast": hourly_records,
        "model_metadata": {
            "model_name": "GridGuard XGBoost Demand Forecaster",
            "model_version": "gridguard-xgb-v1.0",
            "algorithm": "XGBRegressor(tree_method='hist', objective='reg:squarederror')",
            "feature_count": len(FEATURE_COLUMNS),
            "feature_columns": FEATURE_COLUMNS,
            "training_source": "Synthetic hourly energy consumption benchmark (GridGuard verified)",
            "artifact_path": str(Path(model_path or DEFAULT_MODEL_PATH).name),
        },
        "is_synthetic": True,
        "safety_notice": "SYNTHETIC DEMO FORECAST. Operates on simulated data only; does not connect to real electrical grid.",
        "limitations": "Point forecast based on synthetic feature distributions. Subject to weather model uncertainty.",
    }

    log.info(
        "forecast_demand_xgboost completed",
        extra={
            "peak_mw": peak_demand,
            "reserve_margin_pct": reserve_margin_pct,
            "risk_level": forecast_risk_level,
        },
    )
    return result


if __name__ == "__main__":
    import sys
    output = train_and_save_model()
    print(f"Model saved to: {output}")
