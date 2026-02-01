"""
SQLite Database Access Layer for QueueCTL.

Provides atomic operations for job queue management with safe concurrency.
"""

import sqlite3
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Path to schema file
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Default database path
DEFAULT_DB_PATH = Path.home() / ".queuectl" / "queuectl.db"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Get a database connection with proper settings for concurrency.
    
    Args:
        db_path: Path to the database file. Defaults to ~/.queuectl/queuectl.db
    
    Returns:
        sqlite3.Connection with row factory set to sqlite3.Row
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(
        str(db_path),
        timeout=30.0,  # Wait up to 30 seconds for locks
        isolation_level="IMMEDIATE",  # Acquire locks immediately on write
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """
    Initialize the database from schema.sql.
    
    Args:
        db_path: Path to the database file.
    """
    conn = get_connection(db_path)
    try:
        # Create jobs table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('pending', 'processing', 'completed', 'failed', 'dead')),
                priority INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                attempts INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                next_run_at TIMESTAMP
            )
            """
        )
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_state_next_run ON jobs(state, next_run_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_priority_created ON jobs(priority DESC, created_at ASC)")
        conn.commit()
    finally:
        conn.close()


def enqueue_job(
    command: str,
    max_retries: int = 3,
    custom_id: Optional[str] = None,
    priority: int = 0,
    db_path: Optional[Path] = None,
) -> str:
    """
    Add a new job to the queue.
    """
    job_id = custom_id or str(uuid.uuid4())
    
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO jobs (id, command, state, max_retries, priority, next_run_at)
            VALUES (?, ?, 'pending', ?, ?, CURRENT_TIMESTAMP)
            """,
            (job_id, command, max_retries, priority),
        )
        conn.commit()
        return job_id
    except sqlite3.IntegrityError:
        raise ValueError(f"Job with ID {job_id} already exists")
    finally:
        conn.close()


def fetch_next_job(db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Atomically fetch and lock the next runnable job.
    
    This uses a single atomic UPDATE...RETURNING to prevent race conditions.
    Only jobs in 'pending' state with next_run_at <= now are considered.
    
    Args:
        db_path: Path to the database file.
    
    Returns:
        Job dict if available, None otherwise.
    """
    now = datetime.utcnow().isoformat()
    
    conn = get_connection(db_path)
    try:
        # Atomic fetch-and-lock using UPDATE with subquery
        cursor = conn.execute(
            """
            UPDATE jobs
            SET state = 'processing', updated_at = ?
            WHERE id = (
                SELECT id FROM jobs
                WHERE state = 'pending' AND next_run_at <= ?
                ORDER BY next_run_at ASC
                LIMIT 1
            )
            RETURNING id, command, state, attempts, max_retries, next_run_at, created_at, updated_at
            """,
            (now, now),
        )
        row = cursor.fetchone()
        conn.commit()
        
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def update_job_state(
    job_id: str,
    state: str,
    increment_attempts: bool = False,
    next_run_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> bool:
    """
    Update the state of a job.
    
    Args:
        job_id: The job ID to update.
        state: New state (pending, processing, completed, failed, dead).
        increment_attempts: Whether to increment the attempts counter.
        next_run_at: New next_run_at value for retries.
        db_path: Path to the database file.
    
    Returns:
        True if job was updated, False if not found.
    """
    now = datetime.utcnow().isoformat()
    
    conn = get_connection(db_path)
    try:
        if increment_attempts and next_run_at:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET state = ?, attempts = attempts + 1, next_run_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (state, next_run_at, now, job_id),
            )
        elif increment_attempts:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET state = ?, attempts = attempts + 1, updated_at = ?
                WHERE id = ?
                """,
                (state, now, job_id),
            )
        elif next_run_at:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET state = ?, next_run_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (state, next_run_at, now, job_id),
            )
        else:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET state = ?, updated_at = ?
                WHERE id = ?
                """,
                (state, now, job_id),
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def list_jobs_by_state(
    state: str,
    limit: int = 100,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    List jobs filtered by state.
    
    Args:
        state: The state to filter by.
        limit: Maximum number of jobs to return.
        db_path: Path to the database file.
    
    Returns:
        List of job dicts.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, command, state, attempts, max_retries, priority, next_run_at, created_at, updated_at
            FROM jobs
            WHERE state = ?
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
            """,
            (state, limit),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_job(job_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Get a single job by ID.
    
    Args:
        job_id: The job ID.
        db_path: Path to the database file.
    
    Returns:
        Job dict if found, None otherwise.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, command, state, attempts, max_retries, priority, next_run_at, created_at, updated_at
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_job(job_id: str, db_path: Optional[Path] = None) -> bool:
    """
    Permanently delete a job.
    
    Args:
        job_id: The job ID to delete.
        db_path: Path to the database file.
    
    Returns:
        True if job was deleted, False if not found.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ============================================================================
# Configuration Functions
# ============================================================================

def get_config(key: str, db_path: Optional[Path] = None) -> Optional[str]:
    """
    Get a configuration value by key.
    
    Args:
        key: The configuration key.
        db_path: Path to the database file.
    
    Returns:
        The value if found, None otherwise.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT value FROM config WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def set_config(key: str, value: str, db_path: Optional[Path] = None) -> None:
    """
    Set a configuration value.
    
    Args:
        key: The configuration key.
        value: The configuration value.
        db_path: Path to the database file.
    """
    now = datetime.utcnow().isoformat()
    
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
            """,
            (key, value, now, value, now),
        )
        conn.commit()
    finally:
        conn.close()


def list_config(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    List all configuration values.
    
    Args:
        db_path: Path to the database file.
    
    Returns:
        List of config dicts with key, value, updated_at.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT key, value, updated_at FROM config ORDER BY key"
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

