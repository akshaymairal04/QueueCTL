"""
Config command group for QueueCTL CLI.
"""

import typer
from rich.console import Console
from rich.table import Table

from QueueCLI.storage.database import get_config, set_config, list_config, init_db

console = Console()

app = typer.Typer(help="Manage configuration settings.")

# Default configuration values
DEFAULTS = {
    "max-retries": "3",
    "backoff-base": "2",
    "poll-interval": "1.0",
}


@app.command("get")
def config_get(key: str = typer.Argument(..., help="Configuration key")):
    """
    Get a configuration value.
    """
    init_db()
    value = get_config(key)
    
    if value is None:
        default = DEFAULTS.get(key)
        if default:
            console.print(f"[dim]{key}[/dim] = [yellow]{default}[/yellow] (default)")
        else:
            console.print(f"[red]✗[/red] Key not found: {key}")
            raise typer.Exit(1)
    else:
        console.print(f"[dim]{key}[/dim] = [green]{value}[/green]")


@app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value"),
):
    """
    Set a configuration value.
    """
    init_db()
    set_config(key, value)
    console.print(f"[green]✓[/green] Set [dim]{key}[/dim] = [green]{value}[/green]")


@app.command("list")
def config_list():
    """
    List all configuration values.
    """
    init_db()
    configs = list_config()
    
    # Merge with defaults
    all_keys = set(DEFAULTS.keys()) | {c["key"] for c in configs}
    config_map = {c["key"]: c["value"] for c in configs}
    
    table = Table(title="Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")
    table.add_column("Source", style="dim")
    
    for key in sorted(all_keys):
        if key in config_map:
            table.add_row(key, config_map[key], "user")
        else:
            table.add_row(key, DEFAULTS[key], "default")
    
    console.print(table)
