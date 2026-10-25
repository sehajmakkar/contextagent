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


def test_capture_is_stored_and_queued_for_processing(client):
    h = {"X-Brain-Token": client.token}
    assert client.post("/observations", json=OBS, headers=h).json()["status"] == "stored"
    assert client.post("/observations", json=OBS, headers=h).json()["status"] == "duplicate"
    assert client.get("/status", headers=h).json()["captured"] == 1


def test_invalid_payload_is_422(client):
    r = client.post("/observations", json={**OBS, "text": ""}, headers={"X-Brain-Token": client.token})
    assert r.status_code == 422


def test_inbox_lists_and_resolves_loops(client):
    from datetime import date

    from brain.db import store
    from brain.models import ObservationIn
    conn = store.connect(get_settings().db_path)
    with conn:
        obs_id = store.insert_observation(conn, ObservationIn(**OBS))
        store.create_loop(conn, observation_id=obs_id, evidence_quote="Can you send the deck by Friday?",
                          title="Send the deck", direction="i_owe", counterparty="Jordan Lee", deliverable="deck",
                          note="Asked for Friday.", due_date=date(2026, 10, 30), confidence=0.9)
    h = {"X-Brain-Token": client.token}
    [loop] = client.get("/loops", headers=h).json()
    assert (loop["source_app"], loop["quote"], loop["window_title"]) == ("Google Chrome", "Can you send the deck by Friday?", "Inbox - Gmail")

    assert client.post(f"/loops/{loop['id']}/transition", json={"to": "closed"}, headers=h).json()["closed_reason"] == "user"
    assert client.get("/loops", headers=h).json() == []
    # dismissing a closed loop isn't an allowed transition: 409, state unchanged
    assert client.post(f"/loops/{loop['id']}/transition", json={"to": "dismissed"}, headers=h).status_code == 409


def test_approval_endpoint_needs_the_shown_hash_and_sends_once(client):
    """End to end through HTTP with a scripted agent and a fake mailbox."""
    from brain.agent.loop import close_loop
    from brain.api import app
    from brain.mailbox.fake import FakeMailbox
    from tests.test_agent import HAPPY, ME, THREAD, ScriptedLLM

    from datetime import date
    from brain.db import store
    from brain.models import ObservationIn
    conn = store.connect(get_settings().db_path)
    with conn:
        obs_id = store.insert_observation(conn, ObservationIn(**{**OBS, "text": "Sure, will send them over by Wednesday."}))
        loop_id = store.create_loop(conn, observation_id=obs_id, evidence_quote="Sure, will send them over by Wednesday.",
                                    title="Send Priya the Q3 numbers", direction="i_owe", counterparty="Priya Sharma",
                                    deliverable="Q3 numbers", note="n", due_date=date(2026, 10, 21), confidence=0.9)
    fake = FakeMailbox.from_spec(ME, THREAD)
    app.state.mailbox = fake
    run = close_loop(conn, ScriptedLLM(HAPPY), fake, get_settings(), loop_id)
    h = {"X-Brain-Token": client.token}

    assert client.get(f"/actions/{run.action_id}", headers=h).json()["status"] == "awaiting_approval"
    assert client.post(f"/actions/{run.action_id}/approve", json={"draft_hash": "stale"}, headers=h).status_code == 409
    ok = client.post(f"/actions/{run.action_id}/approve", json={"draft_hash": run.draft["draft_hash"]}, headers=h)
    assert ok.status_code == 200 and ok.json()["status"] == "sent"
    assert client.post(f"/actions/{run.action_id}/approve", json={"draft_hash": run.draft["draft_hash"]}, headers=h).status_code == 409
    assert len(fake.sent) == 1
    app.state.mailbox = None


def _demo_loop(conn):
    from datetime import date

    from brain.db import store
    from brain.models import ObservationIn
    with conn:
        obs_id = store.insert_observation(conn, ObservationIn(**{**OBS, "text": "Sure, will send them over by Wednesday."}))
        return store.create_loop(conn, observation_id=obs_id, evidence_quote="Sure, will send them over by Wednesday.",
                                 title="Send Priya the Q3 numbers", direction="i_owe", counterparty="Priya Sharma",
                                 deliverable="Q3 numbers", note="n", due_date=date(2026, 10, 21), confidence=0.9)


def test_agent_progress_streams_as_server_sent_events(client):
    import json

    from brain.api import app
    from brain.db import store
    from brain.mailbox.fake import FakeMailbox
    from tests.test_agent import HAPPY, ME, THREAD, ScriptedLLM

    loop_id = _demo_loop(store.connect(get_settings().db_path))
    app.state.mailbox, app.state.llm = FakeMailbox.from_spec(ME, THREAD), ScriptedLLM(HAPPY)
    h = {"X-Brain-Token": client.token}
    try:
        with client.stream("POST", f"/loops/{loop_id}/close/stream", headers=h) as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    finally:
        app.state.mailbox = app.state.llm = None

    steps = [e["label"] for e in events if e["type"] == "step"]
    assert steps == ["Searching your mail", "Reading the thread", "Drafting the reply", "Wrapping up"]
    done = events[-1]
    assert done["type"] == "done" and done["action"]["status"] == "awaiting_approval"

    [loop] = client.get("/loops", headers=h).json()
    assert loop["state"] == "awaiting_approval" and loop["last_action_id"] == done["action"]["id"]
    assert loop["bundle_id"] == "com.google.Chrome"


def test_delete_all_data_needs_the_exact_confirmation(client):
    from brain.db import store
    _demo_loop(store.connect(get_settings().db_path))
    h = {"X-Brain-Token": client.token}
    assert client.post("/data/delete", json={"confirm": "yes"}, headers=h).status_code == 400
    assert client.post("/data/delete", json={"confirm": "delete everything"}, headers=h).json()["deleted"]["loops"] == 1
    assert client.get("/loops?state=all", headers=h).json() == []


def test_status_reports_whether_the_agent_can_run(client, monkeypatch):
    import keyring
    monkeypatch.setattr(keyring, "get_password", lambda *a: None)
    status = client.get("/status", headers={"X-Brain-Token": client.token}).json()
    assert status["agent_ready"] is False and "gmail-login" in status["agent_detail"]



def test_concurrent_requests_do_not_trip_sqlite_thread_checks(client):
    """Regression: the app fires /loops, /memories and /status in parallel. FastAPI may open, use and close a
    request's connection on different pool threads, which sqlite3 rejects by default."""
    from concurrent.futures import ThreadPoolExecutor

    h = {"X-Brain-Token": client.token}
    paths = ["/loops", "/loops?state=closed", "/memories", "/status"] * 6
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda p: client.get(p, headers=h).status_code, paths))
    assert codes == [200] * len(paths)
