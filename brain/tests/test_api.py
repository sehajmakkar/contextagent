import pytest
from fastapi.testclient import TestClient

from brain.config import get_settings
from brain.db import store
from brain.loops import pipeline

OBS = {"captured_at": "2026-10-25T10:00:00+05:30", "app_name": "Google Chrome", "bundle_id": "com.google.Chrome",
       "window_title": "Inbox - Gmail", "url": "https://mail.google.com/", "text": "Can you send the deck by Friday?"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTO_DETECT", "false")
    monkeypatch.setenv("GEMINI_TIER", "free")
    monkeypatch.setenv("ALLOW_FREE_TIER_LIVE", "false")
    get_settings.cache_clear()
    from brain.api import app

    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        c.token = get_settings().token_path.read_text()
        yield c
    get_settings.cache_clear()


def test_token_file_is_private(client):
    assert oct(get_settings().token_path.stat().st_mode)[-3:] == "600"


def test_requests_without_the_token_are_rejected(client):
    assert client.post("/observations", json=OBS).status_code == 401
    assert client.get("/status", headers={"X-Brain-Token": "guess"}).status_code == 401


def test_foreign_host_header_is_rejected(client):
    """DNS rebinding: a web page at evil.example re-pointed to 127.0.0.1 still sends Host: evil.example."""
    r = client.get("/status", headers={"X-Brain-Token": client.token, "Host": "evil.example:8765"})
    assert r.status_code == 400


def test_capture_is_stored_but_held_back_on_free_tier(client):
    h = {"X-Brain-Token": client.token}
    assert client.post("/observations", json=OBS, headers=h).json()["status"] == "stored"
    assert client.post("/observations", json=OBS, headers=h).json()["status"] == "duplicate"

    status = client.get("/status", headers=h).json()
    assert status["captured"] == 1 and status["held_back"] == 1 and status["pending"] == 0
    assert status["live_detection_allowed"] is False

    conn = store.connect(get_settings().db_path)
    assert pipeline.pending(conn, get_settings()) == []  # never offered to Gemini


def test_invalid_payload_is_422(client):
    r = client.post("/observations", json={**OBS, "text": ""}, headers={"X-Brain-Token": client.token})
    assert r.status_code == 422
