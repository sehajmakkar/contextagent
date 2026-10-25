from datetime import datetime, timedelta

from brain import episodes, retention
from brain.config import Settings
from brain.db import store
from brain.ingest import ingest
from brain.llm.client import Usage
from brain.loops import pipeline
from brain.loops.detect import LoopAnalysis, LoopCandidate, LoopUpdate
from brain.loops.dedupe import SameCommitment
from brain.loops.verify import CloseVerdict
from brain.memory.extract import Extraction, MemoryItem
from brain.models import ObservationIn

T0 = datetime.fromisoformat("2026-10-19T10:00:00+05:30")  # in the past, so finished visits can close
ASK = "Priya Sharma: can you send me the Q3 retention numbers before Thursday?"
REPLY = "Sehaj: sure, will send them by Wednesday"


def _obs(text: str, minutes: float = 0, title: str = "Q3 numbers - Gmail") -> ObservationIn:
    return ObservationIn(captured_at=T0 + timedelta(minutes=minutes), app_name="Google Chrome",
                         bundle_id="com.google.Chrome", window_title=title, text=text)


def test_snapshots_of_one_visit_merge_into_one_episode(conn):
    ingest(conn, _obs(f"Inbox 3\n{ASK}"), "capture")
    ingest(conn, _obs(f"Inbox 3\n{ASK}\n{REPLY}", minutes=2), "capture")  # you replied: one new line
    [ep] = conn.execute("SELECT * FROM episodes").fetchall()
    assert ep["observation_count"] == 2
    assert ep["text"] == f"Inbox 3\n{ASK}\n{REPLY}"  # each line once, first-seen order
    assert ep["raw_chars"] > len(ep["text"])        # the funnel's first saving


def test_a_long_gap_or_another_window_starts_a_new_episode(conn):
    ingest(conn, _obs(ASK), "capture")
    ingest(conn, _obs(ASK + " (again)", minutes=30), "capture")      # same window, 30 min later
    ingest(conn, _obs("Deploy finished", minutes=31, title="#eng - Slack"), "capture")
    assert conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 3


def test_close_stale(conn):
    ingest(conn, _obs(ASK), "capture")
    assert episodes.close_stale(conn, T0 + timedelta(minutes=2)) == 0   # still being visited
    assert episodes.close_stale(conn, T0 + timedelta(minutes=10)) == 1  # visit is over


class StubLLM:
    """Returns canned structured output, so the test checks our pipeline, not the model."""
    model = "stub"

    def __init__(self, updates=None, new_loops=True, verifier_agrees=True):
        self.updates, self.new_loops, self.verifier_agrees = updates or [], new_loops, verifier_agrees

    def embed(self, text, *, model, dims):
        return [1.0] + [0.0] * (dims - 1)  # every loop "looks alike": the judge must decide

    def generate_structured(self, *, schema, system, prompt, thinking_level):
        usage = Usage("stub", 100, 20, 0, 1)
        if schema is Extraction:
            return Extraction(memories=[
                MemoryItem(kind="plan", text="Sehaj will send Priya the Q3 retention numbers by Wednesday.",
                           quote=REPLY, entities=["Priya", "Q3 retention"]),
                MemoryItem(kind="fact", text="An invented fact.", quote="text that is not on screen", entities=[]),
            ]), usage
        if schema is SameCommitment:
            return SameCommitment(same=False, reason="different"), usage
        if schema is CloseVerdict:
            return CloseVerdict(fulfilled=self.verifier_agrees, reason="stub"), usage
        loops = [LoopCandidate(
            title="Send Priya the Q3 retention numbers", direction="i_owe", counterparty="Priya Sharma",
            counterparty_email=None, deliverable="Q3 retention numbers", note="Promised for Wednesday.",
            due_date=None, evidence_quote=REPLY, confidence=0.95)] if self.new_loops else []
        return LoopAnalysis(new_loops=loops, updates=self.updates), usage


def test_pipeline_stores_grounded_memories_and_loops_with_provenance(conn):
    ingest(conn, _obs(ASK), "file")
    reply = ingest(conn, _obs(f"{ASK}\n{REPLY}", minutes=1), "file")
    settings = Settings(gemini_tier="free")
    [ep] = pipeline.pending(conn, settings)  # fixture dates are in the past, so the episode closes

    outcome = pipeline.process(conn, StubLLM(), ep, settings)

    assert outcome.memories == ["Sehaj will send Priya the Q3 retention numbers by Wednesday."]  # ungrounded one dropped
    memory = conn.execute("SELECT * FROM memories").fetchone()
    assert memory["observation_id"] == reply.observation_id   # the snapshot that actually contains the quote
    assert len(outcome.created) == 1
    assert conn.execute("SELECT llm_calls FROM episodes").fetchone()[0] == 2  # no look-alike yet: no judge call
    assert pipeline.pending(conn, settings) == []
    # FTS5 index stays in sync through the trigger.
    assert conn.execute("SELECT COUNT(*) FROM memories_fts WHERE memories_fts MATCH 'retention'").fetchone()[0] == 1


