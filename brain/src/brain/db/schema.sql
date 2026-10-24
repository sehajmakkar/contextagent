-- Schema v1. Applied when PRAGMA user_version < 1 (see store.py).

CREATE TABLE IF NOT EXISTS observations (
    id            INTEGER PRIMARY KEY,
    captured_at   TEXT NOT NULL,           -- ISO 8601 with timezone
    app_name      TEXT NOT NULL,
    bundle_id     TEXT NOT NULL,
    window_title  TEXT NOT NULL DEFAULT '',
    url           TEXT,
    text          TEXT NOT NULL,           -- already redacted
    content_hash  TEXT NOT NULL UNIQUE,    -- sha256 of bundle_id + window_title + text
    processed_at  TEXT                     -- set once loop detection has run
);

CREATE TABLE IF NOT EXISTS loops (
    id                  INTEGER PRIMARY KEY,
    title               TEXT NOT NULL,
    direction           TEXT NOT NULL CHECK (direction IN ('i_owe', 'they_owe')),
    counterparty        TEXT NOT NULL,
    counterparty_email  TEXT,
    deliverable         TEXT NOT NULL,
    due_date            TEXT,              -- YYYY-MM-DD, resolved from the observation's date
    state               TEXT NOT NULL DEFAULT 'open'
                        CHECK (state IN ('open', 'closed', 'dismissed')),
    confidence          REAL NOT NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS loop_evidence (
    id              INTEGER PRIMARY KEY,
    loop_id         INTEGER NOT NULL REFERENCES loops(id) ON DELETE CASCADE,
    observation_id  INTEGER NOT NULL REFERENCES observations(id) ON DELETE CASCADE,
    quote           TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('created', 'progress', 'closed')),
    created_at      TEXT NOT NULL
);

-- Audit log: every LLM-produced action and every human approval (CLAUDE.md safety rules).
CREATE TABLE IF NOT EXISTS actions (
    id            INTEGER PRIMARY KEY,
    loop_id       INTEGER REFERENCES loops(id) ON DELETE SET NULL,
    kind          TEXT NOT NULL,           -- e.g. 'draft_reply'
    status        TEXT NOT NULL,           -- 'drafted' | 'approved' | 'sent' | 'failed'
    input_json    TEXT NOT NULL,
    output_json   TEXT,
    model         TEXT,
    prompt_tokens INTEGER,
    output_tokens INTEGER,
    thinking_tokens INTEGER,
    approved_by   TEXT,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_loops_state ON loops(state);
CREATE INDEX IF NOT EXISTS idx_evidence_loop ON loop_evidence(loop_id);
