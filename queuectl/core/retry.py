"""
Retry and Exponential Backoff Logic for QueueCTL.

Pure computation module with no side effects.
"""

from datetime import datetime, timedelta
from typing import Tuple


def compute_backoff_delay(attempts: int, base: int = 2) -> int:
    """
    Compute the backoff delay in seconds using exponential backoff.
    
    Formula: delay_seconds = base ** attempts
    
    Args:
        attempts: Number of attempts made so far (0-indexed).
        base: Base for exponential calculation (default: 2).
    
    Returns:
        Delay in seconds before the next retry.
    """
    return base ** attempts


def compute_next_run_at(attempts: int, base: int = 2) -> str:
    """
    Compute the next_run_at timestamp for a retry.
    
    Args:
        attempts: Number of attempts made so far.
        base: Base for exponential calculation.
    
    Returns:
        ISO-8601 formatted timestamp for the next run.
    """
    delay = compute_backoff_delay(attempts, base)
    next_run = datetime.utcnow() + timedelta(seconds=delay)
    return next_run.isoformat()


def should_retry(attempts: int, max_retries: int) -> bool:
    """
    Determine if a job should be retried or moved to DLQ.
    
    Args:
        attempts: Current number of attempts (after incrementing).
        max_retries: Maximum allowed retries.
    
    Returns:
        True if job should be retried, False if it should go to DLQ.
    """
    # attempts includes the initial failure + previous retries
    # e.g., max_retries=3
    # Fail 1 (att 1) <= 3 -> Retry
    # Fail 2 (att 2) <= 3 -> Retry
    # Fail 3 (att 3) <= 3 -> Retry
    # Fail 4 (att 4) > 3 -> DLQ
    return attempts <= max_retries


def compute_retry_decision(
    attempts: int,
    max_retries: int,
    base: int = 2,
) -> Tuple[str, str]:
    """
    Compute the retry decision for a failed job.
    
    This is the main entry point for retry logic. It returns the new state
    and next_run_at timestamp based on the current attempt count.
    
    Args:
        attempts: Current number of attempts (before incrementing).
        max_retries: Maximum allowed retries.
        base: Base for exponential calculation.
    
    Returns:
        Tuple of (new_state, next_run_at).
        - If retrying: ('pending', <ISO timestamp>)
        - If moving to DLQ: ('dead', None)
    """
    new_attempts = attempts + 1
    
    if should_retry(new_attempts, max_retries):
        next_run_at = compute_next_run_at(new_attempts, base)
        return ("pending", next_run_at)
    else:
        return ("dead", None)
