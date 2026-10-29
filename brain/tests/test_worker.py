import sqlite3
import time

from brain import episodes
from brain.config import Settings
from brain.db import store
from brain.ingest import ingest
from brain.loops import pipeline, worker
from brain.models import ObservationIn


def test_worker_survives_a_database_error(tmp_path, monkeypatch):
    """A sqlite error used to kill the detection thread for good (seen live after Delete all data)."""
    settings = Settings(gemini_api_key="test", data_dir=tmp_path, detect_min_interval_s=0)
    conn = store.connect(settings.db_path)
    for title in ("first", "second"):
        ingest(conn, ObservationIn(captured_at="2026-10-29T19:00:00+05:30", app_name="Notes", bundle_id="com.apple.Notes",
                                   window_title=title, text=f"Todo in the {title} note: email Priya the deck by Friday"),
               "capture")
        with conn:
            episodes.end_visit(conn, "com.apple.Notes", title)

    calls = []

    def flaky(conn, llm, episode, settings):
        calls.append(episode["window_title"])
        if len(calls) == 1:
            raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")
        with conn:
            conn.execute("UPDATE episodes SET processed_at = 'now' WHERE id = ?", (episode["id"],))
        return pipeline.DetectOutcome()

    monkeypatch.setattr(worker.pipeline, "process", flaky)
    w = worker.DetectionWorker(settings)
    w.start()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE processed_at IS NULL").fetchone()[0]:
        time.sleep(0.1)
    w.stop()
    w.join(timeout=10)

    assert w.failed == 1 and "FOREIGN KEY" in w.last_error
    assert conn.execute("SELECT COUNT(*) FROM episodes WHERE processed_at IS NULL").fetchone()[0] == 0
    assert conn.execute("SELECT process_attempts FROM episodes WHERE window_title = 'second'").fetchone()[0] == 1
