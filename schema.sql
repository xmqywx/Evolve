-- MyAgent pgvector schema
-- Run: createdb myagent && psql -U ying -d myagent -f schema.sql
-- Note: HNSW index requires <= 2000 dimensions in pgvector 0.8.x

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory_embeddings (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER NOT NULL,
    task_id TEXT,
    content TEXT NOT NULL,
    embedding vector(2000),
    tags TEXT[],
    project TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_hnsw
    ON memory_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_tags
    ON memory_embeddings USING gin (tags);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_project
    ON memory_embeddings (project);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_task_id
    ON memory_embeddings (task_id);
