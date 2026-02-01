"""
Status command for QueueCTL CLI.
"""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns

from QueueCLI.storage.database import get_job, list_jobs_by_state, init_db
from QueueCLI.core.process_manager import list_workers

console = Console()

STATES = ["pending", "processing", "completed", "failed", "dead"]


def status(
    job_id: str = typer.Argument(None, help="Job ID to check status (optional)"),
):
    """
    Show queue status or check a specific job.
    
    Without arguments: shows job counts by state and active workers.
    With job_id: shows details for that specific job.
    """
    init_db()

    if job_id:
        _show_job_status(job_id)
    else:
        _show_queue_status()


def _show_job_status(job_id: str) -> None:
    """Show status of a specific job."""
    job = get_job(job_id)

    if not job:
        console.print(f"[red]✗[/red] Job not found: {job_id}")
        raise typer.Exit(1)

    table = Table(title=f"Job {job_id[:8]}...", show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("ID", job["id"])
    table.add_row("Command", job["command"])
    table.add_row("State", _state_color(job["state"]))
    table.add_row("Priority", str(job.get("priority", 0)))
    table.add_row("Attempts", f"{job['attempts']}/{job['max_retries']}")
    table.add_row("Next Run At", job["next_run_at"] or "N/A")
    table.add_row("Created At", job["created_at"])
    table.add_row("Updated At", job["updated_at"])

    console.print(table)


def _show_queue_status() -> None:
    """Show overall queue status."""
    # Job counts by state
    job_table = Table(title="Queue Status")
    job_table.add_column("State", style="cyan")
    job_table.add_column("Count", style="white", justify="right")

    total = 0
    for state in STATES:
        jobs = list_jobs_by_state(state, limit=10000)
        count = len(jobs)
        total += count
        job_table.add_row(_state_color(state), str(count))

    job_table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

    # Active workers
    workers = list_workers()
    worker_panel = Panel(
        f"[green]{len(workers)}[/green] active" if workers else "[yellow]0[/yellow] active",
        title="Workers",
        expand=False,
    )

    console.print(Columns([job_table, worker_panel]))


def _state_color(state: str) -> str:
    """Apply color to state based on its value."""
    colors = {
        "pending": "[yellow]pending[/yellow]",
        "processing": "[blue]processing[/blue]",
        "completed": "[green]completed[/green]",
        "failed": "[red]failed[/red]",
        "dead": "[dim red]dead[/dim red]",
    }
    return colors.get(state, state)
