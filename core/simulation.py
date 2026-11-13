"""Scenario definition, validation and the simulation runner used by the UI."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config
from .aqi import aqi_category
from .twin import AQIDigitalTwin


class ScenarioValidationError(ValueError):
    """Raised with a user-friendly message when scenario inputs are invalid."""


@dataclass(frozen=True)
class Scenario:
    """Hashable description of one simulation run."""

    model_key: str
    zone_ids: tuple[int, ...]
    horizon: int
    changes: tuple[tuple[str, float], ...] = ()  # (feature, % change); zero changes omitted
    base_timestamp: pd.Timestamp | None = None

    def modifications(self) -> dict[str, str]:
        return {feature: f"{pct:g}%" for feature, pct in self.changes}


@dataclass
class SimulationResult:
    scenario: Scenario
    summary: pd.DataFrame  # one row per zone
    forecast: pd.DataFrame  # one row per zone x month
    warnings: list[str] = field(default_factory=list)

    def city_series(self, zone_id: int | None = None) -> pd.DataFrame:
        """Forecast per month: mean across the selected zones, or one zone if ``zone_id`` is given."""
        data = self.forecast if zone_id is None else self.forecast[self.forecast["zone_id"] == zone_id]
        return (
            data.groupby("timestamp", as_index=False)[["baseline_aqi", "scenario_aqi"]]
            .mean()
            .assign(aqi_change=lambda d: d["scenario_aqi"] - d["baseline_aqi"])
        )

    def yearly_summary(self, column: str = "scenario_aqi") -> pd.DataFrame:
        """Average forecast AQI per zone and calendar year (plus an all-zones row)."""
        data = self.forecast.assign(year=lambda d: d["timestamp"].dt.year)
        pivot = data.pivot_table(index="zone_name", columns="year", values=column, aggfunc="mean")
        pivot = pivot.reindex(data["zone_name"].unique())
        pivot.loc["All selected zones"] = pivot.mean()
        return pivot

    def headline(self) -> dict[str, float | str]:
        s = self.summary
        base, scen = s["baseline_aqi"].mean(), s["scenario_aqi"].mean()
        city = self.city_series()
        return {
            "baseline_aqi": base,
            "scenario_aqi": scen,
            "aqi_change": scen - base,
            "pct_change": (scen - base) / base * 100 if base else 0.0,
            "category": aqi_category(scen),
            "avg_forecast_baseline": city["baseline_aqi"].mean(),
            "avg_forecast_scenario": city["scenario_aqi"].mean(),
            "avg_forecast_change": city["aqi_change"].mean(),
        }


def validate_scenario(scenario: Scenario, twin: AQIDigitalTwin) -> None:
    """Raise ScenarioValidationError if the scenario cannot be run safely."""
    if scenario.model_key not in config.MODEL_REGISTRY:
        raise ScenarioValidationError(f"Unknown model '{scenario.model_key}'.")
    if not scenario.zone_ids:
        raise ScenarioValidationError("Select at least one zone.")
    unknown = [z for z in scenario.zone_ids if z not in twin.zones]
    if unknown:
        raise ScenarioValidationError(f"Unknown zone id(s): {unknown}. Valid zones: {list(twin.zones)}.")
    if not 1 <= scenario.horizon <= config.MAX_HORIZON_MONTHS:
        raise ScenarioValidationError(f"Forecast horizon must be between 1 and {config.MAX_HORIZON_MONTHS} months.")

    for feature, pct in scenario.changes:
        driver = config.DRIVERS_BY_FEATURE.get(feature)
        if driver is None or feature not in twin.historical.columns:
            raise ScenarioValidationError(f"'{feature}' is not an adjustable driver.")
        if not isinstance(pct, int | float) or not math.isfinite(pct):
            raise ScenarioValidationError(f"{driver.label}: value must be a finite number.")
        if not driver.min_pct <= pct <= driver.max_pct:
            raise ScenarioValidationError(
                f"{driver.label}: change must be between {driver.min_pct}% and {driver.max_pct}% (got {pct:g}%)."
            )

    if scenario.base_timestamp is not None:
        available = set(twin.historical["timestamp"])
        if pd.Timestamp(scenario.base_timestamp) not in available:
            raise ScenarioValidationError("The selected base month is not in the historical data.")


def history_series(twin: AQIDigitalTwin, zone_ids: tuple[int, ...] | list[int]) -> pd.DataFrame:
    """Observed AQI per month, averaged over the given zones."""
    data = twin.historical[twin.historical["zone_id"].isin(zone_ids)]
    return data.groupby("timestamp", as_index=False)["AQI"].mean()


def run_simulation(twin: AQIDigitalTwin, scenario: Scenario) -> SimulationResult:
    """Run baseline vs scenario for every selected zone (single-month what-if + forecast)."""
    validate_scenario(scenario, twin)
    mods = scenario.modifications()
    names = twin.historical.drop_duplicates("zone_id").set_index("zone_id")["zone_name"].to_dict()

    summary_rows, forecast_frames = [], []
    for zone in scenario.zone_ids:
        sim = twin.simulate_scenario(zone, mods, scenario.base_timestamp)
        base_row = twin.base_row(zone, scenario.base_timestamp)
        summary_rows.append(
            {
                "zone_id": zone,
                "zone_name": names.get(zone, f"Zone {zone}"),
                "base_month": base_row["timestamp"].iloc[0],
                "actual_aqi": float(base_row["AQI"].iloc[0]),
                "baseline_aqi": sim["baseline_aqi"],
                "scenario_aqi": sim["simulated_aqi"],
            }
        )
        baseline_fc = twin.forecast_zone(zone, scenario.horizon, base_timestamp=scenario.base_timestamp)
        scenario_fc = twin.forecast_zone(zone, scenario.horizon, mods, scenario.base_timestamp)
        forecast_frames.append(
            pd.DataFrame(
                {
                    "zone_id": zone,
                    "zone_name": names.get(zone, f"Zone {zone}"),
                    "timestamp": baseline_fc["timestamp"],
                    "baseline_aqi": baseline_fc["predicted_aqi"],
                    "scenario_aqi": scenario_fc["predicted_aqi"],
                }
            )
        )

    summary = pd.DataFrame(summary_rows)
    forecast = pd.concat(forecast_frames, ignore_index=True)
    warnings: list[str] = []

    clipped = 0
    for frame in (summary, forecast):
        for col in ("baseline_aqi", "scenario_aqi"):
            clipped += int((~frame[col].between(config.AQI_MIN, config.AQI_MAX)).sum())
            frame[col] = frame[col].clip(config.AQI_MIN, config.AQI_MAX)
    if clipped:
        warnings.append(
            f"{clipped} prediction(s) fell outside the valid AQI range "
            f"[{config.AQI_MIN:.0f}, {config.AQI_MAX:.0f}] and were clipped."
        )

    summary["aqi_change"] = summary["scenario_aqi"] - summary["baseline_aqi"]
    summary["pct_change"] = np.where(
        summary["baseline_aqi"] != 0, summary["aqi_change"] / summary["baseline_aqi"] * 100, 0.0
    )
    summary["category_baseline"] = summary["baseline_aqi"].map(aqi_category)
    summary["category_scenario"] = summary["scenario_aqi"].map(aqi_category)
    forecast["aqi_change"] = forecast["scenario_aqi"] - forecast["baseline_aqi"]

    label = config.MODEL_REGISTRY[scenario.model_key][0]
    if scenario.changes and forecast["aqi_change"].abs().max() < 1e-9 and summary["aqi_change"].abs().max() < 1e-9:
        warnings.append(
            f"{label} shows no response to the selected changes (its coefficients for those drivers are zero). "
            "Try ElasticNet, Ridge or Linear Regression."
        )
    elif summary["pct_change"].abs().max() > 50:
        warnings.append(
            "A change above 50% in at least one zone is unusually large and may be a model extrapolation "
            "artefact (common with tree-based models). Cross-check with a linear model."
        )

    return SimulationResult(scenario=scenario, summary=summary, forecast=forecast, warnings=warnings)
