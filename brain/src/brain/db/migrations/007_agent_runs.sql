-- Migration 7: agent runs (Phase 5, ADR-046). One 'agent_run' action per "Close it for me"; each tool call is a
-- child row (parent_id), so the audit log shows exactly what the agent read, drafted and was refused.
ALTER TABLE actions ADD COLUMN parent_id INTEGER REFERENCES actions(id) ON DELETE CASCADE;
ALTER TABLE actions ADD COLUMN updated_at TEXT;
CREATE INDEX idx_actions_parent ON actions(parent_id);
