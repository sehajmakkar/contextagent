from pathlib import Path

import pytest

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
