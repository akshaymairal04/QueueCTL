-- QueueCTL SQLite Schema
-- Designed for persistent job queue management with retries and DLQ support.

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Jobs table: stores all job information
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'processing', 'completed', 'failed', 'dead')),
    attempts INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    next_run_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Config table: stores key-value configuration pairs
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Index for efficient job fetching by state and next_run_at
CREATE INDEX IF NOT EXISTS idx_jobs_state_next_run ON jobs (state, next_run_at);

-- Trigger to update updated_at on job modification
CREATE TRIGGER IF NOT EXISTS update_jobs_timestamp
AFTER UPDATE ON jobs
FOR EACH ROW
BEGIN
    UPDATE jobs SET updated_at = datetime('now') WHERE id = OLD.id;
END;

-- Trigger to update updated_at on config modification
CREATE TRIGGER IF NOT EXISTS update_config_timestamp
AFTER UPDATE ON config
FOR EACH ROW
BEGIN
    UPDATE config SET updated_at = datetime('now') WHERE key = OLD.key;
END;
