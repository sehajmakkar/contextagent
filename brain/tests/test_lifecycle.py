import sqlite3
from datetime import date

import pytest
import sqlite_vec

from brain.db import store
from brain.loops import lifecycle
from brain.models import ObservationIn

OBS = ObservationIn(captured_at="2026-10-19T10:00:00+05:30", app_name="Google Chrome", bundle_id="com.google.Chrome",
                    window_title="Q3 - Gmail", text="Sure, will send them over by Wednesday.")


def _loop(conn) -> int:
    obs_id = store.insert_observation(conn, OBS)
    return store.create_loop(conn, observation_id=obs_id, evidence_quote="Sure, will send them over by Wednesday.",
                             title="Send Priya the Q3 numbers", direction="i_owe", counterparty="Priya Sharma",
                             deliverable="Q3 numbers", note="You promised Wednesday.", due_date=date(2026, 10, 21),
                             confidence=0.95)


def test_full_happy_path_is_recorded(conn):
    loop_id = _loop(conn)
    lifecycle.transition(conn, loop_id, "acting", actor="agent", reason="drafting reply")
    lifecycle.transition(conn, loop_id, "awaiting_approval", actor="agent", reason="draft ready")
    lifecycle.transition(conn, loop_id, "closed", actor="user", reason="approved and sent")
    row = conn.execute("SELECT state, closed_reason, closed_at, source_app FROM loops").fetchone()
    assert (row["state"], row["closed_reason"], row["source_app"]) == ("closed", "user", "Google Chrome")
    assert row["closed_at"]
    assert [(h["from_state"], h["to_state"], h["actor"]) for h in lifecycle.history(conn, loop_id)] == [
        (None, "open", "system"), ("open", "acting", "agent"), ("acting", "awaiting_approval", "agent"),
        ("awaiting_approval", "closed", "user")]


def test_inferred_closes_are_distinguishable_and_reopenable(conn):
    loop_id = _loop(conn)
    lifecycle.transition(conn, loop_id, "closed", actor="system", reason="evidence: sent", confidence=0.9)
    assert conn.execute("SELECT closed_reason FROM loops").fetchone()[0] == "inferred"
    lifecycle.transition(conn, loop_id, "open", actor="user", reason="not actually done")
    assert conn.execute("SELECT state, closed_reason FROM loops").fetchone()[:] == ("open", None)


def test_impossible_jumps_are_refused(conn):
    loop_id = _loop(conn)
    lifecycle.transition(conn, loop_id, "dismissed", actor="user", reason="not a loop")
    with pytest.raises(lifecycle.InvalidTransition):
        lifecycle.transition(conn, loop_id, "awaiting_approval", actor="agent", reason="?")


def test_rebuild_migration_keeps_evidence(tmp_path):
    """Regression for the FK trap: DROP TABLE loops would cascade-delete loop_evidence if FKs were on."""
    path = tmp_path / "v5.db"
    old = sqlite3.connect(path)
    old.enable_load_extension(True)
    sqlite_vec.load(old)
    old.execute("PRAGMA foreign_keys=ON")
    for number, migration in enumerate(store._MIGRATIONS[:5], start=1):
        old.executescript(f"BEGIN;\n{migration.read_text()}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute("""INSERT INTO observations (captured_at, app_name, bundle_id, text, content_hash)
                   VALUES ('2026-10-19T10:00:00+05:30', 'Slack', 'x', 'will do', 'h')""")
    old.execute("""INSERT INTO loops (title, direction, counterparty, deliverable, confidence, created_at, updated_at)
                   VALUES ('Review PR', 'i_owe', 'Rahul', 'review', 0.9, 'now', 'now')""")
    old.execute("INSERT INTO loop_evidence (loop_id, observation_id, quote, kind, created_at) VALUES (1, 1, 'will do', 'created', 'now')")
    old.commit()
    old.close()

    conn = store.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION
    assert conn.execute("SELECT COUNT(*) FROM loop_evidence").fetchone()[0] == 1   # survived the rebuild
    assert conn.execute("SELECT source_app FROM loops").fetchone()[0] == "Slack"   # backfilled from evidence
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1                  # switched back on
