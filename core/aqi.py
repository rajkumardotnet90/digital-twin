"""AQI category helpers."""

from __future__ import annotations

from .config import AQI_BANDS


def aqi_category(value: float) -> str:
    for upper, label, _ in AQI_BANDS:
        if value <= upper:
            return label
    return AQI_BANDS[-1][1]


def aqi_color(value: float) -> str:
    for upper, _, color in AQI_BANDS:
        if value <= upper:
            return color
    return AQI_BANDS[-1][2]
