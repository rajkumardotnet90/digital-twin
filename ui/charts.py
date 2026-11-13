"""Plotly figure builders (no Streamlit dependency, so they can be unit-tested)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from core.config import AQI_BANDS

ACTUAL, NO_CHANGE, SCENARIO = "#4C72B0", "#7f7f7f", "#d62728"
RUN_COLORS = ["#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2", "#bcbd22"]


def _add_aqi_bands(fig: go.Figure, y_max: float, y_min: float = 0.0) -> None:
    lower = 0.0
    for upper, label, color in AQI_BANDS:
        if lower >= y_max:
            break
        if upper > y_min:
            fig.add_hrect(
                y0=max(lower, y_min),
                y1=min(upper, y_max),
                fillcolor=color,
                opacity=0.10,
                line_width=0,
                layer="below",
                annotation_text=label,
                annotation_position="top right",
                annotation_font_size=10,
            )
        lower = upper


def _forecast_start(fig: go.Figure, when: pd.Timestamp) -> None:
    fig.add_shape(
        type="line", x0=when, x1=when, y0=0, y1=1, yref="paper", line={"color": "black", "width": 1, "dash": "dot"}
    )
    fig.add_annotation(
        x=when, y=1, yref="paper", text="Forecast start", showarrow=False, xanchor="left", yanchor="bottom"
    )


def forecast_chart(
    history: pd.DataFrame,
    series: pd.DataFrame,
    base_month: pd.Timestamp,
    title: str,
    zoom_forecast: bool = False,
) -> go.Figure:
    """Observed AQI plus no-change and scenario forecasts.

    ``zoom_forecast`` shows only the last 6 observed months and fits the y-axis to the data,
    which makes small scenario effects visible.
    """
    if zoom_forecast:
        history = history[history["timestamp"] >= base_month - pd.DateOffset(months=6)]
    fig = go.Figure()
    fig.add_scatter(x=history["timestamp"], y=history["AQI"], name="Observed AQI", line={"color": ACTUAL, "width": 2})
    fig.add_scatter(
        x=series["timestamp"],
        y=series["baseline_aqi"],
        name="Forecast - no change",
        line={"color": NO_CHANGE, "dash": "dash", "width": 2},
    )
    fig.add_scatter(
        x=series["timestamp"],
        y=series["scenario_aqi"],
        name="Forecast - scenario",
        line={"color": SCENARIO, "width": 3},
        mode="lines+markers",
    )
    values = pd.concat([history["AQI"], series["baseline_aqi"], series["scenario_aqi"]])
    if zoom_forecast:
        pad = max(2.0, (values.max() - values.min()) * 0.15)
        y_min, y_max = max(0.0, values.min() - pad), values.max() + pad
    else:
        y_min, y_max = 0.0, values.max() * 1.15
    _add_aqi_bands(fig, y_max, y_min)
    _forecast_start(fig, base_month)
    fig.update_layout(
        title=title,
        yaxis={"title": "AQI", "range": [y_min, y_max]},
        xaxis_title="Month",
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.2},
        margin={"t": 60, "b": 40},
    )
    return fig


def zone_bar_chart(summary: pd.DataFrame) -> go.Figure:
    """Per-zone predicted AQI: no change vs scenario."""
    fig = go.Figure()
    fig.add_bar(x=summary["zone_name"], y=summary["baseline_aqi"], name="No change", marker_color=NO_CHANGE)
    fig.add_bar(x=summary["zone_name"], y=summary["scenario_aqi"], name="Scenario", marker_color=SCENARIO)
    fig.update_layout(
        barmode="group",
        title="Predicted AQI by zone at the base month",
        yaxis_title="AQI",
        legend={"orientation": "h", "y": -0.3},
        margin={"t": 60},
    )
    return fig


def compare_chart(history: pd.DataFrame | None, runs: list[tuple[str, pd.DataFrame, bool]]) -> go.Figure:
    """Overlay scenario forecasts. ``runs`` = [(label, series, is_baseline)]."""
    fig = go.Figure()
    if history is not None:
        fig.add_scatter(
            x=history["timestamp"], y=history["AQI"], name="Observed AQI", line={"color": ACTUAL, "width": 2}
        )
    palette = iter(RUN_COLORS)
    for label, series, is_baseline in runs:
        style = (
            {"color": NO_CHANGE, "dash": "dash", "width": 4} if is_baseline else {"color": next(palette), "width": 2.5}
        )
        fig.add_scatter(x=series["timestamp"], y=series["scenario_aqi"], name=label, line=style, mode="lines+markers")
    fig.update_layout(
        title="Compare runs - forecast AQI",
        yaxis_title="AQI",
        xaxis_title="Month",
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.25},
        margin={"t": 60, "b": 40},
    )
    return fig
