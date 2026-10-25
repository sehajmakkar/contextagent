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

import sqlite_vec

from brain.models import ObservationIn

_MIGRATIONS = sorted(Path(__file__).with_name("migrations").glob("[0-9][0-9][0-9]_*.sql"))
SCHEMA_VERSION = len(_MIGRATIONS)
MAX_DETECT_ATTEMPTS = 3


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(path: Path | str) -> sqlite3.Connection:
    in_memory = str(path) == ":memory:"
    if not in_memory:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    conn = sqlite3.connect(path)
    # sqlite-vec is a compiled extension; allow loading only for the moment we load it.
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate(conn)
    if not in_memory:
        Path(path).chmod(0o600)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply migrations/NNN_*.sql in order. Each one runs, with its version bump, in one transaction.

    Foreign keys are switched off while migrating: a table rebuild (create new → copy → DROP old → rename)
    would otherwise cascade-delete every child row on the DROP. The switch must happen *outside* the
    transaction, because SQLite silently ignores PRAGMA foreign_keys inside one. Integrity is checked after.
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version >= SCHEMA_VERSION:
        return
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        for number, path in enumerate(_MIGRATIONS, start=1):
            if number > version:
                conn.executescript(f"BEGIN;\n{path.read_text()}\nPRAGMA user_version = {number};\nCOMMIT;")
        if broken := conn.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError(f"migration left {len(broken)} dangling foreign key(s): {broken[:3]}")
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def content_hash(obs: ObservationIn) -> str:
    raw = "\0".join([obs.bundle_id, obs.window_title, obs.text])
    return hashlib.sha256(raw.encode()).hexdigest()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def grounded(quote: str, source: str) -> bool:
    """Is the model's quote really in the source? A quote spliced with "..." passes only if every piece is."""
    pieces = [p for p in re.split(r"\.\.\.|…", normalize(quote)) if p.strip(" .,;:")]
    text = normalize(source)
    return bool(pieces) and all(p.strip(" .,;:") in text for p in pieces)


# --- observations ---------------------------------------------------------

