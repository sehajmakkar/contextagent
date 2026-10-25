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