def test_local_gate_skips_tiny_episodes_without_an_llm_call(conn):
    ingest(conn, _obs("Loading… please wait a moment"), "file")
    [ep] = pipeline.pending(conn, Settings())
    outcome = pipeline.process(conn, None, ep, Settings())  # no LLM needed
    assert outcome.skipped == "too little text"


def test_live_capture_episodes_are_held_back_on_the_free_tier(conn):
    ingest(conn, _obs(f"{ASK}\n{REPLY}", minutes=-60), "capture")
    free = Settings(gemini_tier="free", allow_free_tier_live=False)
    assert pipeline.pending(conn, free) == [] and pipeline.held_back(conn, free) == 1
    assert len(pipeline.pending(conn, Settings(gemini_tier="paid"))) == 1


def test_retention_erases_only_old_processed_snapshots(conn):
    ingest(conn, _obs(f"{ASK}\n{REPLY}"), "file")
    [ep] = pipeline.pending(conn, Settings())
    pipeline.process(conn, StubLLM(), ep, Settings())
    ingest(conn, _obs("A newer unprocessed screen with enough text to matter", title="Other"), "file")

    erased = retention.purge(conn, older_than_days=7, current=T0 + timedelta(days=8))
    assert erased == 1  # the processed one; the unprocessed one is kept until it's distilled
    assert conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 1  # memories survive
    assert store.find_open_loop_by_quote(conn, REPLY) is not None             # loop evidence survives


def test_a_later_screen_closes_the_loop_with_evidence(conn):
    ingest(conn, _obs(f"{ASK}\n{REPLY}"), "file")
    [ep] = pipeline.pending(conn, Settings())
    pipeline.process(conn, StubLLM(), ep, Settings())
    loop_id = conn.execute("SELECT id FROM loops").fetchone()[0]

    sent = "Sehaj: here are the Q3 retention numbers, 63.6% blended M1"
    ingest(conn, _obs(f"{ASK}\n{REPLY}\n{sent}", minutes=60 * 24), "file")
    [ep2] = pipeline.pending(conn, Settings())
    done = LoopUpdate(loop_id=loop_id, status="done", evidence_quote=sent, confidence=0.9)
    outcome = pipeline.process(conn, StubLLM(updates=[done], new_loops=False), ep2, Settings())

    assert outcome.closed == [loop_id]
    row = conn.execute("SELECT state, closed_reason FROM loops").fetchone()
    assert (row["state"], row["closed_reason"]) == ("closed", "inferred")
    assert [e["kind"] for e in store.get_evidence(conn, loop_id)][-1] == "closed"


def test_a_low_confidence_done_is_only_progress(conn):
    ingest(conn, _obs(f"{ASK}\n{REPLY}"), "file")
    [ep] = pipeline.pending(conn, Settings())
    pipeline.process(conn, StubLLM(), ep, Settings())
    loop_id = conn.execute("SELECT id FROM loops").fetchone()[0]
    ingest(conn, _obs(f"{ASK}\n{REPLY}\nSehaj: almost done with the numbers", minutes=60 * 24), "file")
    [ep2] = pipeline.pending(conn, Settings())
    maybe = LoopUpdate(loop_id=loop_id, status="done", evidence_quote="Sehaj: almost done with the numbers", confidence=0.5)
    outcome = pipeline.process(conn, StubLLM(updates=[maybe], new_loops=False), ep2, Settings())
    assert outcome.closed == [] and outcome.progressed == [loop_id]
    assert conn.execute("SELECT state FROM loops").fetchone()[0] == "open"


def test_the_verifier_can_veto_a_close(conn):
    """Regression: the NDA email 'closed' the Contoso renewal loop in an end-to-end run."""
    ingest(conn, _obs(f"{ASK}\n{REPLY}"), "file")
    [ep] = pipeline.pending(conn, Settings())
    pipeline.process(conn, StubLLM(), ep, Settings())
    loop_id = conn.execute("SELECT id FROM loops").fetchone()[0]
    other = "Sehaj: attached the signed NDA"
    ingest(conn, _obs(f"{ASK}\n{other}", minutes=60 * 24), "file")
    [ep2] = pipeline.pending(conn, Settings())
    claim = LoopUpdate(loop_id=loop_id, status="done", evidence_quote=other, confidence=0.95)
    outcome = pipeline.process(conn, StubLLM(updates=[claim], new_loops=False, verifier_agrees=False), ep2, Settings())
    assert outcome.closed == [] and conn.execute("SELECT state FROM loops").fetchone()[0] == "open"

