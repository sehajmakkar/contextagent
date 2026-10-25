-- Migration 6: loop lifecycle (Phase 4, ADR-040). SQLite can't alter a CHECK constraint, so `loops` is
-- rebuilt: create new → copy → drop → rename. Safe because the runner turns foreign keys off around it.

CREATE TABLE loops_new (
    id                  INTEGER PRIMARY KEY,
    title               TEXT NOT NULL,
    direction           TEXT NOT NULL CHECK (direction IN ('i_owe', 'they_owe', 'self')),
    counterparty        TEXT NOT NULL,           -- 'self' for reminders to yourself
    counterparty_email  TEXT,
    deliverable         TEXT NOT NULL,
    note                TEXT,                    -- one line: why it's still open (shown in the inbox)
    due_date            TEXT,
    state               TEXT NOT NULL DEFAULT 'open'
                        CHECK (state IN ('open', 'acting', 'awaiting_approval', 'closed', 'dismissed')),
    confidence          REAL NOT NULL,
    source_app          TEXT,
    closed_reason       TEXT CHECK (closed_reason IN ('user', 'inferred', 'agent')),
    closed_at           TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

INSERT INTO loops_new (id, title, direction, counterparty, counterparty_email, deliverable, due_date, state,
                       confidence, source_app, created_at, updated_at)
SELECT l.id, l.title, l.direction, l.counterparty, l.counterparty_email, l.deliverable, l.due_date, l.state,
       l.confidence,
       (SELECT o.app_name FROM loop_evidence e JOIN observations o ON o.id = e.observation_id
        WHERE e.loop_id = l.id ORDER BY e.id LIMIT 1),
       l.created_at, l.updated_at
FROM loops l;

DROP TABLE loops;
ALTER TABLE loops_new RENAME TO loops;
CREATE INDEX idx_loops_state ON loops(state);

-- Every state change, who made it, and the evidence for it. "Inferred" closes stay distinguishable from yours.
CREATE TABLE loop_transitions (
    id              INTEGER PRIMARY KEY,
    loop_id         INTEGER NOT NULL REFERENCES loops(id) ON DELETE CASCADE,
    from_state      TEXT,
    to_state        TEXT NOT NULL,
    actor           TEXT NOT NULL CHECK (actor IN ('system', 'user', 'agent')),
    reason          TEXT NOT NULL,
    observation_id  INTEGER REFERENCES observations(id) ON DELETE SET NULL,
    confidence      REAL,
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_transitions_loop ON loop_transitions(loop_id);

-- Loop vectors for semantic dedupe ("send the deck" vs "share the slides").
CREATE VIRTUAL TABLE loop_vectors USING vec0(loop_id INTEGER PRIMARY KEY, embedding float[768] distance_metric=cosine);
