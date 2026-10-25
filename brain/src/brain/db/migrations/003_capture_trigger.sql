-- Migration 3: why the app read the screen (Phase 3, event-driven capture).
-- 'settled' = after change notifications went quiet, 'leaving' = you switched away, 'poll' = backup timer.
ALTER TABLE observations ADD COLUMN capture_trigger TEXT
    CHECK (capture_trigger IN ('settled', 'leaving', 'poll'));
