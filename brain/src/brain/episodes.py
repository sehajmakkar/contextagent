"""Episodes: one visit to one window. Many near-identical snapshots collapse into one text (ADR-033).

An observation joins the open episode for its window if it arrives within EPISODE_GAP of the last one;
otherwise it starts a new episode. An episode closes once EPISODE_GAP passes with no new snapshot,
and only closed episodes are sent for extraction, so we extract a visit once, after it's over.
"""

import re
import sqlite3
from datetime import datetime, timedelta

from brain.db.store import now

EPISODE_GAP = timedelta(minutes=5)


def assign(conn: sqlite3.Connection, obs_id: int) -> int:
    """Attach a stored observation to its window's open episode, or start a new one."""
    obs = conn.execute("SELECT * FROM observations WHERE id = ?", (obs_id,)).fetchone()
    episode = conn.execute(
        """SELECT * FROM episodes WHERE bundle_id = ? AND window_title = ? AND source = ? AND closed_at IS NULL
           ORDER BY id DESC LIMIT 1""",
        (obs["bundle_id"], obs["window_title"], obs["source"]),
    ).fetchone()
    at = datetime.fromisoformat(obs["captured_at"])

    if episode and at - datetime.fromisoformat(episode["ended_at"]) <= EPISODE_GAP:
        conn.execute(
            """UPDATE episodes SET text = ?, ended_at = ?, observation_count = observation_count + 1,
                                   raw_chars = raw_chars + ?, url = COALESCE(?, url) WHERE id = ?""",
            (merge_lines(episode["text"], obs["text"]), obs["captured_at"], len(obs["text"]), obs["url"], episode["id"]),
        )
        episode_id = episode["id"]
    else:
        if episode:  # same window, but after a long gap: the old visit is over
            conn.execute("UPDATE episodes SET closed_at = ? WHERE id = ?", (now(), episode["id"]))
        episode_id = conn.execute(
            """INSERT INTO episodes (source, app_name, bundle_id, window_title, url, started_at, ended_at, text, raw_chars)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (obs["source"], obs["app_name"], obs["bundle_id"], obs["window_title"], obs["url"],
             obs["captured_at"], obs["captured_at"], dedupe_lines(obs["text"]), len(obs["text"])),
        ).lastrowid
    conn.execute("UPDATE observations SET episode_id = ? WHERE id = ?", (episode_id, obs_id))
    return episode_id


def backfill(conn: sqlite3.Connection) -> int:
    """Group observations stored before episodes existed. Purely local: nothing is sent anywhere."""
    ids = [r["id"] for r in conn.execute("SELECT id FROM observations WHERE episode_id IS NULL ORDER BY id")]
    for obs_id in ids:
        assign(conn, obs_id)
    return len(ids)


def end_visit(conn: sqlite3.Connection, bundle_id: str, window_title: str) -> int | None:
    """The app saw you leave this window: the visit is over, so close its episode now instead of waiting
    EPISODE_GAP. That's what makes a loop appear seconds after you switch away (ADR-051)."""
    row = conn.execute("""SELECT id FROM episodes WHERE bundle_id = ? AND window_title = ? AND source = 'capture'
                          AND closed_at IS NULL ORDER BY id DESC LIMIT 1""", (bundle_id, window_title)).fetchone()
    if row:
        conn.execute("UPDATE episodes SET closed_at = ? WHERE id = ?", (now(), row["id"]))
        return row["id"]
    return None


def close_stale(conn: sqlite3.Connection, current: datetime | None = None) -> int:
    """Close episodes whose window hasn't produced a snapshot for EPISODE_GAP. Returns how many closed."""
    current = current or datetime.now().astimezone()
    stale = [r["id"] for r in conn.execute("SELECT id, ended_at FROM episodes WHERE closed_at IS NULL")
             if current - datetime.fromisoformat(r["ended_at"]) > EPISODE_GAP]
    conn.executemany("UPDATE episodes SET closed_at = ? WHERE id = ?", [(now(), i) for i in stale])
    return len(stale)


def merge_lines(existing: str, new: str) -> str:
    """Append the lines of `new` not already in `existing` (digits masked), keeping first-seen order."""
    seen = {_mask(line) for line in existing.splitlines() if line.strip()}
    added = []
    for line in new.splitlines():
        key = _mask(line)
        if line.strip() and key not in seen:
            seen.add(key)
            added.append(line)
    return "\n".join([existing, *added]) if added else existing


def dedupe_lines(text: str) -> str:
    return merge_lines("", text).lstrip("\n")


def _mask(line: str) -> str:
    return re.sub(r"\d+", "#", " ".join(line.lower().split()))
