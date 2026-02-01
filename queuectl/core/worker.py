"""
Worker Processing Loop for QueueCTL.

Implements the core worker lifecycle with atomic job fetching,
execution, retry handling, and graceful shutdown.
"""

import signal
import time
from typing import Optional
from pathlib import Path

from QueueCLI.storage.database import (
    fetch_next_job,
    update_job_state,
    init_db,
)
from QueueCLI.core.executor import execute_command
from QueueCLI.core.retry import compute_retry_decision
from QueueCLI.core.models import Job


# Global flag for graceful shutdown
_shutdown_requested = False


def _handle_shutdown(signum, frame):
    """Signal handler for graceful shutdown."""
    global _shutdown_requested
    _shutdown_requested = True


def process_job(job: Job, db_path: Optional[Path] = None) -> None:
    """
    Process a single job: execute command and update state.
    
    Args:
        job: The Job to process.
        db_path: Path to the database file.
    """
    # Execute the command
    result = execute_command(job.command)
    
    # Print output for visibility (especially in foreground mode)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(f"[ERR] {result.stderr.strip()}")
    
    if result.success:
        # Job completed successfully
        update_job_state(job.id, "completed", db_path=db_path)
    else:
        # Job failed - determine retry or DLQ
        new_state, next_run_at = compute_retry_decision(
            job.attempts,
            job.max_retries,
        )
        
        update_job_state(
            job.id,
            new_state,
            increment_attempts=True,
            next_run_at=next_run_at,
            db_path=db_path,
        )


def run_worker(
    poll_interval: float = 1.0,
    db_path: Optional[Path] = None,
) -> None:
    """
    Run the worker processing loop.
    
    The worker will:
    1. Fetch one runnable job atomically
    2. Execute the command
    3. Update job state (completed/failed/dead)
    4. Sleep briefly if no job found
    5. Exit gracefully on SIGTERM/SIGINT
    
    Args:
        poll_interval: Seconds to sleep when no job is available.
        db_path: Path to the database file.
    """
    global _shutdown_requested
    _shutdown_requested = False
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    
    # Ensure database is initialized
    init_db(db_path)
    
    while not _shutdown_requested:
        try:
            # Fetch next runnable job atomically
            job_data = fetch_next_job(db_path)
            
            if job_data:
                job = Job.from_dict(job_data)
                process_job(job, db_path)
            else:
                # No job available, sleep briefly
                time.sleep(poll_interval)
        except Exception as e:
            # Log error and sleep briefly to avoid tight loop on persistent failure
            # In a real app, use logging.error
            print(f"[Worker] Error in processing loop: {e}")
            time.sleep(poll_interval)


def run_worker_once(db_path: Optional[Path] = None) -> bool:
    """
    Run a single iteration of the worker loop.
    
    Useful for testing or one-shot processing.
    
    Args:
        db_path: Path to the database file.
    
    Returns:
        True if a job was processed, False otherwise.
    """
    job_data = fetch_next_job(db_path)
    
    if job_data:
        job = Job.from_dict(job_data)
        process_job(job, db_path)
        return True
    
    return False
