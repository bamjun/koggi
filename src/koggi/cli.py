from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from . import __version__
from .config.env_loader import load_profiles
from .database.backup import backup_database
from .database.restore import restore_database
from .database.connection import test_connection
from .exceptions import KoggiError


console = Console()
app = typer.Typer(help="Koggi: PostgreSQL backup & restore CLI")
pg_app = typer.Typer(help="PostgreSQL operations")
config_app = typer.Typer(help="Configuration & profiles")

app.add_typer(pg_app, name="pg")
app.add_typer(config_app, name="config")


@app.callback()
def _version(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=lambda v: _print_version(v), is_eager=True
    )
):
    """Global options."""
    # Handled in callback
    return


def _print_version(value: Optional[bool]) -> None:
    if value:
        console.print(f"koggi {__version__}")
        raise typer.Exit()


@config_app.command("list")
def config_list() -> None:
    """List detected profiles from environment/.env."""
    profiles = load_profiles()
    if not profiles:
        console.print("[yellow]No profiles detected. Run 'koggi config init' or set env vars.[/yellow]")
        raise typer.Exit(code=1)

    table = Table(title="Koggi Profiles", box=box.SIMPLE_HEAD)
    table.add_column("Profile")
    table.add_column("DB Name")
    table.add_column("Host")
    table.add_column("Port")
    table.add_column("SSL")
    table.add_column("Backup Dir")

    for name, p in profiles.items():
        table.add_row(name, p.db_name, p.host, str(p.port), p.ssl_mode, str(p.backup_dir))

    console.print(table)


@config_app.command("test")
def config_test(profile: str = typer.Argument("DEFAULT", help="Profile name, e.g., DEV1, PROD")) -> None:
    """Test database connection for a profile."""
    profiles = load_profiles()
    if profile not in profiles:
        console.print(f"[red]Profile '{profile}' not found.[/red]")
        raise typer.Exit(code=1)
    ok, msg = test_connection(profiles[profile])
    if ok:
        console.print(f"[green]Connection OK[/green] - {msg}")
    else:
        console.print(f"[red]Connection failed[/red] - {msg}")
        raise typer.Exit(code=1)


@pg_app.command("backup")
def pg_backup(
    profile: str = typer.Option("DEFAULT", "-p", "--profile", help="Profile name"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output file path"),
    fmt: str = typer.Option("plain", "--fmt", help="Backup format: plain|custom"),
    compress: bool = typer.Option(False, "-c", "--compress", help="Compress output if supported"),
):
    """Create a database backup using pg_dump."""
    profiles = load_profiles()
    if profile not in profiles:
        console.print(f"[red]Profile '{profile}' not found.[/red]")
        raise typer.Exit(code=1)
    try:
        out = backup_database(profiles[profile], output=output, fmt=fmt, compress=compress)
        console.print(f"[green]Backup completed:[/green] {out}")
    except KoggiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@pg_app.command("restore")
def pg_restore(
    profile: str = typer.Option("DEFAULT", "-p", "--profile", help="Profile name"),
    backup_file: Optional[Path] = typer.Argument(None, help="Backup file path; if omitted, latest is used"),
):
    """Restore a database from a backup file (auto-detects tool)."""
    profiles = load_profiles()
    if profile not in profiles:
        console.print(f"[red]Profile '{profile}' not found.[/red]")
        raise typer.Exit(code=1)
    try:
        used_file = restore_database(profiles[profile], backup_file=backup_file)
        console.print(f"[green]Restore completed from:[/green] {used_file}")
    except KoggiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
