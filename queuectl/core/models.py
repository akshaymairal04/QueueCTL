"""
Job Domain Model for QueueCTL.

Pure data model with no database logic.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Job:
    """
    Represents a job in the queue.
    
    All timestamps are ISO-8601 format strings.
    State transitions are handled by the service layer, not this model.
    """
    
    id: str
    command: str
    state: str  # pending | processing | completed | failed | dead
    attempts: int
    max_retries: int
    next_run_at: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        """Create a Job from a dictionary (e.g., from database row)."""
        return cls(
            id=data["id"],
            command=data["command"],
            state=data["state"],
            attempts=data["attempts"],
            max_retries=data["max_retries"],
            next_run_at=data.get("next_run_at"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def to_dict(self) -> dict:
        """Convert Job to a dictionary."""
        return {
            "id": self.id,
            "command": self.command,
            "state": self.state,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "next_run_at": self.next_run_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
