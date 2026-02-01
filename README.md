# QueueCTL

A production-grade CLI for background job queue management with **priority scheduling**, retries, exponential backoff, and dead letter queue support.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            QueueCTL Architecture                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────┐    enqueue     ┌──────────────────────────────────┐      │
│   │   CLI   │ ─────────────► │            SQLite DB             │      │
│   └─────────┘                │  ┌────────┐  ┌────────┐  ┌────┐  │      │
│        │                     │  │ pending│  │complete│  │dead│  │      │
│        │                     │  └────────┘  └────────┘  └────┘  │      │
│        │                     └──────────────────────────────────┘      │
│        │                                    ▲                          │
│        │                                    │ atomic fetch              │
│        │ start                              │ + priority sort           │
│        ▼                                    │                          │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐                            │
│   │Worker 1 │    │Worker 2 │    │Worker N │  ◄── multiprocessing       │
│   └─────────┘    └─────────┘    └─────────┘                            │
│        │              │              │                                  │
│        └──────────────┴──────────────┘                                  │
│                       │                                                 │
│                       ▼                                                 │
│              ┌─────────────────┐                                        │
│              │ Command Executor│ → subprocess.run(shell=True)           │
│              └─────────────────┘                                        │
│                       │                                                 │
│            ┌──────────┴──────────┐                                      │
│            ▼                     ▼                                      │
│       [success]             [failure]                                   │
│            │                     │                                      │
│            ▼                     ▼                                      │
│      ┌──────────┐    ┌─────────────────────┐                           │
│      │completed │    │ Retry Logic          │                           │
│      └──────────┘    │ delay = base^attempts│                           │
│                      └─────────────────────┘                           │
│                               │                                         │
│                    ┌──────────┴──────────┐                              │
│                    ▼                     ▼                              │
│            [attempts < max]      [attempts >= max]                      │
│                    │                     │                              │
│                    ▼                     ▼                              │
│             ┌──────────┐          ┌──────────┐                          │
│             │ pending  │          │   dead   │ (DLQ)                    │
│             │(+backoff)│          └──────────┘                          │
│             └──────────┘                                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Priority Queue**: Higher priority jobs execute first (configurable per job)
- **Synchronous Execution**: `--wait` flag to see output immediately
- **Persistent Queue**: Jobs survive process restarts (SQLite storage)
- **Retry with Exponential Backoff**: `delay = base^attempts` seconds
- **Dead Letter Queue**: Failed jobs after max retries go to DLQ
- **Parallel Workers**: Run multiple workers for concurrent job processing
- **Atomic Job Locking**: No duplicate processing across workers
- **Graceful Shutdown**: Workers finish current job on SIGTERM
- **Rich CLI Output**: Beautiful tables and colored output

## Quick Start

```powershell
# Clone and setup
cd queuectl
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Start workers in background (2 parallel workers)
python -m queuectl.main worker start --count 2

# Enqueue a job with priority and see output immediately
python -m queuectl.main enqueue --command "echo Hello World!" --priority 10 --wait

# Check status
python -m queuectl.main status
```

## CLI Reference

### Job Management

```powershell
# Enqueue jobs
python -m queuectl.main enqueue --command "echo hello"
python -m queuectl.main enqueue --command "python script.py" --retries 5
python -m queuectl.main enqueue --command "echo urgent" --priority 10

# Enqueue with --wait to see output immediately (synchronous)
python -m queuectl.main enqueue --command "echo Hello!" --wait

# Enqueue JSON format
python -m queuectl.main enqueue '{"command": "python script.py", "max_retries": 3, "priority": 5}'

# List jobs (sorted by priority DESC, then created_at ASC)
python -m queuectl.main list --state pending
python -m queuectl.main list --state all --limit 50

# Check job status
python -m queuectl.main status <job_id>
python -m queuectl.main status  # Overview of all states
```

### Worker Management

```powershell
# Start workers
python -m queuectl.main worker start --count 4           # 4 parallel background workers
python -m queuectl.main worker start --foreground        # Single foreground worker (see output)

# Manage workers
python -m queuectl.main worker list                      # List running workers
python -m queuectl.main worker stop                      # Graceful shutdown
```

### Dead Letter Queue

```powershell
python -m queuectl.main dlq list                         # View failed jobs
python -m queuectl.main dlq retry <job_id>               # Retry a failed job
python -m queuectl.main dlq clear --force                # Clear all failed jobs
```

