"""Is this new loop one we already track? Embeddings find look-alikes; an LLM judge decides (ADR-041).

Vectors alone can't decide: "send Priya the Q3 numbers" and "send Priya the Q2 numbers" are near-identical
as embeddings (challenge #17). So a vector match only nominates candidates, and a small structured
"same commitment?" call makes the decision. The judge runs only for close pairs, so it's rare and cheap.
"""

import sqlite3

from pydantic import BaseModel, Field

from brain.config import Settings
from brain.llm.client import LLMClient, Usage
from brain.loops.detect import LoopCandidate
from brain.memory.embed import DOCUMENT_PREFIX, vector_for

# Cosine distance under which two loops are worth asking the judge about. Calibrated on real loops:
# paraphrases of one loop sat at 0.022 / 0.041 / 0.105; the closest *different* loops at 0.164+ (ADR-043).
JUDGE_DISTANCE = 0.14
MAX_JUDGE_CALLS = 2
ACTIVE = ("open", "acting", "awaiting_approval")


class SameCommitment(BaseModel):
    same: bool = Field(description="True only if both describe the same promise: same people, same thing owed.")
    reason: str = Field(description="One short sentence.")


JUDGE_SYSTEM = """\
You decide whether two open-loop descriptions refer to the same commitment.
Same commitment = the same people and the same deliverable, even if worded differently or with a new deadline.
Different = a different deliverable, period, version, amount or person (Q2 vs Q3 numbers, PR #482 vs #519).
"""


def loop_text(direction: str, counterparty: str, title: str, deliverable: str) -> str:
    return DOCUMENT_PREFIX.format(text=f"{direction} {counterparty}: {title} ({deliverable})")


def find_duplicate(conn: sqlite3.Connection, llm: LLMClient, settings: Settings,
                   c: LoopCandidate) -> tuple[int | None, bytes, list[Usage]]:
    """Returns (id of the tracked loop this duplicates or None, the candidate's vector, judge usages)."""
    vector, _ = vector_for(conn, llm, loop_text(c.direction, c.counterparty, c.title, c.deliverable), settings)
    marks = ",".join("?" * len(ACTIVE))
    near = conn.execute(
        f"""SELECT v.loop_id, v.distance, l.title, l.direction, l.counterparty, l.deliverable
            FROM (SELECT loop_id, distance FROM loop_vectors WHERE embedding MATCH ? AND k = 5) v
            JOIN loops l ON l.id = v.loop_id WHERE l.state IN ({marks}) ORDER BY v.distance""",
        (vector, *ACTIVE),
    ).fetchall()
    usages = []
    for n in near[:MAX_JUDGE_CALLS]:
        if n["distance"] > JUDGE_DISTANCE:
            break
        verdict, usage = llm.generate_structured(
            schema=SameCommitment, system=JUDGE_SYSTEM, thinking_level="low",
            prompt=(f"A: {n['direction']} | {n['counterparty']} | {n['title']} | owed: {n['deliverable']}\n"
                    f"B: {c.direction} | {c.counterparty} | {c.title} | owed: {c.deliverable}"),
        )
        usages.append(usage)
        if verdict.same:
            return n["loop_id"], vector, usages
    return None, vector, usages


def index(conn: sqlite3.Connection, loop_id: int, vector: bytes) -> None:
    conn.execute("INSERT OR REPLACE INTO loop_vectors (loop_id, embedding) VALUES (?, ?)", (loop_id, vector))


def related_open_loops(conn: sqlite3.Connection, episode: sqlite3.Row, limit: int = 10) -> list[dict]:
    """Tracked loops this screen may be about: the counterparty is named in it, or it's the same window
    the loop was seen in (a reply in the same thread). Cheap and local: no embedding call."""
    text = episode["text"].lower()
    marks = ",".join("?" * len(ACTIVE))
    rows = conn.execute(
        f"""SELECT l.*, EXISTS(SELECT 1 FROM loop_evidence e JOIN observations o ON o.id = e.observation_id
                               WHERE e.loop_id = l.id AND o.window_title = ?) AS same_window
            FROM loops l WHERE l.state IN ({marks}) ORDER BY l.updated_at DESC""",
        (episode["window_title"], *ACTIVE),
    ).fetchall()
    related = []
    for r in rows:
        first = r["counterparty"].split()[0].lower() if r["counterparty"] else ""
        if r["same_window"] or (len(first) > 2 and first != "self" and first in text):
            related.append({k: r[k] for k in ("id", "title", "direction", "counterparty", "deliverable")})
    return related[:limit]
