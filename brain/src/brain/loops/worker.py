"""Background thread that processes closed episodes (memories + loops), at a capped rate."""

import logging
import threading
import time

from brain.config import Settings
from brain.db import store
from brain.llm.client import LLMClient, LLMError
from brain.memory.embed import embed_memories
from brain.loops import pipeline

log = logging.getLogger(__name__)


class DetectionWorker(threading.Thread):
    def __init__(self, settings: Settings) -> None:
        super().__init__(name="detection-worker", daemon=True)
        self.settings = settings
        self.processed = 0
        self.failed = 0
        self.last_error: str | None = None
        self._stop = threading.Event()
        self._current: int | None = None

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        # sqlite3 connections belong to the thread that made them, so the worker opens its own.
        conn = store.connect(self.settings.db_path)
        llm = LLMClient(self.settings.gemini_api_key.get_secret_value(), self.settings.llm_model)
        while not self._stop.is_set():
            try:
                self._stop.wait(self._tick(conn, llm))
            except Exception as e:  # noqa: BLE001
                # Never let one bad episode stop detection for good. Before this, a sqlite error (for example
                # "Delete all data" removing the episode mid-run) silently killed the thread until a restart.
                log.exception("detection worker error, continuing")
                self.failed += 1
                self.last_error = f"detection error: {e}"
                self._count_attempt(conn)
                self._stop.wait(5.0)
        conn.close()

    def _tick(self, conn, llm) -> float:
        """Process at most one episode; return how long to wait before the next tick."""
        self._current = None
        batch = pipeline.pending(conn, self.settings, limit=1)
        if not batch:
            return 2.0
        self._current = batch[0]["id"]
        started = time.monotonic()
        outcome = pipeline.process(conn, llm, batch[0], self.settings)
        if outcome.quota_exhausted:
            self.last_error = outcome.error
            log.warning("%s; pausing detection for 30 min", outcome.error)
            return 1800
        if outcome.error:
            self.failed += 1
            self.last_error = outcome.error
            log.warning("processing failed for episode %s: %s", batch[0]["id"], outcome.error)
        else:
            self.processed += 1
            for loop_id, title, conf in outcome.created:
                log.info("loop #%s created: %s (%.2f)", loop_id, title, conf)
            log.info("episode %s: %d memories, %d llm calls", batch[0]["id"], len(outcome.memories), len(outcome.usages))
            if outcome.memories:
                try:
                    embed_memories(conn, llm, self.settings)
                except LLMError as e:  # memories are safe; `brain embed` backfills later
                    log.warning("embedding failed: %s", e)
        # Rate cap: never start detections faster than one per `detect_min_interval_s`.
        return max(0.0, self.settings.detect_min_interval_s - (time.monotonic() - started))

    def _count_attempt(self, conn) -> None:
        """Charge the failure to the episode, so one that always fails is given up after MAX_ATTEMPTS."""
        try:
            conn.rollback()
            if self._current is not None:
                with conn:
                    conn.execute("UPDATE episodes SET process_attempts = process_attempts + 1 WHERE id = ?",
                                 (self._current,))
        except Exception:  # noqa: BLE001  (the episode may be gone, e.g. after Delete all data)
            log.exception("couldn't record the failed attempt")
