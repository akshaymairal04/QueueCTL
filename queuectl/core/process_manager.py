"""
Worker Process Manager for QueueCTL.

Manages multiple worker processes with PID tracking and graceful shutdown.
"""

import json
import signal
import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional

# PID file location
DEFAULT_PID_FILE = Path.home() / ".queuectl" / "workers.json"


def _get_pid_file(pid_file: Optional[Path] = None) -> Path:
    """Get the PID file path."""
    return pid_file or DEFAULT_PID_FILE


def _read_pids(pid_file: Optional[Path] = None) -> List[int]:
    """Read worker PIDs from the PID file."""
    pf = _get_pid_file(pid_file)
    if not pf.exists():
        return []
    
    try:
        with open(pf, "r") as f:
            data = json.load(f)
            return data.get("pids", [])
    except (json.JSONDecodeError, IOError):
        return []


def _write_pids(pids: List[int], pid_file: Optional[Path] = None) -> None:
    """Write worker PIDs to the PID file."""
    pf = _get_pid_file(pid_file)
    pf.parent.mkdir(parents=True, exist_ok=True)
    
    with open(pf, "w") as f:
        json.dump({"pids": pids}, f)


if os.name == 'nt':
    import ctypes
    
    def _is_process_running(pid: int) -> bool:
        """Check if a process with the given PID is running (Windows)."""
        try:
            kernel32 = ctypes.windll.kernel32
            # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            # SYNCHRONIZE = 0x00100000
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            
            h_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h_process:
                return False
                
            exit_code = ctypes.c_ulong()
            try:
                if kernel32.GetExitCodeProcess(h_process, ctypes.byref(exit_code)):
                    # STILL_ACTIVE = 259
                    return exit_code.value == 259
            finally:
                kernel32.CloseHandle(h_process)
            return False
        except Exception:
            return False
else:
    def _is_process_running(pid: int) -> bool:
        """Check if a process with the given PID is running (POSIX)."""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def start_workers(
    count: int = 1,
    poll_interval: float = 1.0,
    db_path: Optional[Path] = None,
    pid_file: Optional[Path] = None,
) -> List[int]:
    """
    Start multiple worker processes.
    
    Args:
        count: Number of workers to start.
        poll_interval: Polling interval for each worker.
        db_path: Path to the database file.
        pid_file: Path to the PID file.
    
    Returns:
        List of started worker PIDs.
    """
    existing_pids = [p for p in _read_pids(pid_file) if _is_process_running(p)]
    new_pids = []
    
    # Creation flags for Windows to detach process
    creationflags = 0
    if os.name == 'nt':
        creationflags = subprocess.DETACHED_PROCESS
    
    cmd = [
        sys.executable, "-m", "queuectl.main", 
        "worker", "start", 
        "--foreground", 
        "--interval", str(poll_interval)
    ]
    
    for _ in range(count):
        # We spawn a new detached process running the worker in foreground mode
        # stdout/stderr are discarded or could be logged to file in future
        proc = subprocess.Popen(
            cmd,
            creationflags=creationflags,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        new_pids.append(proc.pid)
    
    all_pids = existing_pids + new_pids
    _write_pids(all_pids, pid_file)
    
    return new_pids


def stop_workers(pid_file: Optional[Path] = None) -> List[int]:
    """
    Stop all worker processes gracefully.
    
    Sends SIGTERM to allow workers to finish current jobs.
    
    Args:
        pid_file: Path to the PID file.
    
    Returns:
        List of stopped worker PIDs.
    """
    pids = _read_pids(pid_file)
    stopped = []
    
    for pid in pids:
        if _is_process_running(pid):
            try:
                os.kill(pid, signal.SIGTERM)
                stopped.append(pid)
            except Exception:
                pass
    
    _write_pids([], pid_file)
    return stopped


def list_workers(pid_file: Optional[Path] = None) -> List[int]:
    """
    List all running worker PIDs.
    
    Args:
        pid_file: Path to the PID file.
    
    Returns:
        List of running worker PIDs.
    """
    pids = _read_pids(pid_file)
    running = [p for p in pids if _is_process_running(p)]
    
    # Update PID file to remove stale entries
    if len(running) != len(pids):
        _write_pids(running, pid_file)
    
    return running
