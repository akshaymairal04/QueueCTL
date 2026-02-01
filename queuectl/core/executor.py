"""
Job Command Execution for QueueCTL.

Executes shell commands safely and returns structured results.
"""

import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionResult:
    """
    Structured result of a command execution.
    """
    
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    error: Optional[str] = None  # For exceptions (e.g., command not found)


def execute_command(command: str, timeout: Optional[int] = None) -> ExecutionResult:
    """
    Execute a shell command and return a structured result.
    
    Args:
        command: The shell command to execute.
        timeout: Optional timeout in seconds.
    
    Returns:
        ExecutionResult with success status, exit code, stdout, stderr.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        return ExecutionResult(
            success=(result.returncode == 0),
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    
    except subprocess.TimeoutExpired as e:
        return ExecutionResult(
            success=False,
            exit_code=-1,
            stdout=e.stdout or "" if hasattr(e, 'stdout') and e.stdout else "",
            stderr=e.stderr or "" if hasattr(e, 'stderr') and e.stderr else "",
            error=f"Command timed out after {timeout} seconds",
        )
    
    except FileNotFoundError as e:
        return ExecutionResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr="",
            error=f"Command not found: {e}",
        )
    
    except Exception as e:
        return ExecutionResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr="",
            error=f"Execution error: {e}",
        )
