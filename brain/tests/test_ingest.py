import sqlite3
from datetime import datetime, timedelta

from brain.db import store
from brain.ingest import ingest, new_lines
from brain.models import ObservationIn

T0 = datetime.fromisoformat("2026-10-25T10:00:00+05:30")
THREAD = ("Q3 retention numbers for Thursday\nPriya Sharma\nCan you send me the Q3 retention numbers before "
          "Thursday's business review? I want to put the cohort chart on slide 4.\nSure, will send them over by Wednesday.")
CHANNEL = "\n".join(f"Dev {i}: deploy {i} finished, metrics look normal, nothing to report from the on-call side"
                    for i in range(25))


def _obs(text: str, at: datetime = T0, title: str = "Q3 retention - Gmail") -> ObservationIn:
    return ObservationIn(captured_at=at, app_name="Google Chrome", bundle_id="com.google.Chrome",
                         window_title=title, text=text)


def test_exact_then_near_duplicate_then_new(conn):
    assert ingest(conn, _obs("Inbox 12\n" + THREAD), "capture").status == "stored"
    assert ingest(conn, _obs("Inbox 12\n" + THREAD), "capture").status == "duplicate"
    # Only the unread counter changed a minute later: same screen, don't store it again.
    near = ingest(conn, _obs("Inbox 11\n" + THREAD, T0 + timedelta(minutes=1)), "capture")
    assert near.status == "near_duplicate" and near.new_lines == 0
    # Same window 2 days later is a real revisit (it becomes loop evidence), so it's kept.
    assert ingest(conn, _obs("Inbox 9\n" + THREAD, T0 + timedelta(days=2)), "capture").status == "stored"


def test_a_new_chat_message_in_a_long_channel_is_kept(conn):
    """Regression for the Jaccard design: ~95% similar, but the new line is a commitment we must not drop."""
    assert ingest(conn, _obs(CHANNEL, title="#eng - Slack"), "capture").status == "stored"
    later = CHANNEL + "\nSehaj 10:02: yep, will do"  # 3 new words, same size as a clock change
    assert ingest(conn, _obs(later, T0 + timedelta(minutes=2), title="#eng - Slack"), "capture").status == "stored"


def test_clock_and_badge_changes_are_not_new_content():
    assert new_lines("Inbox 12\nUpdated 10:41 AM\nHello", "Inbox 11\nUpdated 10:42 AM\nHello") == []


def test_redaction_happens_before_storage(conn):
    result = ingest(conn, _obs("my key AIza" + "x" * 35 + " please rotate"), "capture")
    stored = store.get_observation(conn, result.observation_id)["text"]
    assert "AIza" not in stored and result.redactions["api_key"] == 1


def test_new_lines_ignores_scrolled_away_content():
    assert new_lines("a\nb\nc", "b\nc") == []
    assert new_lines("a\nb", "a\nb\nnew message") == ["new message"]


def test_v1_database_upgrades_in_place(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript((store._MIGRATIONS[0]).read_text())
    old.execute("PRAGMA user_version = 1")
    old.execute("""INSERT INTO observations (captured_at, app_name, bundle_id, text, content_hash)
                   VALUES ('2026-10-19T10:00:00+05:30', 'Mail', 'x', 'hello', 'h')""")
    old.commit()
    old.close()

    conn = store.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION
    row = conn.execute("SELECT source, detect_attempts FROM observations").fetchone()
    assert (row["source"], row["detect_attempts"]) == ("file", 0)
