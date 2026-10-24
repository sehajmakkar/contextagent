from datetime import date

from brain.db import store


def test_fixtures_load_and_dedupe(conn, demo_observations):
    ids = [store.insert_observation(conn, o, o.text) for o in demo_observations]
    assert all(ids), "every fixture line is distinct content"
    # Ingesting the same file again stores nothing new.
    assert [store.insert_observation(conn, o, o.text) for o in demo_observations] == [None] * len(ids)
    assert len(store.unprocessed_observations(conn)) == len(ids)


def test_loop_lifecycle_and_quote_dedupe(conn, demo_observations):
    first = store.insert_observation(conn, demo_observations[0], demo_observations[0].text)
    revisit = store.insert_observation(conn, demo_observations[-1], demo_observations[-1].text)
    quote = "Sure, will send them over by Wednesday."

    loop_id = store.create_loop(
        conn, observation_id=first, evidence_quote=quote, title="Send Priya the Q3 retention numbers",
        direction="i_owe", counterparty="Priya Sharma", counterparty_email="priya.sharma@northwind.example",
        deliverable="Q3 retention numbers", due_date=date(2026, 10, 21), confidence=0.95,
    )
    # Same sentence, different whitespace/case, seen on a later screen → same loop.
    assert store.find_open_loop_by_quote(conn, "  sure, will send them over   by Wednesday. ") == loop_id
    store.add_evidence(conn, loop_id, revisit, quote, "progress")

    [row] = store.list_loops(conn)
    assert row["due_date"] == "2026-10-21" and row["evidence_count"] == 2
    assert [e["kind"] for e in store.get_evidence(conn, loop_id)] == ["created", "progress"]


def test_audit_log(conn):
    action_id = store.log_action(conn, loop_id=None, kind="draft_reply", status="drafted",
                                 input={"x": 1}, output={"body": "hi"}, model="m")
    row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    assert row["status"] == "drafted" and '"body": "hi"' in row["output_json"]
