"""Headless UI smoke tests using Streamlit's AppTest."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TIMEOUT = 120


@pytest.fixture
def app():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def metric(at, label):
    return next(m for m in at.metric if m.label == label)


def test_default_render(app):
    assert app.title[0].value.endswith("Digital Twin - Air Quality Index")
    assert len(app.metric) == 4
    assert float(metric(app, "Scenario AQI").value) == pytest.approx(float(metric(app, "Predicted AQI").value))
    assert not app.error


def test_traffic_slider_lowers_aqi_live(app):
    app.slider(key="chg_avg_traffic_volume").set_value(-50).run()
    assert not app.exception
    assert "-" in metric(app, "Scenario AQI").delta


def test_preset_fills_sliders(app):
    app.selectbox(key="preset").select("Combined Green Policy").run()
    assert app.slider(key="chg_avg_traffic_volume").value == -30
    assert app.slider(key="chg_total_vehicles_charged").value == 100


def test_reset_restores_defaults(app):
    app.slider(key="chg_avg_traffic_volume").set_value(-50).run()
    app.button(key="reset_btn").click().run()
    assert app.slider(key="chg_avg_traffic_volume").value == 0
    assert app.selectbox(key="model").value == "elasticnet"


def test_empty_zone_selection_shows_friendly_error(app):
    app.multiselect(key="zones").set_value([]).run()
    assert any("at least one zone" in e.value for e in app.error)
    assert not app.exception


def test_run_saves_run_for_comparison(app):
    app.slider(key="chg_avg_traffic_volume").set_value(-30).run()
    app.button(key="run_btn").click().run()
    assert len(app.session_state["runs"]) == 1
    assert not app.exception


def test_lasso_shows_insensitivity_warning(app):
    app.selectbox(key="model").select("lasso_regression").run()
    app.slider(key="chg_avg_traffic_volume").set_value(-30).run()
    assert any("no response" in w.value for w in app.warning)


def test_live_off_waits_for_run(app):
    app.toggle(key="live").set_value(False).run()
    app.slider(key="chg_avg_traffic_volume").set_value(-50).run()
    assert any("Click **Run Simulation**" in i.value for i in app.info)
    app.button(key="run_btn").click().run()
    assert not any("Click **Run Simulation**" in i.value for i in app.info)
