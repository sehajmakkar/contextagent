-- Migration 2: live capture from the Swift app (Phase 2).

-- Where an observation came from: 'file' (fixtures, CLI) or 'capture' (Accessibility, live screen).
-- Live captures on the Gemini free tier are held back from detection (ADR-027).
ALTER TABLE observations ADD COLUMN source TEXT NOT NULL DEFAULT 'file'
    CHECK (source IN ('file', 'capture'));

-- Failed detections are retried a few times, then skipped so one bad row can't block the queue.
ALTER TABLE observations ADD COLUMN detect_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE observations ADD COLUMN detect_error TEXT;

-- Near-duplicate check looks up the latest snapshot of the same window.
CREATE INDEX IF NOT EXISTS idx_obs_window ON observations(bundle_id, window_title, id);
