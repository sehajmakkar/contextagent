"""One path for every observation, from a fixture file or the Swift app: redact → dedupe → store."""

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from brain import episodes
from brain.db import store
from brain.models import ObservationIn
from brain.redact import redact

NEAR_DUPLICATE_WINDOW = timedelta(minutes=30)


@dataclass
class IngestResult:
    status: Literal["stored", "duplicate", "near_duplicate"]
    observation_id: int | None = None
    new_lines: int | None = None
    redactions: Counter[str] = field(default_factory=Counter)


def ingest(conn: sqlite3.Connection, obs: ObservationIn, source: Literal["file", "capture"]) -> IngestResult:
    text, redactions = redact(obs.text)
    clean = obs.model_copy(update={"text": text})

    if store.has_content(conn, clean):
        return IngestResult("duplicate", redactions=redactions)

    previous = store.latest_for_window(conn, clean.bundle_id, clean.window_title)
    if previous is not None and _within_window(previous["captured_at"], clean.captured_at):
        if not new_lines(previous["text"], clean.text):
            return IngestResult("near_duplicate", previous["id"], 0, redactions)

    obs_id = store.insert_observation(conn, clean, source=source)
    episodes.assign(conn, obs_id)
    return IngestResult("stored", obs_id, redactions=redactions)


def new_lines(old: str, new: str) -> list[str]:
    """Lines in `new` that weren't on the previous screen, ignoring digits.

    Masking digits makes unread badges and clocks ("Inbox 12" → "Inbox 11", "10:41") count as unchanged,
    while any new message, however short ("yep, will do"), counts as new. Relative similarity (Jaccard)
    gets both wrong: one badge change on a short screen looks big, one new message in a long channel looks tiny.
    Tradeoff: an edit that only changes a number (a due date "28" → "30") is treated as unchanged.
    """
    seen = {_mask(line) for line in old.splitlines() if line.strip()}
    return [line for line in new.splitlines() if line.strip() and _mask(line) not in seen]


def _mask(line: str) -> str:
    return re.sub(r"\d+", "#", " ".join(line.lower().split()))


def _within_window(previous_iso: str, current: datetime) -> bool:
    return abs(current - datetime.fromisoformat(previous_iso)) <= NEAR_DUPLICATE_WINDOW
