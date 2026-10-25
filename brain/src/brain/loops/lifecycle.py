"""The open-loop state machine (ADR-040). Every change is validated and recorded with who made it and why.

    open ──► acting ──► awaiting_approval ──► closed        (Phase 5: the agent drafts, you approve)
     │  ▲       │                 │            │  ▲
     │  └───────┘ (agent failed)  └─► open     │  │ reopen: new evidence says it isn't done
     ├──────────────────────────────────────► closed       (you resolved it, or evidence shows it's done)
     └──────────────────────────────────────► dismissed    (not a real loop: feeds the eval)
"""

import sqlite3
from typing import Literal

from brain.db.store import now

State = Literal["open", "acting", "awaiting_approval", "closed", "dismissed"]
Actor = Literal["system", "user", "agent"]

ALLOWED: dict[str, set[str]] = {
    "open": {"acting", "closed", "dismissed"},
    "acting": {"awaiting_approval", "open", "closed"},
    "awaiting_approval": {"closed", "open", "dismissed"},
    "closed": {"open"},
    "dismissed": {"open"},
}
# Who closed it decides how much to trust it: the UI shows "inferred" closes differently from yours.
CLOSED_REASON = {"user": "user", "system": "inferred", "agent": "agent"}


class InvalidTransition(ValueError):
    pass


def transition(conn: sqlite3.Connection, loop_id: int, to_state: State, *, actor: Actor, reason: str,
               observation_id: int | None = None, confidence: float | None = None) -> None:
    row = conn.execute("SELECT state FROM loops WHERE id = ?", (loop_id,)).fetchone()
    if row is None:
        raise InvalidTransition(f"no loop #{loop_id}")
    current = row["state"]
    if to_state not in ALLOWED[current]:
        raise InvalidTransition(f"loop #{loop_id}: {current} → {to_state} is not allowed")
    ts = now()
    closed = to_state == "closed"
    conn.execute(
        "UPDATE loops SET state = ?, updated_at = ?, closed_reason = ?, closed_at = ? WHERE id = ?",
        (to_state, ts, CLOSED_REASON[actor] if closed else None, ts if closed else None, loop_id),
    )
    _record(conn, loop_id, current, to_state, actor, reason, observation_id, confidence)


def record_created(conn: sqlite3.Connection, loop_id: int, *, reason: str, observation_id: int | None,
                   confidence: float | None) -> None:
    _record(conn, loop_id, None, "open", "system", reason, observation_id, confidence)


def history(conn: sqlite3.Connection, loop_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM loop_transitions WHERE loop_id = ? ORDER BY id", (loop_id,)).fetchall()


def _record(conn, loop_id, from_state, to_state, actor, reason, observation_id, confidence) -> None:
    conn.execute(
        """INSERT INTO loop_transitions (loop_id, from_state, to_state, actor, reason, observation_id, confidence,
                                         created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (loop_id, from_state, to_state, actor, reason, observation_id, confidence, now()),
    )
