"""
Jobs list command for QueueCTL CLI.
"""

import typer
from rich.console import Console
from rich.table import Table

from QueueCLI.storage.database import list_jobs_by_state, init_db

console = Console()

VALID_STATES = ["pending", "processing", "completed", "failed", "dead", "all"]


def list_jobs(
    state: str = typer.Option("pending", "--state", "-s", help="Filter by state (or 'all')"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum jobs to show"),
):
    """
    List jobs in the queue.
    """
    init_db()

    if state not in VALID_STATES:
        console.print(f"[red]✗[/red] Invalid state: {state}. Valid: {', '.join(VALID_STATES)}")
        raise typer.Exit(1)

    if state == "all":
        all_jobs = []
        for s in ["pending", "processing", "completed", "failed", "dead"]:
            all_jobs.extend(list_jobs_by_state(s, limit=limit))
        jobs = sorted(all_jobs, key=lambda j: j["created_at"], reverse=True)[:limit]
    else:
        jobs = list_jobs_by_state(state, limit=limit)

    if not jobs:
        console.print(f"[yellow]No jobs found{'' if state == 'all' else f' with state: {state}'}[/yellow]")
        return

    title = "All Jobs" if state == "all" else f"Jobs ({state})"
    table = Table(title=title)
    table.add_column("ID", style="cyan", max_width=12)
    table.add_column("Command", style="white", max_width=35)
    table.add_column("State", style="dim")
    table.add_column("Priority", style="yellow", justify="center")
    table.add_column("Attempts", style="magenta", justify="center")
    table.add_column("Created", style="dim")

    for job in jobs:
        table.add_row(
            job["id"][:12] + "...",
            job["command"][:35] + ("..." if len(job["command"]) > 35 else ""),
            _state_color(job["state"]),
            str(job.get("priority", 0)),
            f"{job['attempts']}/{job['max_retries']}",
            job["created_at"][:19],
        )

    console.print(table)
    console.print(f"[dim]Showing {len(jobs)} job(s)[/dim]")


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