### Configuration

```powershell
python -m queuectl.main config set max-retries 5
python -m queuectl.main config get max-retries
python -m queuectl.main config list
```

## Priority Queue

Jobs are processed in **priority order** (higher priority first). When priorities are equal, jobs are processed FIFO (oldest first).

```powershell
# High priority job (runs first)
python -m queuectl.main enqueue --command "echo URGENT" --priority 10

# Normal priority job (runs after high priority)
python -m queuectl.main enqueue --command "echo normal" --priority 5

# Low priority job (runs last)
python -m queuectl.main enqueue --command "echo low" --priority 1
```

**Default priority**: `0`

## Synchronous Execution with `--wait`

Use the `--wait` flag to block until the job completes and see the output immediately:

```powershell
# Start workers first
python -m queuectl.main worker start --count 2

# Enqueue and wait for result
python -m queuectl.main enqueue --command "echo Hello World!" --wait
# Output:
# ✓ Job enqueued: abc123...
# Waiting for job to complete...
# ✓ Job completed successfully
# 
# Output:
# Hello World!

# Works with longer jobs too
python -m queuectl.main enqueue --command "timeout /t 5 > NUL & echo Done!" --wait --priority 10
```

## Parallel Execution Example

```powershell
# Start 2 workers
python -m queuectl.main worker start --count 2

# Enqueue multiple jobs
python -m queuectl.main enqueue --command "timeout /t 15 > NUL & echo Job1" --priority 10
python -m queuectl.main enqueue --command "echo Job2" --priority 5

# Both jobs run in parallel (Job2 finishes first despite being enqueued second)
python -m queuectl.main list --state all
```

## Architecture

### Directory Structure

```
queuectl/
├── queuectl/
│   ├── main.py          # CLI entrypoint
│   ├── cli/             # Command handlers (no business logic)
│   ├── core/            # Business logic
│   │   ├── worker.py    # Worker loop
│   │   ├── executor.py  # Command execution
│   │   ├── retry.py     # Backoff computation
│   │   └── models.py    # Job dataclass
│   ├── storage/         # Persistence layer
│   │   ├── database.py  # SQLite operations
│   │   └── schema.sql   # DB schema
│   └── config/          # Configuration
└── tests/               # Test scripts
```

### Job States

| State | Description |
|-------|-------------|
| `pending` | Waiting to be processed |
| `processing` | Currently being executed |
| `completed` | Successfully finished |
| `failed` | Failed, may be retried |
| `dead` | Max retries exceeded (DLQ) |

### Database Schema

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('pending', 'processing', 'completed', 'failed', 'dead')),
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    attempts INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_run_at TIMESTAMP
);

CREATE INDEX idx_state_next_run ON jobs(state, next_run_at);
CREATE INDEX idx_priority_created ON jobs(priority DESC, created_at ASC);
```

## Retry Strategy

**Formula**: `delay_seconds = base ^ attempts`

| Attempt | Delay (base=2) |
|---------|----------------|
| 1 | 2 seconds |
| 2 | 4 seconds |
| 3 | 8 seconds |
| 4 | 16 seconds |

Jobs exceeding `max_retries` move to the Dead Letter Queue.

## Locking Strategy

Workers use **atomic UPDATE with BEGIN IMMEDIATE** to claim jobs:

```sql
BEGIN IMMEDIATE;
SELECT id, command, state, attempts, max_retries, priority, next_run_at
FROM jobs
WHERE state = 'pending'
  AND (next_run_at IS NULL OR next_run_at <= CURRENT_TIMESTAMP)
ORDER BY priority DESC, created_at ASC
LIMIT 1;

UPDATE jobs SET state = 'processing', updated_at = ? WHERE id = ?;
COMMIT;
```

This prevents race conditions without external locks.

## Tradeoffs

| Decision | Benefit | Tradeoff |
|----------|---------|----------|
| SQLite | Zero dependencies, atomic ops | Single-machine only |
| WAL mode | Better read concurrency | Slightly more disk space |
| shell=True | Full shell features | Security if commands untrusted |
| Multiprocessing | True parallelism | PID management complexity |
| No ORM | Direct control, performance | More SQL to maintain |
| Priority Queue | Critical jobs first | Starvation risk for low priority |

## Requirements

- Python 3.10+
- typer
- rich
- python-dateutil

## License

MIT
