"""
Worker command for QueueCTL CLI.
"""

import typer
from rich.console import Console
from rich.table import Table

from QueueCLI.core.worker import run_worker
from QueueCLI.core.process_manager import start_workers, stop_workers, list_workers

console = Console()

app = typer.Typer(help="Manage background workers.")


@app.command("start")
def start(
    count: int = typer.Option(1, "--count", "-n", help="Number of workers to start"),
    poll_interval: float = typer.Option(1.0, "--interval", "-i", help="Polling interval in seconds"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground (single worker)"),
):
    """
    Start background workers to process jobs.
    """
    if foreground:
        console.print("[blue]Starting worker in foreground...[/blue] Press Ctrl+C to stop.")
        run_worker(poll_interval=poll_interval)
        console.print("[yellow]Worker stopped.[/yellow]")
    else:
        pids = start_workers(count=count, poll_interval=poll_interval)
        console.print(f"[green]✓[/green] Started {len(pids)} worker(s): {pids}")


@app.command("stop")
def stop():
    """
    Stop all background workers gracefully.
    """
    stopped = stop_workers()
    if stopped:
        console.print(f"[green]✓[/green] Stopped {len(stopped)} worker(s): {stopped}")
    else:
        console.print("[yellow]No workers running.[/yellow]")


@app.command("list")
def list_running():
    """
    List all running workers.
    """
    pids = list_workers()
    
    if not pids:
        console.print("[yellow]No workers running.[/yellow]")
        return
    
    table = Table(title="Running Workers")
    table.add_column("PID", style="cyan")
    table.add_column("Status", style="green")
    
    for pid in pids:
        table.add_row(str(pid), "Running")
    
    console.print(table)
