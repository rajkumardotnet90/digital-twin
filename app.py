"""Streamlit UI for the AQI Digital Twin.  Run with:  streamlit run app.py

All model/simulation logic lives in ``core/``; this file only handles widgets and layout.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import config
from core.loader import ArtifactError, load_history, load_metadata, load_model_metrics, load_twin
from core.simulation import (
    Scenario,
    ScenarioValidationError,
    SimulationResult,
    history_series,
    run_simulation,
    validate_scenario,
)
from ui import charts

st.set_page_config(page_title="Digital Twin - AQI", page_icon="🌫️", layout="wide")


# --------------------------------------------------------------------------- cached loaders
@st.cache_resource(show_spinner="Loading historical data...")
def get_history() -> pd.DataFrame:
    return load_history()


@st.cache_resource(show_spinner="Loading model...")
def get_twin(model_key: str):
    return load_twin(model_key, get_history())


@st.cache_data(show_spinner="Running simulation...")
def cached_run(
    model_key: str, zone_ids: tuple[int, ...], horizon: int, changes: tuple[tuple[str, float], ...], base_iso: str
) -> SimulationResult:
    scenario = Scenario(model_key, zone_ids, horizon, changes, pd.Timestamp(base_iso))
    return run_simulation(get_twin(model_key), scenario)


def execute(scenario: Scenario) -> SimulationResult:
    return cached_run(
        scenario.model_key,
        scenario.zone_ids,
        scenario.horizon,
        scenario.changes,
        pd.Timestamp(scenario.base_timestamp).isoformat(),
    )


# --------------------------------------------------------------------------- load artifacts
try:
    history = get_history()
    metadata = load_metadata()
    model_metrics = load_model_metrics()
except ArtifactError as exc:
    st.error(f"Could not load the model/data files. {exc}")
    st.stop()

zone_names: dict[int, str] = history.drop_duplicates("zone_id").set_index("zone_id")["zone_name"].to_dict()
ALL_ZONES = sorted(zone_names)
MONTHS = [pd.Timestamp(m) for m in sorted(history["timestamp"].unique())]
DEFAULT_MODEL = config.DEFAULT_MODEL if config.DEFAULT_MODEL in config.MODEL_REGISTRY else "elasticnet"

DEFAULTS: dict = {
    "model": DEFAULT_MODEL,
    "zones": ALL_ZONES,
    "horizon": min(config.DEFAULT_HORIZON_MONTHS, config.MAX_HORIZON_MONTHS),
    "base_month": MONTHS[-1],
    "preset": "Custom (manual)",
    "live": True,
    **{f"chg_{d.feature}": 0 for d in config.DRIVERS},
}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)
st.session_state.setdefault("runs", [])
st.session_state.setdefault("run_counter", 0)


# --------------------------------------------------------------------------- callbacks / helpers
def reset_defaults() -> None:
    for key, value in DEFAULTS.items():
        st.session_state[key] = value
    st.session_state.pop("applied", None)


def apply_preset() -> None:
    preset = config.POLICY_PRESETS[st.session_state["preset"]]
    if st.session_state["preset"] == "Custom (manual)":
        return
    for driver in config.DRIVERS:
        if driver.group == "policy":
            st.session_state[f"chg_{driver.feature}"] = int(preset.get(driver.feature, 0))


def pin_baseline(result: SimulationResult) -> None:
    st.session_state["baseline"] = {"name": "Pinned baseline", "result": result}


def clear_runs() -> None:
    st.session_state["runs"] = []


def scenario_from_state() -> Scenario:
    ss = st.session_state
    changes = tuple((d.feature, float(ss[f"chg_{d.feature}"])) for d in config.DRIVERS if ss[f"chg_{d.feature}"] != 0)
    return Scenario(
        ss["model"], tuple(sorted(ss["zones"])), int(ss["horizon"]), changes, pd.Timestamp(ss["base_month"])
    )


def describe_changes(changes: tuple[tuple[str, float], ...]) -> str:
    if not changes:
        return "none"
    return ", ".join(f"{config.DRIVERS_BY_FEATURE[f].label} {pct:+g}%" for f, pct in changes)


def describe_zones(zone_ids: tuple[int, ...]) -> str:
    return "All zones" if set(zone_ids) == set(ALL_ZONES) else ", ".join(zone_names[z] for z in zone_ids)


# --------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Simulation controls")
    run_clicked = st.button("▶ Run Simulation", type="primary", key="run_btn", width="stretch")
    reset_col, live_col = st.columns([1, 1.3], vertical_alignment="center")
    reset_col.button("↺ Reset", key="reset_btn", on_click=reset_defaults, width="stretch", help="Reset to defaults")
    live_col.toggle(
        "Live update",
        key="live",
        help="On: results refresh as you move controls. Off: they refresh only when you click Run Simulation. "
        "Run Simulation always saves the run so it can be compared.",
    )

    st.subheader("Scope")
    st.multiselect(
        "Zones",
        ALL_ZONES,
        key="zones",
        format_func=lambda z: f"{z} - {zone_names[z]}",
        help="Zones to simulate. Charts show the average across the selected zones.",
    )
    st.selectbox(
        "Prediction model",
        list(config.MODEL_REGISTRY),
        key="model",
        format_func=lambda k: config.MODEL_REGISTRY[k][0],
        help="Models respond differently to what-if changes. Lasso (best R²) ignores most drivers; "
        "ElasticNet is the notebook's choice for what-if analysis.",
    )
    st.slider(
        "Forecast horizon (months)",
        1,
        config.MAX_HORIZON_MONTHS,
        key="horizon",
        help="How many months ahead to forecast from the base month.",
    )
    st.select_slider(
        "Base month",
        options=MONTHS,
        key="base_month",
        format_func=lambda m: m.strftime("%b %Y"),
        help="Starting state for the simulation. Defaults to the latest observed month.",
    )
    forecast_end = pd.Timestamp(st.session_state["base_month"]) + pd.DateOffset(months=int(st.session_state["horizon"]))
    st.caption(f"Forecast runs through **{forecast_end:%b %Y}**.")

    st.subheader("Scenario drivers (% change)")
    st.selectbox(
        "Quick policy preset",
        list(config.POLICY_PRESETS),
        key="preset",
        on_change=apply_preset,
        help="Fills the sliders below with a policy from the notebook. You can fine-tune afterwards.",
    )
    for driver in (d for d in config.DRIVERS if d.group == "policy"):
        st.slider(
            driver.label,
            driver.min_pct,
            driver.max_pct,
            step=driver.step,
            key=f"chg_{driver.feature}",
            format="%d%%",
            help=driver.help,
        )
    with st.expander("Sensor overrides (% change)"):
        for driver in (d for d in config.DRIVERS if d.group == "sensor"):
            st.number_input(
                driver.label,
                min_value=driver.min_pct,
                max_value=driver.max_pct,
                step=driver.step,
                key=f"chg_{driver.feature}",
                help=driver.help,
            )

# --------------------------------------------------------------------------- build + validate scenario
current = scenario_from_state()
if st.session_state["live"] or run_clicked or "applied" not in st.session_state:
    st.session_state["applied"] = current
scenario: Scenario = st.session_state["applied"]

st.title("🌫️ Digital Twin - Air Quality Index")
st.caption("What-if simulation and forecasting for a smart city, powered by the trained AQI models.")

try:
    validate_scenario(scenario, get_twin(scenario.model_key))
    result = execute(scenario)
except ScenarioValidationError as exc:
    st.error(f"Invalid input: {exc}")
    st.stop()
except ArtifactError as exc:
    st.error(f"Model files are missing or unreadable: {exc}")
    st.stop()
except Exception as exc:  # last-resort guard so the demo never shows a raw traceback
    st.error("Something went wrong while running the simulation. Please adjust the inputs and try again.")
    with st.expander("Technical details"):
        st.exception(exc)
    st.stop()

twin = get_twin(scenario.model_key)

if "baseline" not in st.session_state:
    default_scenario = Scenario(DEFAULT_MODEL, tuple(ALL_ZONES), DEFAULTS["horizon"], (), MONTHS[-1])
    st.session_state["baseline"] = {"name": "Baseline (defaults)", "result": execute(default_scenario)}

if run_clicked:
    st.session_state["run_counter"] += 1
    runs = st.session_state["runs"]
    runs.append({"name": f"Run {st.session_state['run_counter']}", "result": result})
    st.session_state["runs"] = runs[-config.MAX_SAVED_RUNS :]
    st.toast(f"Saved as Run {st.session_state['run_counter']}")

if current != scenario:
    st.info("Controls changed. Click **Run Simulation** to update the results (Live update is off).")
for message in result.warnings:
    st.warning(message)

# --------------------------------------------------------------------------- headline metrics
headline = result.headline()
model_row = model_metrics[model_metrics["Model"] == config.MODEL_REGISTRY[scenario.model_key][2]].iloc[0]
metric_cols = st.columns(4)
metric_cols[0].metric(
    "Predicted AQI",
    f"{headline['baseline_aqi']:.1f}",
    help="Model prediction at the base month with no changes, averaged over the selected zones.",
)
metric_cols[1].metric(
    "Scenario AQI",
    f"{headline['scenario_aqi']:.1f}",
    f"{headline['aqi_change']:+.1f} ({headline['pct_change']:+.1f}%)",
    delta_color="inverse" if abs(headline["aqi_change"]) > 1e-9 else "off",
    help="Predicted AQI after applying the driver changes. Lower is better.",
)
metric_cols[2].metric(
    f"Avg forecast ({scenario.horizon} mo)",
    f"{headline['avg_forecast_scenario']:.1f}",
    f"{headline['avg_forecast_change']:+.1f} vs no change",
    delta_color="inverse" if abs(headline["avg_forecast_change"]) > 1e-9 else "off",
    help="Mean scenario forecast over the horizon.",
)
metric_cols[3].metric(
    "Model test R²",
    f"{model_row['Test_R2']:.4f}",
    f"RMSE {model_row['Test_RMSE']:.1f}",
    delta_color="off",
    help="Hold-out performance of the selected model from the modelling phase.",
)
badge_color = {"Good": "green", "Moderate": "yellow", "Unhealthy (Sensitive)": "orange", "Unhealthy": "red"}.get(
    str(headline["category"]), "violet"
)
st.markdown(f"Scenario AQI category: :{badge_color}-badge[{headline['category']}]")

tab_forecast, tab_zones, tab_compare, tab_results, tab_about = st.tabs(
    ["📈 Forecast", "🏙️ Zones", "🔀 Compare runs", "📋 Results & export", "ℹ️ About"]
)

# --------------------------------------------------------------------------- forecast tab
with tab_forecast:
    ctrl_cols = st.columns([3, 1], vertical_alignment="bottom")
    view_zone = ctrl_cols[0].selectbox(
        "Chart view",
        [None, *scenario.zone_ids],
        format_func=lambda z: "Average of selected zones" if z is None else f"{z} - {zone_names[z]}",
    )
    zoom = ctrl_cols[1].toggle(
        "Zoom to forecast", value=True, help="Fit the axes to the forecast so small scenario effects are visible."
    )
    zones_in_view = list(scenario.zone_ids) if view_zone is None else [view_zone]
    title = "AQI: observed history and forecast" + ("" if view_zone is None else f" - {zone_names[view_zone]}")
    st.plotly_chart(
        charts.forecast_chart(
            history_series(twin, zones_in_view),
            result.city_series(view_zone),
            scenario.base_timestamp,
            title,
            zoom_forecast=zoom,
        ),
        width="stretch",
    )
    st.caption(
        f"Scenario: **{describe_changes(scenario.changes)}** · Model: {config.MODEL_REGISTRY[scenario.model_key][0]} · "
        f"Zones: {describe_zones(scenario.zone_ids)}"
    )

# --------------------------------------------------------------------------- zones tab
with tab_zones:
    st.plotly_chart(charts.zone_bar_chart(result.summary), width="stretch")
    st.dataframe(
        result.summary[
            ["zone_id", "zone_name", "actual_aqi", "baseline_aqi", "scenario_aqi", "aqi_change", "pct_change"]
            + ["category_scenario"]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "zone_id": "Zone",
            "zone_name": "Name",
            "actual_aqi": st.column_config.NumberColumn("Observed AQI", format="%.1f"),
            "baseline_aqi": st.column_config.NumberColumn("No change", format="%.1f"),
            "scenario_aqi": st.column_config.NumberColumn("Scenario", format="%.1f"),
            "aqi_change": st.column_config.NumberColumn("Change", format="%+.1f"),
            "pct_change": st.column_config.NumberColumn("Change %", format="%+.1f%%"),
            "category_scenario": "Category",
        },
    )

# --------------------------------------------------------------------------- compare tab
with tab_compare:
    baseline_entry = st.session_state["baseline"]
    saved = st.session_state["runs"]
    st.write(
        "Click **Run Simulation** after each tweak to save a run, then overlay them against the pinned baseline. "
        "Each line is the average over that run's own zones and model."
    )
    action_cols = st.columns([1, 1, 3])
    action_cols[0].button(
        "📌 Pin current as baseline", on_click=pin_baseline, args=(result,), key="pin_btn", help="Replace the baseline"
    )
    action_cols[1].button("🗑 Clear saved runs", on_click=clear_runs, key="clear_btn", disabled=not saved)

    chosen = st.multiselect("Saved runs to overlay", [r["name"] for r in saved], default=[r["name"] for r in saved])
    entries = [(f"Baseline: {baseline_entry['name']}", baseline_entry["result"], True)]
    entries += [(r["name"], r["result"], False) for r in saved if r["name"] in chosen]
    entries.append(("Current (live)", result, False))

    show_history = st.toggle("Show observed history", value=False, help="Off fits the axes to the forecasts.")
    st.plotly_chart(
        charts.compare_chart(
            history_series(twin, scenario.zone_ids) if show_history else None,
            [(name, res.city_series(), base) for name, res, base in entries],
        ),
        width="stretch",
    )
    comparison = pd.DataFrame(
        [
            {
                "Run": name,
                "Model": config.MODEL_REGISTRY[res.scenario.model_key][0],
                "Zones": describe_zones(res.scenario.zone_ids),
                "Horizon (mo)": res.scenario.horizon,
                "Changes": describe_changes(res.scenario.changes),
                "Scenario AQI (base month)": res.headline()["scenario_aqi"],
                "Avg forecast AQI": res.headline()["avg_forecast_scenario"],
                "Avg change vs own no-change": res.headline()["avg_forecast_change"],
            }
            for name, res, _ in entries
        ]
    )
    st.dataframe(
        comparison,
        hide_index=True,
        width="stretch",
        column_config={
            "Scenario AQI (base month)": st.column_config.NumberColumn(format="%.1f"),
            "Avg forecast AQI": st.column_config.NumberColumn(format="%.1f"),
            "Avg change vs own no-change": st.column_config.NumberColumn(format="%+.1f"),
        },
    )

# --------------------------------------------------------------------------- results tab
with tab_results:
    st.subheader("Forecast by year (average AQI)")
    yearly = result.yearly_summary().round(1)
    yearly.columns = [str(c) for c in yearly.columns]
    st.dataframe(yearly, width="stretch")
    st.caption(
        "Years with fewer than 12 months of forecast are partial. Forecasts beyond about 12 months repeat the latest "
        "observed state, so treat long-range values (2026-2027) as indicative, not precise."
    )
    st.subheader("All predictions (zone x month)")
    table = result.forecast.assign(timestamp=lambda d: d["timestamp"].dt.strftime("%Y-%m")).round(2)
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "zone_id": "Zone",
            "zone_name": "Name",
            "timestamp": "Month",
            "baseline_aqi": "No-change AQI",
            "scenario_aqi": "Scenario AQI",
            "aqi_change": "Change",
        },
    )
    dl_cols = st.columns(2)
    dl_cols[0].download_button(
        "⬇ Download forecast (CSV)",
        table.to_csv(index=False).encode("utf-8"),
        file_name="digital_twin_forecast.csv",
        mime="text/csv",
        key="dl_forecast",
    )
    dl_cols[1].download_button(
        "⬇ Download zone summary (CSV)",
        result.summary.assign(base_month=lambda d: d["base_month"].dt.strftime("%Y-%m"))
        .round(3)
        .to_csv(index=False)
        .encode("utf-8"),
        file_name="digital_twin_zone_summary.csv",
        mime="text/csv",
        key="dl_summary",
    )

# --------------------------------------------------------------------------- about tab
with tab_about:
    st.markdown(
        f"""
**Project:** Digital Twin for Air Quality Index (AQI) prediction - {len(ALL_ZONES)} zones,
{history["timestamp"].min():%b %Y} to {history["timestamp"].max():%b %Y}, {metadata["n_features"]} model features.

**How a run works**
1. Take each zone's state at the *base month*.
2. Scale the chosen drivers by the given percentages (e.g. traffic -30%).
3. Predict AQI with and without the changes, then roll the forecast forward month by month.

**Limitations (be aware when interpreting results)**
- Forecasts hold every feature constant except month, year, quarter and the sin/cos month terms, as in the notebook.
- Changing a driver does not recompute derived features (lags, rolling stats, interaction terms).
- AQI is computed from pollutant concentrations that are also model inputs, so test R² is very high
  and pollutant sensor overrides have a strong effect.
- Tree-based models cannot extrapolate and may jump unrealistically; prefer linear models for what-if analysis.
"""
    )
    st.subheader("Model performance (hold-out test set)")
    st.dataframe(
        model_metrics[["Model", "Test_RMSE", "Test_MAE", "Test_R2", "Test_MAPE"]],
        hide_index=True,
        width="stretch",
    )
