CREATE TABLE IF NOT EXISTS challenges (
    client_id TEXT PRIMARY KEY,
    nonce TEXT NOT NULL,
    expiry REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    client_id TEXT PRIMARY KEY,
    approved BOOLEAN NOT NULL DEFAULT 0,
    device_token TEXT
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_text TEXT,
    assistant_text TEXT,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_turns_session_id ON turns(session_id);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    metadata TEXT, -- JSON
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    content='memories',
    content_rowid='rowid'
);

CREATE TABLE IF NOT EXISTS memory_embeddings (
    memory_id TEXT PRIMARY KEY,
    embedding BLOB,
    FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
);
