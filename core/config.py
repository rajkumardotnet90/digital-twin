"""Static configuration: paths, drivers, presets and the model registry.

Paths and limits can be overridden with environment variables (see .env.example).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DT_DATA_DIR", PROJECT_ROOT / "data"))
MODEL_DIR = Path(os.getenv("DT_MODEL_DIR", PROJECT_ROOT / "models"))
DEFAULT_MODEL = os.getenv("DT_DEFAULT_MODEL", "elasticnet")
MAX_HORIZON_MONTHS = int(os.getenv("DT_MAX_HORIZON", "36"))
DEFAULT_HORIZON_MONTHS = int(os.getenv("DT_DEFAULT_HORIZON", "12"))
MAX_SAVED_RUNS = int(os.getenv("DT_MAX_SAVED_RUNS", "10"))

MASTER_FILE = "master_feature_matrix.csv"
METADATA_FILE = "model_metadata.json"
SCALER_FILE = "model_scaler.joblib"
METRICS_FILE = "model_comparison_results.csv"

# Physical AQI range used to sanity-check (and clip) model output.
AQI_MIN, AQI_MAX = 0.0, 500.0

# (upper bound, label, colour) - same bands as the deployment notebook.
AQI_BANDS: list[tuple[float, str, str]] = [
    (50, "Good", "#00e400"),
    (100, "Moderate", "#ffff00"),
    (150, "Unhealthy (Sensitive)", "#ff7e00"),
    (200, "Unhealthy", "#ff0000"),
    (300, "Very Unhealthy", "#8f3f97"),
    (500, "Hazardous", "#7e0023"),
]


@dataclass(frozen=True)
class Driver:
    """A feature the user can scale by a percentage in a what-if scenario."""

    feature: str
    label: str
    help: str
    group: str  # "policy" or "sensor"
    min_pct: int = -100
    max_pct: int = 200
    step: int = 5


DRIVERS: tuple[Driver, ...] = (
    Driver("avg_traffic_volume", "Traffic volume", "Average monthly traffic volume.", "policy", -100, 100),
    Driver("avg_renewable_pct", "Renewable energy share", "Share of renewables in the energy mix.", "policy"),
    Driver("avg_energy_consumption", "Energy consumption", "Average energy consumption.", "policy", -100, 100),
    Driver("total_vehicles_charged", "EVs charged", "EVs charged at stations (EV adoption).", "policy", -100, 300),
    Driver("total_energy_dispensed", "EV energy dispensed", "Energy dispensed by EV stations.", "policy", -100, 300),
    Driver("avg_noise_db", "Noise level (dB)", "Average noise level.", "policy", -50, 50),
    Driver("pm2_5", "PM2.5 sensor", "Override the PM2.5 sensor reading.", "sensor", -50, 100),
    Driver("pm10", "PM10 sensor", "Override the PM10 sensor reading.", "sensor", -50, 100),
    Driver("no2", "NO2 sensor", "Override the NO2 sensor reading.", "sensor", -50, 100),
    Driver("so2", "SO2 sensor", "Override the SO2 sensor reading.", "sensor", -50, 100),
    Driver("o3", "O3 sensor", "Override the ozone sensor reading.", "sensor", -50, 100),
    Driver("co", "CO sensor", "Override the CO sensor reading.", "sensor", -50, 100),
    Driver("co2", "CO2 sensor", "Override the CO2 sensor reading.", "sensor", -50, 100),
)
DRIVERS_BY_FEATURE = {d.feature: d for d in DRIVERS}

# Policy presets from the deployment notebook: {feature: % change}.
POLICY_PRESETS: dict[str, dict[str, float]] = {
    "Custom (manual)": {},
    "Green Transport (30% less traffic)": {"avg_traffic_volume": -30},
    "Clean Energy (50% more renewables)": {"avg_renewable_pct": 50, "avg_energy_consumption": -25},
    "EV Push (100% more EVs)": {"total_vehicles_charged": 100, "total_energy_dispensed": 100},
    "Combined Green Policy": {
        "avg_traffic_volume": -30,
        "avg_renewable_pct": 50,
        "avg_energy_consumption": -25,
        "total_vehicles_charged": 100,
    },
}

# key -> (display label, joblib file, row name in model_comparison_results.csv)
MODEL_REGISTRY: dict[str, tuple[str, str, str]] = {
    "lasso_regression": ("Lasso Regression (best test R²)", "model_lasso_regression.joblib", "Lasso Regression"),
    "elasticnet": ("ElasticNet (best for what-if)", "model_elasticnet.joblib", "ElasticNet"),
    "ridge_regression": ("Ridge Regression", "model_ridge_regression.joblib", "Ridge Regression"),
    "linear_regression": ("Linear Regression", "model_linear_regression.joblib", "Linear Regression"),
    "gradient_boosting": ("Gradient Boosting", "model_gradient_boosting.joblib", "Gradient Boosting"),
    "random_forest": ("Random Forest", "model_random_forest.joblib", "Random Forest"),
    "svr": ("SVR", "model_svr.joblib", "SVR"),
    "knn": ("KNN", "model_knn.joblib", "KNN"),
    "decision_tree": ("Decision Tree", "model_decision_tree.joblib", "Decision Tree"),
    "adaboost": ("AdaBoost", "model_adaboost.joblib", "AdaBoost"),
}
