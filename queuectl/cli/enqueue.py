"""
Enqueue command for QueueCTL CLI.
"""

import json
import typer
from rich.console import Console

from QueueCLI.storage.database import enqueue_job, get_job, init_db

console = Console()


def enqueue(
    command_arg: str = typer.Argument(
        None,
        help="Command to execute (or JSON object)",
    ),
    command_opt: str = typer.Option(
        None, "--command", "-c", help="Command to execute (alternative to argument)"
    ),
    retries: int = typer.Option(
        None, "--retries", help="Max retries for this job (overrides config)"
    ),
    priority: int = typer.Option(
        0, "--priority", help="Job priority (higher runs first)"
    ),
    custom_id: str = typer.Option(None, "--id", help="Custom Job ID"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for job to complete and show output"),
):
    """
    Add a new job to the queue.
    
    """
    # Resolve command from argument or option
    command = command_arg or command_opt
    job_cmd = command
    
    # Try parsing command as JSON if it looks like one
    if command and command.strip().startswith("{"):
        try:
            data = json.loads(command)
            job_cmd = data.get("command")
            if not job_cmd:
                console.print("[red]Error: JSON input must contain 'command' field[/red]")
                raise typer.Exit(1)
            
            # Extract other fields if present (CLI flags override JSON)
            if retries is None:
                retries = data.get("max_retries")
            if custom_id is None:
                custom_id = data.get("id")
            # If priority not set via flag (default 0), check json
            if priority == 0:
                priority = data.get("priority", 0)
                
        except json.JSONDecodeError:
            # Not valid JSON, treat as raw command string
            pass

    if not job_cmd:
        console.print("[red]Error: Missing command[/red]")
        raise typer.Exit(1)

    # Use default if still None
    if retries is None:
        retries = 3

    try:
        job_id = enqueue_job(job_cmd, max_retries=retries, custom_id=custom_id, priority=priority)
        console.print(f"[green]✓[/green] Job enqueued: {job_id}")
        if priority > 0:
            console.print(f"  [dim]Priority: {priority}[/dim]")
        
        # If --wait flag is set, poll until job completes
        if wait:
            import time
            from QueueCLI.core.executor import execute_command
            
            console.print("[dim]Waiting for job to complete...[/dim]")
            
            while True:
                job = get_job(job_id)
                if not job:
                    console.print("[red]✗[/red] Job not found")
                    raise typer.Exit(1)
                
                state = job["state"]
                
                if state == "completed":
                    console.print("[green]✓[/green] Job completed successfully")
                    # Execute command locally to show output (since we don't store it)
                    result = execute_command(job_cmd)
                    if result.stdout:
                        console.print(f"\n[bold]Output:[/bold]\n{result.stdout}")
                    if result.stderr:
                        console.print(f"\n[bold red]Errors:[/bold red]\n{result.stderr}")
                    break
                elif state in ["failed", "dead"]:
                    console.print(f"[red]✗[/red] Job {state}")
                    raise typer.Exit(1)
                elif state == "processing":
                    console.print("[dim].[/dim]", end="")
                
                time.sleep(0.5)
                
    except ValueError as e:
        console.print(f"[red]✗[/red] Error enqueuing job: {e}")
        raise typer.Exit(1)

