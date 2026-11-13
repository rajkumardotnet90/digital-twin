"""Load model artifacts and historical data from disk."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from . import config
from .twin import AQIDigitalTwin


class ArtifactError(RuntimeError):
    """Raised when a required model/data file is missing or unreadable."""


def _require(path: Path) -> Path:
    if not path.exists():
        raise ArtifactError(f"Required file not found: {path}. Check DT_DATA_DIR / DT_MODEL_DIR.")
    return path


def load_metadata(model_dir: Path | None = None) -> dict:
    path = _require((model_dir or config.MODEL_DIR) / config.METADATA_FILE)
    return json.loads(path.read_text())


def load_history(data_dir: Path | None = None) -> pd.DataFrame:
    path = _require((data_dir or config.DATA_DIR) / config.MASTER_FILE)
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def load_model_metrics(model_dir: Path | None = None) -> pd.DataFrame:
    return pd.read_csv(_require((model_dir or config.MODEL_DIR) / config.METRICS_FILE))


def load_twin(
    model_key: str,
    history: pd.DataFrame | None = None,
    model_dir: Path | None = None,
) -> AQIDigitalTwin:
    """Build a twin around one of the bundled models (trusted, repo-shipped pickles only)."""
    if model_key not in config.MODEL_REGISTRY:
        raise ArtifactError(f"Unknown model '{model_key}'. Choose from: {', '.join(config.MODEL_REGISTRY)}")
    model_dir = model_dir or config.MODEL_DIR
    _, filename, _ = config.MODEL_REGISTRY[model_key]
    model = joblib.load(_require(model_dir / filename))
    scaler = joblib.load(_require(model_dir / config.SCALER_FILE))
    features = load_metadata(model_dir)["features"]
    return AQIDigitalTwin(model, scaler, features, history if history is not None else load_history())
