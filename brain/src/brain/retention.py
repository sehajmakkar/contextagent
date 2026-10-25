"""Retention: raw screen text is short-lived; distilled memories are what we keep (ADR-035)."""

import sqlite3
from datetime import datetime, timedelta

from brain.db.store import now

RAW_RETENTION_DAYS = 7


def purge(conn: sqlite3.Connection, older_than_days: int = RAW_RETENTION_DAYS, current: datetime | None = None) -> int:
    """Erase the text of processed snapshots older than the cutoff. Rows stay so loop evidence keeps its link.

    Unprocessed snapshots are kept, so nothing is erased before it has been distilled.
    """
    cutoff = (current or datetime.now().astimezone()) - timedelta(days=older_than_days)
    old = [r["id"] for r in conn.execute(
        "SELECT id, captured_at FROM observations WHERE processed_at IS NOT NULL AND purged_at IS NULL")
        if datetime.fromisoformat(r["captured_at"]) < cutoff]
    conn.executemany("UPDATE observations SET text = '', purged_at = ? WHERE id = ?", [(now(), i) for i in old])
    return len(old)
