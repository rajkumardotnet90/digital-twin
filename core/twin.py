"""Port of the notebook's ``AQIDigitalTwin`` so it can be imported, tested and reused.

Behaviour matches ``05_digital_twin_deployment.ipynb``:
* ``simulate_scenario`` applies "%" strings as relative changes and anything else as
  an absolute value, on the zone's base row.
* ``forecast_zone`` holds every feature constant except month / year / quarter and the
  cyclical month encodings.
Differences: forecasting is vectorised (one model call per forecast) and ``predict``
falls back to historical medians if a column is entirely missing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd


class AQIDigitalTwin:
    """Predict, simulate what-if scenarios and forecast AQI per zone."""

    def __init__(self, model: Any, scaler: Any, features: list[str], historical_data: pd.DataFrame):
        self.model = model
        self.scaler = scaler
        self.features = list(features)
        self.historical = historical_data.copy()
        self.zones = sorted(historical_data["zone_id"].unique())
        self._global_median = self.historical[self.features].median()

    # ------------------------------------------------------------------ prediction
    def predict(self, input_data: pd.DataFrame) -> np.ndarray:
        """Predict AQI for rows that contain all model features."""
        X = input_data[self.features].copy()
        X = X.replace([np.inf, -np.inf], np.nan)
        X = X.fillna(X.median()).fillna(self._global_median)
        X_scaled = pd.DataFrame(self.scaler.transform(X), columns=self.features)
        return self.model.predict(X_scaled)

    # ------------------------------------------------------------------ helpers
    def zone_data(self, zone_id: int) -> pd.DataFrame:
        return self.historical[self.historical["zone_id"] == zone_id].sort_values("timestamp")

    def base_row(self, zone_id: int, base_timestamp: pd.Timestamp | None = None) -> pd.DataFrame:
        """Row used as the starting state: the requested month, else the latest."""
        data = self.zone_data(zone_id)
        if base_timestamp is not None:
            match = data[data["timestamp"] == pd.Timestamp(base_timestamp)]
            if len(match) > 0:
                return match.iloc[[-1]]
        return data.iloc[[-1]]

    @staticmethod
    def apply_modifications(row: pd.DataFrame, modifications: Mapping[str, Any]) -> pd.DataFrame:
        """Return a copy of ``row`` with modifications applied ("-10%" = relative, number = absolute)."""
        modified = row.copy()
        for feature, value in modifications.items():
            if feature not in modified.columns:
                continue
            if isinstance(value, str) and value.endswith("%"):
                pct = float(value.rstrip("%")) / 100
                modified[feature] = modified[feature] * (1 + pct)
            else:
                modified[feature] = value
        return modified

    # ------------------------------------------------------------------ scenarios
    def simulate_scenario(
        self,
        zone_id: int,
        modifications: Mapping[str, Any],
        base_timestamp: pd.Timestamp | None = None,
    ) -> dict[str, Any]:
        """What-if on a single month: baseline vs modified prediction for one zone."""
        base_row = self.base_row(zone_id, base_timestamp)
        baseline_aqi = self.predict(base_row)[0]
        simulated_aqi = self.predict(self.apply_modifications(base_row, modifications))[0]
        return {
            "zone_id": zone_id,
            "baseline_aqi": baseline_aqi,
            "simulated_aqi": simulated_aqi,
            "aqi_change": simulated_aqi - baseline_aqi,
            "pct_change": ((simulated_aqi - baseline_aqi) / baseline_aqi * 100) if baseline_aqi != 0 else 0,
            "modifications": dict(modifications),
        }

    def forecast_zone(
        self,
        zone_id: int,
        periods: int = 6,
        modifications: Mapping[str, Any] | None = None,
        base_timestamp: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Forecast ``periods`` months ahead, optionally under modified drivers."""
        row = self.base_row(zone_id, base_timestamp)
        if modifications:
            row = self.apply_modifications(row, modifications)
        last_timestamp = row["timestamp"].iloc[0]
        timestamps = pd.DatetimeIndex([last_timestamp + pd.DateOffset(months=i) for i in range(1, periods + 1)])

        rows = pd.concat([row] * periods, ignore_index=True)
        rows["timestamp"] = timestamps
        rows["month"] = timestamps.month
        rows["year"] = timestamps.year
        rows["quarter"] = timestamps.quarter
        rows["month_sin"] = np.sin(2 * np.pi * timestamps.month / 12)
        rows["month_cos"] = np.cos(2 * np.pi * timestamps.month / 12)

        return pd.DataFrame({"timestamp": timestamps, "predicted_aqi": self.predict(rows), "zone_id": zone_id})

    def zone_comparison(self) -> pd.DataFrame:
        """Observed vs predicted AQI for every zone at its latest month."""
        latest = self.historical.sort_values("timestamp").groupby("zone_id").tail(1)
        comparison = latest[["zone_id", "timestamp", "AQI"]].copy()
        comparison["Predicted_AQI"] = self.predict(latest)
        return comparison.sort_values("zone_id")
