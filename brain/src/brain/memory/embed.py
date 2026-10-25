"""Embed memories into the local vector index, with a cache and near-duplicate detection (ADR-020/038)."""

import hashlib
import re
import sqlite3
from dataclasses import dataclass

import sqlite_vec

from brain.config import Settings
from brain.db.store import now
from brain.llm.client import LLMClient

# gemini-embedding-2 has no task_type: the task goes into the text itself (Google's recommended prefixes).
DOCUMENT_PREFIX = "title: none | text: {text}"
QUERY_PREFIX = "task: search result | query: {text}"

# Cosine distance (0 = identical) under which a new memory may be a restatement of an existing one.
# Calibrated on the fixture week: a true restatement was 0.062, but two *different* lease facts
# ("lease ends Nov 30" / "confirm renewal by Oct 31") were 0.094. The gap is thin, so we also require
# the same kind, and duplicates are only marked (reversible), never deleted. See challenges.md #17.
DUPLICATE_DISTANCE = 0.075


@dataclass
class EmbedOutcome:
    embedded: int = 0
    duplicates: int = 0
    api_calls: int = 0


def vector_for(conn: sqlite3.Connection, llm: LLMClient, text: str, settings: Settings) -> tuple[bytes, bool]:
    """The packed float32 vector for `text`, from the cache if we've seen it. Returns (vector, was_api_call)."""
    key = hashlib.sha256(f"{settings.embed_model}\0{settings.embed_dims}\0{text}".encode()).hexdigest()
    if row := conn.execute("SELECT vector FROM embedding_cache WHERE content_hash = ?", (key,)).fetchone():
        return row["vector"], False
    blob = sqlite_vec.serialize_float32(llm.embed(text, model=settings.embed_model, dims=settings.embed_dims))
    with conn:
        conn.execute("INSERT OR IGNORE INTO embedding_cache (content_hash, vector, created_at) VALUES (?, ?, ?)",
                     (key, blob, now()))
    return blob, True


def nearest(conn: sqlite3.Connection, vector: bytes, k: int = 1) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT memory_id, distance FROM memory_vectors WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (vector, k),
    ).fetchall()


def embed_memories(conn: sqlite3.Connection, llm: LLMClient, settings: Settings) -> EmbedOutcome:
    """Embed every memory that has no vector yet. A near-copy of an indexed memory is marked, not indexed."""
    outcome = EmbedOutcome()
    todo = conn.execute(
        """SELECT m.id, m.text, m.kind FROM memories m LEFT JOIN memory_embeddings e ON e.memory_id = m.id
           WHERE e.memory_id IS NULL AND m.duplicate_of IS NULL ORDER BY m.id"""
    ).fetchall()
    for m in todo:
        # The network call happens outside the write transaction, so we never hold the DB lock while waiting.
        vector, called = vector_for(conn, llm, DOCUMENT_PREFIX.format(text=m["text"]), settings)
        outcome.api_calls += called
        with conn:
            close = nearest(conn, vector)
            if close and close[0]["distance"] <= DUPLICATE_DISTANCE and is_restatement(conn, m, close[0]["memory_id"]):
                conn.execute("UPDATE memories SET duplicate_of = ? WHERE id = ?", (close[0]["memory_id"], m["id"]))
                outcome.duplicates += 1
                continue
            conn.execute("INSERT INTO memory_vectors (memory_id, embedding) VALUES (?, ?)", (m["id"], vector))
            conn.execute("INSERT INTO memory_embeddings (memory_id, model, dims, created_at) VALUES (?, ?, ?, ?)",
                         (m["id"], settings.embed_model, settings.embed_dims, now()))
            outcome.embedded += 1
    return outcome


def is_restatement(conn: sqlite3.Connection, new: sqlite3.Row, existing_id: int) -> bool:
    """Vectors blur exact tokens (Q2 vs Q3, 58.9% vs 63.6%), so closeness alone isn't enough (challenge #17).
    Also require the same kind, and that one memory's numbers are contained in the other's: a restatement
    may add a resolved date ({3} ⊂ {3, 21, 2026}), but different figures are a different fact."""
    old = conn.execute("SELECT kind, text FROM memories WHERE id = ?", (existing_id,)).fetchone()
    if old["kind"] != new["kind"]:
        return False
    a, b = numbers(old["text"]), numbers(new["text"])
    return a <= b or b <= a


def numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d+(?:[.,]\d+)*", text)}

