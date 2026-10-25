"""Offline checks of the code around the LLM calls: schemas, grounding, recipient safety."""

from datetime import date

import pytest

from brain.loops.detect import Detection, LoopCandidate, _keep

SOURCE = "Priya Sharma <priya.sharma@northwind.example>\nSure, will send them over by Wednesday.\nReply"


def _candidate(**overrides) -> LoopCandidate:
    fields = dict(title="Send Priya the numbers", direction="i_owe", counterparty="Priya Sharma",
                  counterparty_email=None, deliverable="Q3 numbers", due_date=date(2026, 10, 21),
                  note="Promised for Wednesday.", evidence_quote="Sure, will send them over by Wednesday.", confidence=0.9)
    return LoopCandidate(**(fields | overrides))


def test_grounded_confident_candidate_is_kept():
    assert _keep(_candidate(), SOURCE)


def test_low_confidence_is_dropped():
    assert not _keep(_candidate(confidence=0.3), SOURCE)


def test_paraphrased_quote_is_dropped():
    assert not _keep(_candidate(evidence_quote="I'll send the numbers Wednesday"), SOURCE)


def test_detection_schema_uses_supported_json_schema_features():
    schema = str(Detection.model_json_schema())
    assert "'format': 'date'" in schema and "'$ref'" in schema


@pytest.mark.live
def test_live_detects_the_demo_loop(conn, demo_observations):
    from brain.config import get_settings
    from brain.db import store
    from brain.llm.client import LLMClient
    from brain.loops.detect import detect_loops

    s = get_settings()
    if not s.gemini_api_key:
        pytest.skip("GEMINI_API_KEY not set")
    obs_id = store.insert_observation(conn, demo_observations[0])
    loops, _ = detect_loops(LLMClient(s.gemini_api_key.get_secret_value(), s.llm_model),
                            store.get_observation(conn, obs_id), name=s.user_name, email=s.user_email)
    assert len(loops) == 1
    assert loops[0].direction == "i_owe" and loops[0].due_date == date(2026, 10, 21)


def test_spliced_quotes_are_grounded_only_if_every_piece_is_real():
    from brain.db.store import grounded
    source = "Maya Chen <maya@acme-talent.example>\nI came across your work and would love a quick 30-minute intro call."
    assert grounded("Maya Chen <maya@acme-talent.example> ... would love a quick 30-minute intro call", source)
    assert not grounded("Maya Chen ... would love a two-hour onsite", source)


def test_different_figures_are_never_folded_as_duplicates():
    from brain.memory.embed import numbers
    q3, q2 = "The Q3 blended M1 retention is 63.6%, up from 58.9% in Q2.", "The Q2 blended M1 retention is 58.9%, up from 55.4% in Q1."
    a, b = numbers(q3), numbers(q2)
    assert not (a <= b or b <= a)
    restated = numbers("Sehaj will send the Q3 retention numbers by Wednesday, October 21, 2026.")
    assert numbers("Sehaj will send the Q3 retention numbers by Wednesday.") <= restated
