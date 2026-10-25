"""Process one closed episode: local gate → memories → loops, persisted in one transaction (ADR-033/034).

Shared by the CLI and the API worker. Runs per *episode* (one visit to one window), not per snapshot,
so a 30-snapshot visit costs the same LLM calls as a 1-snapshot visit.
"""

import json
import sqlite3
from dataclasses import dataclass, field

from brain import episodes
from brain.config import Settings
from brain.db import store
from brain.llm.client import LLMClient, LLMError, QuotaExhausted, Usage
from brain.loops.detect import detect_loops
from brain.memory.extract import extract_memories

MIN_EPISODE_CHARS = 80   # local gate: below this there's nothing to extract, so don't pay for a call
MAX_ATTEMPTS = 3


@dataclass
class DetectOutcome:
    usages: list[Usage] = field(default_factory=list)
    created: list[tuple[int, str, float]] = field(default_factory=list)  # (loop_id, title, confidence)
    merged: list[int] = field(default_factory=list)
    memories: list[str] = field(default_factory=list)
    skipped: str | None = None
    error: str | None = None
    quota_exhausted: bool = False


def pending(conn: sqlite3.Connection, settings: Settings, limit: int | None = None) -> list[sqlite3.Row]:
    """Closed, unprocessed episodes. Live captures only when the tier allows it (ADR-027)."""
    with conn:
        episodes.close_stale(conn)
    sql = ("SELECT * FROM episodes WHERE closed_at IS NOT NULL AND processed_at IS NULL"
           f" AND process_attempts < {MAX_ATTEMPTS}")
    if not settings.live_detection_allowed:
        sql += " AND source != 'capture'"
    sql += " ORDER BY id" + (f" LIMIT {int(limit)}" if limit else "")
    return conn.execute(sql).fetchall()


def held_back(conn: sqlite3.Connection, settings: Settings) -> int:
    """Live-capture episodes waiting because the free tier may not see real screen text (ADR-027)."""
    if settings.live_detection_allowed:
        return 0
    return conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE processed_at IS NULL AND source = 'capture'"
    ).fetchone()[0]


def process(conn: sqlite3.Connection, llm: LLMClient, episode: sqlite3.Row, settings: Settings) -> DetectOutcome:
    if len(episode["text"]) < MIN_EPISODE_CHARS:
        with conn:
            _finish(conn, episode, [], skipped="too little text")
        return DetectOutcome(skipped="too little text")

    outcome = DetectOutcome()
    try:
        memories, usage = extract_memories(llm, episode, name=settings.user_name)
        outcome.usages.append(usage)
        # Loop detection reads the episode exactly like an observation: same prompt, same grounding check.
        as_observation = {"captured_at": episode["started_at"], "app_name": episode["app_name"],
                          "window_title": episode["window_title"], "url": episode["url"], "text": episode["text"]}
        candidates, usage = detect_loops(llm, as_observation, name=settings.user_name, email=settings.user_email)
        outcome.usages.append(usage)
    except QuotaExhausted as e:
        # Not the episode's fault: don't spend one of its attempts. The caller stops the batch.
        return DetectOutcome(error=str(e), quota_exhausted=True)
    except LLMError as e:
        with conn:
            conn.execute("UPDATE episodes SET process_attempts = process_attempts + 1, process_error = ? WHERE id = ?",
                         (str(e)[:500], episode["id"]))
        return DetectOutcome(error=str(e))

    with conn:  # memories + loops + processed flags land together, or not at all
        for m in memories:
            store.insert_memory(conn, episode_id=episode["id"], observation_id=_source_of(conn, episode, m.quote),
                                kind=m.kind, text=m.text, quote=m.quote, entities=json.dumps(m.entities),
                                happened_at=episode["started_at"])
            outcome.memories.append(m.text)
        for c in candidates:
            obs_id = _source_of(conn, episode, c.evidence_quote)
            existing = store.find_open_loop_by_quote(conn, c.evidence_quote)
            if existing:
                store.add_evidence(conn, existing, obs_id, c.evidence_quote, "progress")
                outcome.merged.append(existing)
            else:
                loop_id = store.create_loop(conn, observation_id=obs_id, **c.model_dump())
                outcome.created.append((loop_id, c.title, c.confidence))
        _finish(conn, episode, outcome.usages)
    return outcome


def _source_of(conn: sqlite3.Connection, episode: sqlite3.Row, quote: str) -> int:
    """Provenance: the first snapshot in the episode whose text contains the quote (else the last one)."""
    rows = conn.execute("SELECT id, text FROM observations WHERE episode_id = ? ORDER BY id", (episode["id"],)).fetchall()
    target = store.normalize(quote)
    return next((r["id"] for r in rows if target in store.normalize(r["text"])), rows[-1]["id"])


def _finish(conn: sqlite3.Connection, episode: sqlite3.Row, usages: list[Usage], skipped: str | None = None) -> None:
    conn.execute(
        """UPDATE episodes SET processed_at = ?, skipped_reason = ?, process_error = NULL, llm_calls = ?,
                               prompt_tokens = ?, output_tokens = ?, thinking_tokens = ? WHERE id = ?""",
        (store.now(), skipped, len(usages), sum(u.prompt_tokens for u in usages),
         sum(u.output_tokens for u in usages), sum(u.thinking_tokens for u in usages), episode["id"]),
    )
    conn.execute("UPDATE observations SET processed_at = ? WHERE episode_id = ?", (store.now(), episode["id"]))
