import numpy as np
import pandas as pd
import pytest

from core import config
from core.aqi import aqi_category, aqi_color
from core.simulation import Scenario, ScenarioValidationError, run_simulation, validate_scenario


def make(model="elasticnet", zones=(1, 2), horizon=6, changes=(), base=None):
    return Scenario(model, tuple(zones), horizon, tuple(changes), base)


def test_aqi_category_bands():
    assert aqi_category(25) == "Good"
    assert aqi_category(50) == "Good"
    assert aqi_category(51) == "Moderate"
    assert aqi_category(999) == "Hazardous"
    assert aqi_color(10) == config.AQI_BANDS[0][2]


def test_apply_modifications_relative_and_absolute(twin_enet):
    row = twin_enet.base_row(1)
    out = twin_enet.apply_modifications(row, {"avg_traffic_volume": "-50%", "pm10": 10, "not_a_column": "5%"})
    assert out["avg_traffic_volume"].iloc[0] == pytest.approx(row["avg_traffic_volume"].iloc[0] * 0.5)
    assert out["pm10"].iloc[0] == 10
    assert row["pm10"].iloc[0] != 10  # original untouched


def test_no_changes_means_no_delta(twin_enet):
    res = run_simulation(twin_enet, make())
    assert res.summary["aqi_change"].abs().max() < 1e-9
    assert res.forecast["aqi_change"].abs().max() < 1e-9
    assert not res.warnings


def test_traffic_reduction_lowers_aqi_with_elasticnet(twin_enet):
    res = run_simulation(twin_enet, make(zones=range(1, 11), changes=[("avg_traffic_volume", -30.0)]))
    assert res.headline()["aqi_change"] < 0
    assert len(res.forecast) == 10 * 6
    assert res.city_series().shape[0] == 6


def test_lasso_ignoring_traffic_triggers_warning(twin_lasso):
    res = run_simulation(twin_lasso, make("lasso_regression", changes=[("avg_traffic_volume", -30.0)]))
    assert any("no response" in w for w in res.warnings)


def test_outputs_are_clipped_to_valid_range(twin_enet):
    res = run_simulation(twin_enet, make(changes=[("avg_energy_consumption", 100.0)]))
    for frame in (res.summary, res.forecast):
        assert frame["scenario_aqi"].between(config.AQI_MIN, config.AQI_MAX).all()


def test_forecast_months_are_consecutive(twin_enet):
    res = run_simulation(twin_enet, make(zones=(3,), horizon=12))
    months = pd.DatetimeIndex(res.forecast["timestamp"])
    assert months[0] == pd.Timestamp("2024-07-01")
    assert (np.diff(months.month.values) % 12 == 1).all()


@pytest.mark.parametrize(
    "scenario, message",
    [
        (make(zones=()), "at least one zone"),
        (make(zones=(99,)), "Unknown zone"),
        (make(horizon=0), "horizon"),
        (make(horizon=config.MAX_HORIZON_MONTHS + 1), "horizon"),
        (make(model="nope"), "Unknown model"),
        (make(changes=[("avg_traffic_volume", -150.0)]), "between"),
        (make(changes=[("avg_traffic_volume", float("nan"))]), "finite"),
        (make(changes=[("secret_column", 10.0)]), "not an adjustable driver"),
        (make(base=pd.Timestamp("1999-01-01")), "base month"),
    ],
)
def test_validation_rejects_bad_input(twin_enet, scenario, message):
    with pytest.raises(ScenarioValidationError, match=message):
        validate_scenario(scenario, twin_enet)


def test_base_month_changes_starting_point(twin_enet):
    early = run_simulation(twin_enet, make(zones=(1,), base=pd.Timestamp("2022-01-01")))
    assert early.forecast["timestamp"].min() == pd.Timestamp("2022-02-01")
