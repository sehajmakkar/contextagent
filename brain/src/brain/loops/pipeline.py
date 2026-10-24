"""Run loop detection on one stored observation and persist the result. Shared by the CLI and the API worker."""

import sqlite3
from dataclasses import dataclass, field

from brain.config import Settings
from brain.db import store
from brain.llm.client import LLMClient, LLMError, Usage
from brain.loops.detect import detect_loops


@dataclass
class DetectOutcome:
    usage: Usage | None = None
    created: list[tuple[int, str, float]] = field(default_factory=list)  # (loop_id, title, confidence)
    merged: list[int] = field(default_factory=list)
    error: str | None = None


def pending(conn: sqlite3.Connection, settings: Settings, limit: int | None = None) -> list[sqlite3.Row]:
    return store.unprocessed_observations(conn, include_capture=settings.live_detection_allowed, limit=limit)


def held_back(conn: sqlite3.Connection, settings: Settings) -> int:
    """Live captures waiting because the free tier may not see real screen text (ADR-027)."""
    if settings.live_detection_allowed:
        return 0
    return conn.execute(
        "SELECT COUNT(*) FROM observations WHERE processed_at IS NULL AND source = 'capture'"
    ).fetchone()[0]


def process(conn: sqlite3.Connection, llm: LLMClient, obs: sqlite3.Row, settings: Settings) -> DetectOutcome:
    try:
        candidates, usage = detect_loops(llm, obs, name=settings.user_name, email=settings.user_email)
    except LLMError as e:
        with conn:
            store.record_detect_failure(conn, obs["id"], str(e))
        return DetectOutcome(error=str(e))

    outcome = DetectOutcome(usage=usage)
    with conn:  # one transaction per observation: its loops + processed flag, or nothing
        for c in candidates:
            existing = store.find_open_loop_by_quote(conn, c.evidence_quote)
            if existing:
                store.add_evidence(conn, existing, obs["id"], c.evidence_quote, "progress")
                outcome.merged.append(existing)
            else:
                loop_id = store.create_loop(conn, observation_id=obs["id"], **c.model_dump())
                outcome.created.append((loop_id, c.title, c.confidence))
        store.mark_processed(conn, obs["id"])
    return outcome
