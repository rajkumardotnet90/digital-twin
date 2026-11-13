"""Parity tests: the extracted twin must reproduce the notebook's saved outputs."""

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def test_forecast_matches_notebook(twin_lasso):
    expected = pd.read_csv(FIXTURES / "aqi_forecasts.csv", parse_dates=["timestamp"])
    actual = pd.concat([twin_lasso.forecast_zone(z, periods=6) for z in twin_lasso.zones], ignore_index=True)
    assert len(actual) == len(expected)
    np.testing.assert_allclose(actual["predicted_aqi"], expected["predicted_aqi"], rtol=1e-9, atol=1e-9)
    assert (actual["timestamp"].values == expected["timestamp"].values).all()


def test_policy_simulation_matches_notebook(twin_lasso):
    expected = pd.read_csv(FIXTURES / "policy_simulation_results.csv")
    for _, row in expected.iterrows():
        mods = ast.literal_eval(row["modifications"])
        result = twin_lasso.simulate_scenario(int(row["zone_id"]), mods)
        np.testing.assert_allclose(result["baseline_aqi"], row["baseline_aqi"], rtol=1e-9)
        np.testing.assert_allclose(result["simulated_aqi"], row["simulated_aqi"], rtol=1e-9)


def test_traffic_scenarios_match_notebook(twin_enet):
    # Values printed by the notebook's ElasticNet traffic scenario (rounded to 2 decimals).
    expected = pd.read_csv(FIXTURES / "traffic_elasticnet_notebook.csv").set_index("zone_id")
    for zone_id, row in expected.iterrows():
        for change, aqi in row.items():
            result = twin_enet.simulate_scenario(int(zone_id), {"avg_traffic_volume": f"{change}%"})
            assert result["simulated_aqi"] == pytest.approx(aqi, abs=0.006)
