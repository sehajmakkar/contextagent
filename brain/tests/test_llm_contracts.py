"""Offline checks of the code around the LLM calls: schemas, grounding, recipient safety."""

from datetime import date

import pytest

from brain.agent.draft import EmailDraft, _only_known_recipients
from brain.loops.detect import Detection, LoopCandidate, _keep

SOURCE = "Priya Sharma <priya.sharma@northwind.example>\nSure, will send them over by Wednesday.\nReply"


def _candidate(**overrides) -> LoopCandidate:
    fields = dict(title="Send Priya the numbers", direction="i_owe", counterparty="Priya Sharma",
                  counterparty_email=None, deliverable="Q3 numbers", due_date=date(2026, 10, 21),
                  evidence_quote="Sure, will send them over by Wednesday.", confidence=0.9)
    return LoopCandidate(**(fields | overrides))


def test_grounded_confident_candidate_is_kept():
    assert _keep(_candidate(), SOURCE)


def test_low_confidence_is_dropped():
    assert not _keep(_candidate(confidence=0.3), SOURCE)


def test_paraphrased_quote_is_dropped():
    assert not _keep(_candidate(evidence_quote="I'll send the numbers Wednesday"), SOURCE)


def test_recipients_outside_the_thread_are_removed():
    draft = EmailDraft(to=["priya.sharma@northwind.example", "x@evil.example"], subject="Re: Q3",
                       body="Hi", missing_info=[])
    kept, removed = _only_known_recipients(draft, SOURCE)
    assert kept.to == ["priya.sharma@northwind.example"] and removed == ["x@evil.example"]


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
    obs_id = store.insert_observation(conn, demo_observations[0], demo_observations[0].text)
    loops, _ = detect_loops(LLMClient(s.gemini_api_key.get_secret_value(), s.llm_model),
                            store.get_observation(conn, obs_id), name=s.user_name, email=s.user_email)
    assert len(loops) == 1
    assert loops[0].direction == "i_owe" and loops[0].due_date == date(2026, 10, 21)
