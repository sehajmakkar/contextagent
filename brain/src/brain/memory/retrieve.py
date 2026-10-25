"""Find the memories that answer a question: BM25, vector, or hybrid with Reciprocal Rank Fusion (ADR-009)."""

import re
import sqlite3
from dataclasses import dataclass
from typing import Literal

from brain.config import Settings
from brain.llm.client import LLMClient
from brain.memory.embed import QUERY_PREFIX, nearest, vector_for

Mode = Literal["bm25", "vector", "hybrid", "hybrid_recency"]

RRF_K = 60          # the standard constant: damps the gap between rank 1 and rank 2
CANDIDATES = 50     # how deep each list goes before fusion
RECENCY_WEIGHT = 0.5

_STOPWORDS = {"a", "an", "the", "of", "to", "in", "on", "for", "and", "or", "is", "are", "was", "were", "be", "did",
              "do", "does", "what", "which", "who", "when", "where", "how", "i", "me", "my", "we", "our", "you",
              "your", "it", "that", "this", "with", "about", "from", "by", "at", "as", "have", "has", "had"}


@dataclass(frozen=True)
class Hit:
    memory_id: int
    score: float
    text: str
    kind: str
    happened_at: str
    app_name: str
    window_title: str


def search(conn: sqlite3.Connection, llm: LLMClient | None, settings: Settings, query: str,
           k: int = 5, mode: Mode = "hybrid") -> list[Hit]:
    if mode == "bm25":
        ranked = [(i, 1.0 / (RRF_K + r)) for r, i in enumerate(bm25_ids(conn, query, CANDIDATES), start=1)]
    elif mode == "vector":
        ranked = [(i, 1.0 / (RRF_K + r)) for r, i in enumerate(vector_ids(conn, llm, settings, query, CANDIDATES), start=1)]
    else:
        lists = [bm25_ids(conn, query, CANDIDATES), vector_ids(conn, llm, settings, query, CANDIDATES)]
        weights = [1.0, 1.0]
        if mode == "hybrid_recency":
            lists.append(by_recency(conn, {i for lst in lists for i in lst}))
            weights.append(RECENCY_WEIGHT)
        ranked = rrf(lists, weights)
    return _hits(conn, ranked[:k])


def rrf(lists: list[list[int]], weights: list[float] | None = None) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: score(d) = Σ w_i / (RRF_K + rank_i(d)). Uses ranks only, never raw scores,
    so BM25 scores (unbounded) and cosine distances (0–2) never have to be put on one scale."""
    weights = weights or [1.0] * len(lists)
    scores: dict[int, float] = {}
    for ranked, weight in zip(lists, weights):
        for rank, item in enumerate(ranked, start=1):
            scores[item] = scores.get(item, 0.0) + weight / (RRF_K + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])


def fts_query(query: str) -> str | None:
    """User text → a safe FTS5 query: words OR-ed together, each quoted so punctuation can't break the syntax."""
    words = [w for w in re.findall(r"\w+", query.lower()) if w not in _STOPWORDS]
    return " OR ".join(f'"{w}"' for w in dict.fromkeys(words)) or None


def bm25_ids(conn: sqlite3.Connection, query: str, n: int) -> list[int]:
    if not (match := fts_query(query)):
        return []
    rows = conn.execute(
        """SELECT m.id FROM memories_fts f JOIN memories m ON m.id = f.rowid
           WHERE memories_fts MATCH ? AND m.duplicate_of IS NULL ORDER BY bm25(memories_fts) LIMIT ?""",
        (match, n),
    ).fetchall()
    return [r["id"] for r in rows]


def vector_ids(conn: sqlite3.Connection, llm: LLMClient, settings: Settings, query: str, n: int) -> list[int]:
    vector, _ = vector_for(conn, llm, QUERY_PREFIX.format(text=query), settings)
    return [r["memory_id"] for r in nearest(conn, vector, k=n)]


def by_recency(conn: sqlite3.Connection, ids: set[int]) -> list[int]:
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = conn.execute(f"SELECT id FROM memories WHERE id IN ({marks}) ORDER BY happened_at DESC", tuple(ids))
    return [r["id"] for r in rows]


def _hits(conn: sqlite3.Connection, ranked: list[tuple[int, float]]) -> list[Hit]:
    hits = []
    for memory_id, score in ranked:
        r = conn.execute(
            """SELECT m.text, m.kind, m.happened_at, e.app_name, e.window_title FROM memories m
               JOIN episodes e ON e.id = m.episode_id WHERE m.id = ?""", (memory_id,)).fetchone()
        hits.append(Hit(memory_id, score, r["text"], r["kind"], r["happened_at"], r["app_name"], r["window_title"]))
    return hits
