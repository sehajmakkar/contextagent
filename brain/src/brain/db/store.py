"""SQLite access. The brain is the only process that opens the database (ADR-004).

Functions here don't commit; callers wrap a unit of work in `with conn:` so it
lands atomically (e.g. an observation plus the loops found in it).
"""

import hashlib
import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from brain.models import ObservationIn

SCHEMA_VERSION = 1
_SCHEMA = Path(__file__).with_name("schema.sql")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(path: Path | str) -> sqlite3.Connection:
    in_memory = str(path) == ":memory:"
    if not in_memory:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate(conn)
    if not in_memory:
        Path(path).chmod(0o600)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        conn.executescript(_SCHEMA.read_text())
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def content_hash(obs: ObservationIn) -> str:
    raw = "\0".join([obs.bundle_id, obs.window_title, obs.text])
    return hashlib.sha256(raw.encode()).hexdigest()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


# --- observations ---------------------------------------------------------

def insert_observation(conn: sqlite3.Connection, obs: ObservationIn, redacted_text: str) -> int | None:
    """Store an observation. Returns its id, or None if identical content was already stored."""
    cur = conn.execute(
        """INSERT OR IGNORE INTO observations
           (captured_at, app_name, bundle_id, window_title, url, text, content_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (obs.captured_at.isoformat(), obs.app_name, obs.bundle_id, obs.window_title,
         obs.url, redacted_text, content_hash(obs)),
    )
    return cur.lastrowid if cur.rowcount else None


def get_observation(conn: sqlite3.Connection, obs_id: int) -> sqlite3.Row:
    return conn.execute("SELECT * FROM observations WHERE id = ?", (obs_id,)).fetchone()


def unprocessed_observations(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM observations WHERE processed_at IS NULL ORDER BY captured_at").fetchall()


def mark_processed(conn: sqlite3.Connection, obs_id: int) -> None:
    conn.execute("UPDATE observations SET processed_at = ? WHERE id = ?", (now(), obs_id))


# --- loops ----------------------------------------------------------------

def create_loop(conn: sqlite3.Connection, *, observation_id: int, evidence_quote: str, **fields: Any) -> int:
    ts = now()
    due = fields.get("due_date")
    cur = conn.execute(
        """INSERT INTO loops (title, direction, counterparty, counterparty_email, deliverable,
                              due_date, confidence, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (fields["title"], fields["direction"], fields["counterparty"], fields.get("counterparty_email"),
         fields["deliverable"], due.isoformat() if due else None, fields["confidence"], ts, ts),
    )
    loop_id = cur.lastrowid
    add_evidence(conn, loop_id, observation_id, evidence_quote, "created")
    return loop_id


def add_evidence(conn: sqlite3.Connection, loop_id: int, observation_id: int, quote: str, kind: str) -> None:
    conn.execute(
        "INSERT INTO loop_evidence (loop_id, observation_id, quote, kind, created_at) VALUES (?, ?, ?, ?, ?)",
        (loop_id, observation_id, quote, kind, now()),
    )
    conn.execute("UPDATE loops SET updated_at = ? WHERE id = ?", (now(), loop_id))


def find_open_loop_by_quote(conn: sqlite3.Connection, quote: str) -> int | None:
    """Exact-quote dedupe: the same sentence seen again belongs to the same loop.

    Phase 4 replaces this with semantic matching (embeddings + LLM judge).
    """
    target = normalize(quote)
    rows = conn.execute(
        """SELECT e.loop_id, e.quote FROM loop_evidence e
           JOIN loops l ON l.id = e.loop_id WHERE l.state = 'open'"""
    ).fetchall()
    return next((r["loop_id"] for r in rows if normalize(r["quote"]) == target), None)


def list_loops(conn: sqlite3.Connection, state: str | None = "open") -> list[sqlite3.Row]:
    sql = """SELECT l.*, COUNT(e.id) AS evidence_count FROM loops l
             LEFT JOIN loop_evidence e ON e.loop_id = l.id"""
    params: tuple = ()
    if state:
        sql += " WHERE l.state = ?"
        params = (state,)
    sql += " GROUP BY l.id ORDER BY l.due_date IS NULL, l.due_date, l.id"
    return conn.execute(sql, params).fetchall()


def get_loop(conn: sqlite3.Connection, loop_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM loops WHERE id = ?", (loop_id,)).fetchone()


def get_evidence(conn: sqlite3.Connection, loop_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT e.quote, e.kind, o.id AS observation_id, o.captured_at, o.app_name,
                  o.window_title, o.url, o.text
           FROM loop_evidence e JOIN observations o ON o.id = e.observation_id
           WHERE e.loop_id = ? ORDER BY o.captured_at""",
        (loop_id,),
    ).fetchall()


# --- audit log ------------------------------------------------------------

def log_action(conn: sqlite3.Connection, *, loop_id: int | None, kind: str, status: str,
               input: dict, output: dict | None, model: str | None = None,
               prompt_tokens: int | None = None, output_tokens: int | None = None,
               thinking_tokens: int | None = None) -> int:
    cur = conn.execute(
        """INSERT INTO actions (loop_id, kind, status, input_json, output_json, model,
                                prompt_tokens, output_tokens, thinking_tokens, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (loop_id, kind, status, json.dumps(input, default=str),
         json.dumps(output, default=str) if output is not None else None,
         model, prompt_tokens, output_tokens, thinking_tokens, now()),
    )
    return cur.lastrowid
