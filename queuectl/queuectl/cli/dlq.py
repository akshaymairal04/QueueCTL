"""
DLQ (Dead Letter Queue) commands for QueueCTL CLI.
"""

import typer
from rich.console import Console
from rich.table import Table
from datetime import datetime

from queuectl.storage.database import list_jobs_by_state, get_job, update_job_state, init_db

console = Console()

app = typer.Typer(help="Manage the dead letter queue.")


@app.command("list")
def list_dlq(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum jobs to show"),
):
    """
    List jobs in the dead letter queue.
    """
    init_db()
    jobs = list_jobs_by_state("dead", limit=limit)

    if not jobs:
        console.print("[green]✓[/green] No jobs in the dead letter queue.")
        return

    table = Table(title="Dead Letter Queue")
    table.add_column("ID", style="red", max_width=12)
    table.add_column("Command", style="white", max_width=35)
    table.add_column("Attempts", style="magenta", justify="center")
    table.add_column("Failed At", style="dim")

    for job in jobs:
        table.add_row(
            job["id"][:12] + "...",
            job["command"][:35] + ("..." if len(job["command"]) > 35 else ""),
            f"{job['attempts']}/{job['max_retries']}",
            job["updated_at"][:19],
        )

    console.print(table)
    console.print(f"[dim]Showing {len(jobs)} failed job(s)[/dim]")


@app.command("retry")
def retry_job(
    job_id: str = typer.Argument(..., help="Job ID to retry"),
):
    """
    Retry a job from the dead letter queue.
    
    Resets attempts and moves job back to pending.
    """
    init_db()
    job = get_job(job_id)

    if not job:
        console.print(f"[red]✗[/red] Job not found: {job_id}")
        raise typer.Exit(1)

    if job["state"] != "dead":
        console.print(f"[red]✗[/red] Job is not in DLQ. Current state: {job['state']}")
        raise typer.Exit(1)

    # Reset job: set state to pending, reset attempts via direct SQL
    now = datetime.utcnow().isoformat()
    success = update_job_state(job_id, "pending", next_run_at=now)

    if success:
        console.print(f"[green]✓[/green] Job {job_id[:12]}... moved back to pending queue.")
    else:
        console.print(f"[red]✗[/red] Failed to retry job.")
        raise typer.Exit(1)


@app.command("clear")
def clear_dlq(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """
    Clear all jobs from the dead letter queue.
    """
    init_db()
    jobs = list_jobs_by_state("dead", limit=10000)

    if not jobs:
        console.print("[green]✓[/green] Dead letter queue is already empty.")
        return

    if not force:
        confirm = typer.confirm(f"Delete {len(jobs)} job(s) from DLQ?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    # Permanently remove jobs from DLQ
    from queuectl.storage.database import delete_job
    
    deleted_count = 0
    for job in jobs:
        if delete_job(job["id"]):
            deleted_count += 1

    console.print(f"[green]✓[/green] Cleared {deleted_count} job(s) from DLQ.")
