-- Migration 5: vector search over memories (Phase 3, ADR-020/038). Needs the sqlite-vec extension (store.connect).

-- The vector index. 768 dims = gemini-embedding-2 at output_dimensionality=768; cosine distance (0 = same).
CREATE VIRTUAL TABLE memory_vectors USING vec0(memory_id INTEGER PRIMARY KEY, embedding float[768] distance_metric=cosine);

-- Which model made each vector: vectors from different models can't be compared, so a model change means re-embedding.
CREATE TABLE memory_embeddings (
    memory_id  INTEGER PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
    model      TEXT NOT NULL,
    dims       INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

-- Never send the same text to the embedding API twice (queries in evals repeat a lot).
CREATE TABLE embedding_cache (
    content_hash TEXT PRIMARY KEY,   -- sha256(model, dims, prefixed text)
    vector       BLOB NOT NULL,
    created_at   TEXT NOT NULL
);

-- A memory that says the same thing as an earlier one (e.g. from revisiting a thread) points at it and isn't indexed.
ALTER TABLE memories ADD COLUMN duplicate_of INTEGER REFERENCES memories(id) ON DELETE SET NULL;

CREATE TRIGGER memories_vec_ad AFTER DELETE ON memories BEGIN
    DELETE FROM memory_vectors WHERE memory_id = old.id;
END;