def insert_observation(conn: sqlite3.Connection, obs: ObservationIn, source: str = "file") -> int | None:
    """Store an (already redacted) observation. Returns its id, or None if identical content exists."""
    cur = conn.execute(
        """INSERT OR IGNORE INTO observations
           (captured_at, app_name, bundle_id, window_title, url, text, content_hash, source, capture_trigger)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (obs.captured_at.isoformat(), obs.app_name, obs.bundle_id, obs.window_title,
         obs.url, obs.text, content_hash(obs), source, obs.trigger),
    )
    return cur.lastrowid if cur.rowcount else None


def has_content(conn: sqlite3.Connection, obs: ObservationIn) -> bool:
    return conn.execute("SELECT 1 FROM observations WHERE content_hash = ?", (content_hash(obs),)).fetchone() is not None


def get_observation(conn: sqlite3.Connection, obs_id: int) -> sqlite3.Row:
    return conn.execute("SELECT * FROM observations WHERE id = ?", (obs_id,)).fetchone()


def latest_for_window(conn: sqlite3.Connection, bundle_id: str, window_title: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM observations WHERE bundle_id = ? AND window_title = ? ORDER BY id DESC LIMIT 1",
        (bundle_id, window_title),
    ).fetchone()


def unprocessed_observations(conn: sqlite3.Connection, *, include_capture: bool = True,
                             limit: int | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM observations WHERE processed_at IS NULL AND detect_attempts < ?"
    if not include_capture:
        sql += " AND source != 'capture'"
    sql += " ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql, (MAX_DETECT_ATTEMPTS,)).fetchall()


def mark_processed(conn: sqlite3.Connection, obs_id: int) -> None:
    conn.execute("UPDATE observations SET processed_at = ?, detect_error = NULL WHERE id = ?", (now(), obs_id))


def record_detect_failure(conn: sqlite3.Connection, obs_id: int, error: str) -> None:
    conn.execute("UPDATE observations SET detect_attempts = detect_attempts + 1, detect_error = ? WHERE id = ?",
                 (error[:500], obs_id))


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        f"""SELECT
              (SELECT COUNT(*) FROM observations) AS observations,
              (SELECT COUNT(*) FROM observations WHERE source = 'capture') AS captured,
              (SELECT COUNT(*) FROM episodes WHERE processed_at IS NULL
                                             AND process_attempts < {MAX_DETECT_ATTEMPTS}) AS pending,
              (SELECT COUNT(*) FROM episodes WHERE processed_at IS NULL
                                             AND process_attempts >= {MAX_DETECT_ATTEMPTS}) AS failed,
              (SELECT COUNT(*) FROM loops WHERE state = 'open') AS open_loops,
              (SELECT COUNT(*) FROM episodes) AS episodes,
              (SELECT COUNT(*) FROM memories) AS memories"""
    ).fetchone()
    return dict(row)


# --- loops ----------------------------------------------------------------

def create_loop(conn: sqlite3.Connection, *, observation_id: int, evidence_quote: str, **fields: Any) -> int:
    ts = now()
    due = fields.get("due_date")
    source_app = conn.execute("SELECT app_name FROM observations WHERE id = ?", (observation_id,)).fetchone()
    cur = conn.execute(
        """INSERT INTO loops (title, direction, counterparty, counterparty_email, deliverable, note,
                              due_date, confidence, source_app, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (fields["title"], fields["direction"], fields["counterparty"], fields.get("counterparty_email"),
         fields["deliverable"], fields.get("note"), due.isoformat() if due else None, fields["confidence"],
         source_app["app_name"] if source_app else None, ts, ts),
    )
    loop_id = cur.lastrowid
    add_evidence(conn, loop_id, observation_id, evidence_quote, "created")
    # Local import: lifecycle imports store.now, so importing it at module level would be circular.
    from brain.loops.lifecycle import record_created
    record_created(conn, loop_id, reason="detected", observation_id=observation_id,
                   confidence=fields["confidence"])
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


# --- memories --------------------------------------------------------------

def insert_memory(conn: sqlite3.Connection, *, episode_id: int, observation_id: int | None, kind: str,
                  text: str, quote: str, entities: str, happened_at: str) -> int:
    return conn.execute(
        """INSERT INTO memories (episode_id, observation_id, kind, text, quote, entities, happened_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (episode_id, observation_id, kind, text, quote, entities, happened_at, now()),
    ).lastrowid


# --- audit log ------------------------------------------------------------

def log_action(conn: sqlite3.Connection, *, loop_id: int | None, kind: str, status: str,
               input: dict, output: dict | None, model: str | None = None,
               prompt_tokens: int | None = None, output_tokens: int | None = None,
               thinking_tokens: int | None = None, parent_id: int | None = None) -> int:
    ts = now()
    cur = conn.execute(
        """INSERT INTO actions (loop_id, kind, status, input_json, output_json, model,
                                prompt_tokens, output_tokens, thinking_tokens, parent_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (loop_id, kind, status, json.dumps(input, default=str),
         json.dumps(output, default=str) if output is not None else None,
         model, prompt_tokens, output_tokens, thinking_tokens, parent_id, ts, ts),
    )
    return cur.lastrowid


def update_action(conn: sqlite3.Connection, action_id: int, *, status: str, output: dict) -> None:
    conn.execute(
        """UPDATE actions SET status = ?, output_json = ?, updated_at = ?,
               prompt_tokens = COALESCE(?, prompt_tokens), output_tokens = COALESCE(?, output_tokens),
               thinking_tokens = COALESCE(?, thinking_tokens) WHERE id = ?""",
        (status, json.dumps(output, default=str), now(), output.get("prompt_tokens"), output.get("output_tokens"),
         output.get("thinking_tokens"), action_id),
    )
