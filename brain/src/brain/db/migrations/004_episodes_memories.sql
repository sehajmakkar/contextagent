-- Migration 4: shrink-first memory (Phase 3, ADR-033/034).
-- observations (raw, short-lived) → episodes (one visit to one window) → memories (distilled, kept).

CREATE TABLE episodes (
    id               INTEGER PRIMARY KEY,
    source           TEXT NOT NULL CHECK (source IN ('file', 'capture')),
    app_name         TEXT NOT NULL,
    bundle_id        TEXT NOT NULL,
    window_title     TEXT NOT NULL,
    url              TEXT,
    started_at       TEXT NOT NULL,
    ended_at         TEXT NOT NULL,
    text             TEXT NOT NULL,            -- every distinct line seen during the visit, first-seen order
    observation_count INTEGER NOT NULL DEFAULT 1,
    raw_chars        INTEGER NOT NULL DEFAULT 0,  -- sum of snapshot sizes, for the funnel
    closed_at        TEXT,                     -- no new snapshot for EPISODE_GAP → ready to process
    processed_at     TEXT,
    skipped_reason   TEXT,                     -- local gate said "nothing to extract"
    process_attempts INTEGER NOT NULL DEFAULT 0,
    process_error    TEXT,
    llm_calls        INTEGER NOT NULL DEFAULT 0,
    prompt_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens    INTEGER NOT NULL DEFAULT 0,
    thinking_tokens  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_episodes_open ON episodes(bundle_id, window_title, source) WHERE closed_at IS NULL;
CREATE INDEX idx_episodes_todo ON episodes(closed_at, processed_at);

ALTER TABLE observations ADD COLUMN episode_id INTEGER REFERENCES episodes(id);
-- Retention: raw text is erased after a few days; the row stays so loop evidence keeps its link.
ALTER TABLE observations ADD COLUMN purged_at TEXT;

CREATE TABLE memories (
    id              INTEGER PRIMARY KEY,
    episode_id      INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    observation_id  INTEGER REFERENCES observations(id) ON DELETE SET NULL,  -- the snapshot holding the quote
    kind            TEXT NOT NULL CHECK (kind IN ('fact', 'decision', 'number', 'event', 'person', 'plan')),
    text            TEXT NOT NULL,     -- standalone sentence, understandable months later
    quote           TEXT NOT NULL,     -- verbatim evidence from the screen
    entities        TEXT NOT NULL DEFAULT '[]',  -- JSON list of names, projects, numbers
    happened_at     TEXT NOT NULL,     -- when it was on screen
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_memories_episode ON memories(episode_id);

-- Keyword search (BM25) over memories, kept in sync by triggers (Part C).
CREATE VIRTUAL TABLE memories_fts USING fts5(text, entities, content='memories', content_rowid='id');
CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, text, entities) VALUES (new.id, new.text, new.entities);
END;
CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, text, entities) VALUES ('delete', old.id, old.text, old.entities);
END;
