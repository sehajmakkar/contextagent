from datetime import datetime, timedelta

from brain import episodes
from brain.config import Settings
from brain.ingest import ingest
from brain.loops import pipeline
from brain.models import ObservationIn

T0 = datetime.now().astimezone()


def _obs(title: str, text: str) -> ObservationIn:
    return ObservationIn(captured_at=T0, app_name="Google Chrome", bundle_id="com.google.Chrome", window_title=title, text=text)


def test_leaving_a_window_closes_its_visit_immediately(conn):
    ingest(conn, _obs("Repo link - Gmail", "can you send me the repo link before Friday?"), "capture")
    assert pipeline.pending(conn, Settings()) == []  # still being visited (5-min gap)
    with conn:
        assert episodes.end_visit(conn, "com.google.Chrome", "Repo link - Gmail")
    assert len(pipeline.pending(conn, Settings())) == 1


def _notes(title: str, text: str, trigger: str = "settled") -> ObservationIn:
    return ObservationIn(captured_at=T0, app_name="Notes", bundle_id="com.apple.Notes", window_title=title, text=text,
                         trigger=trigger)


def test_reading_another_window_closes_the_previous_visit(conn):
    # Notes puts the note count in the title, so a new note is a new window with no "leaving" read of the old one.
    ingest(conn, _notes("All iCloud – 53 notes", "Todo: email Priya the Q3 retention numbers by Wednesday"), "capture")
    ingest(conn, _notes("New Folder – 1 note", "Groceries: oat milk, eggs, coffee beans and bread"), "capture")
    [closed] = pipeline.pending(conn, Settings())
    assert closed["window_title"] == "All iCloud – 53 notes"  # the one you left; the current one stays open


def test_a_late_leaving_read_doesnt_close_the_window_you_are_in(conn):
    ingest(conn, _notes("New Folder – 1 note", "Groceries: oat milk, eggs, coffee beans and bread"), "capture")
    ingest(conn, _obs("Repo link - Gmail", "the leaving read of the app you just switched away from"), "capture")
    ingest(conn, _notes("Old note", "a leaving read arriving after the next window was read", trigger="leaving"), "capture")
    open_titles = {r["window_title"] for r in conn.execute("SELECT window_title FROM episodes WHERE closed_at IS NULL")}
    assert "Repo link - Gmail" in open_titles


def test_newest_visit_is_processed_first(conn):
    for title in ("first", "second"):
        ingest(conn, _obs(title, f"some text long enough to keep, in the {title} window"), "capture")
        with conn:
            episodes.end_visit(conn, "com.google.Chrome", title)
    assert [e["window_title"] for e in pipeline.pending(conn, Settings())] == ["second", "first"]
