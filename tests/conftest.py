import pytest

from core import config
from core.loader import load_history, load_twin

MODEL_DIR_OK = (config.MODEL_DIR / config.METADATA_FILE).exists()


@pytest.fixture(scope="session")
def history():
    return load_history()


@pytest.fixture(scope="session")
def twin_lasso(history):
    return load_twin("lasso_regression", history)


@pytest.fixture(scope="session")
def twin_enet(history):
    return load_twin("elasticnet", history)
