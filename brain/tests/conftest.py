from pathlib import Path

import pytest

from brain.config import Settings, get_settings

from brain.db import store
from brain.models import ObservationIn

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "sessions" / "demo_week.jsonl"


@pytest.fixture
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def demo_observations() -> list[ObservationIn]:
    return [ObservationIn.model_validate_json(line) for line in FIXTURES.read_text().splitlines() if line.strip()]


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """Tests never read the developer's .env (it holds real keys and settings that change behaviour)."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for var in ("LLM_MODEL", "AUTO_DETECT", "DATA_DIR"):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
