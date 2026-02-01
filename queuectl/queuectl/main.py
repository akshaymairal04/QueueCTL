"""
QueueCTL CLI - Main Entrypoint.

Wire all CLI commands under a single `queuectl` command.
"""

import typer
from rich.console import Console

from queuectl.cli import enqueue, worker, status, jobs, dlq, config

app = typer.Typer(
    name="queuectl",
    help="A production-grade CLI for background job queue management.",
    add_completion=False,
)

console = Console()

# Register commands
app.command("enqueue")(enqueue.enqueue)
app.add_typer(worker.app, name="worker")
app.command("status")(status.status)
app.command("list")(jobs.list_jobs)
app.add_typer(dlq.app, name="dlq")
app.add_typer(config.app, name="config")


@app.callback()
def callback():
    """
    QueueCTL: A production-grade CLI for background job queue management.
    """
    pass


if __name__ == "__main__":
    app()
