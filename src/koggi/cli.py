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
from .binaries import (
    get_pg_dump_path,
    get_psql_path,
    get_pg_restore_path,
    get_binary_info,
)
from .binaries.downloader import (
    download_postgresql_binaries,
    check_binaries_status,
    clean_binaries,
    get_download_info,
)
from .binaries import get_platform_tag


console = Console()
app = typer.Typer(help="Koggi: PostgreSQL backup & restore CLI")
pg_app = typer.Typer(help="PostgreSQL operations")
config_app = typer.Typer(help="Configuration & profiles")
binaries_app = typer.Typer(help="Embedded PostgreSQL binaries")

app.add_typer(pg_app, name="pg")
app.add_typer(config_app, name="config")
app.add_typer(binaries_app, name="binaries")


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


@binaries_app.command("which")
def binaries_which() -> None:
    """Show resolved paths for pg tools."""
    info = get_binary_info()
    
    table = Table(title="PostgreSQL Binaries Status", box=box.SIMPLE_HEAD)
    table.add_column("Tool")
    table.add_column("Path")
    table.add_column("Status")
    
    tools = ["pg_dump", "psql", "pg_restore"]
    for tool in tools:
        path = info[tool]
        exists = Path(path).exists()
        status = "✅ Found" if exists else "❌ Missing"
        table.add_row(tool, path, status)
    
    console.print(table)
    
    # Show additional info
    console.print(f"\n📋 Platform: {info['platform']}")
    console.print(f"📁 Embedded dir: {info['embedded_dir']}")
    console.print(f"💾 Cache dir: {info['cache_dir']}")


@binaries_app.command("download")
def binaries_download(
    force: bool = typer.Option(False, "--force", "-f", help="Force re-download even if binaries exist")
) -> None:
    """Download PostgreSQL binaries for current platform."""
    try:
        if not get_download_info():
            console.print(f"[red]No binaries available for your platform[/red]")
            console.print(f"Platform: {get_platform_tag()}")
            console.print("Please install PostgreSQL client tools manually.")
            raise typer.Exit(1)
            
        download_postgresql_binaries(force=force)
        console.print("[green]✅ Binaries ready![/green] Try: koggi binaries which")
        
    except KoggiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@binaries_app.command("status")
def binaries_status() -> None:
    """Check status of PostgreSQL binaries."""
    status = check_binaries_status()
    download_info = get_download_info()
    
    table = Table(title="Binaries Status", box=box.SIMPLE_HEAD)
    table.add_column("Tool")
    table.add_column("Available")
    table.add_column("Location")
    
    all_available = True
    for tool, available in status.items():
        if available:
            # Find where it's located
            from .binaries import find_binary
            binary_path = find_binary(tool)
            location = str(binary_path) if binary_path else "Unknown"
        else:
            location = "Not found"
            all_available = False
            
        status_icon = "✅" if available else "❌"
        table.add_row(tool, status_icon, location)
    
    console.print(table)
    
    if not all_available:
        if download_info:
            console.print("\n💡 To install missing binaries: [bold]koggi binaries download[/bold]")
        else:
            console.print(f"\n⚠️  No auto-download available for platform: {get_platform_tag()}")
            console.print("Please install PostgreSQL client tools manually.")


@binaries_app.command("clean")
def binaries_clean() -> None:
    """Remove downloaded PostgreSQL binaries."""
    if typer.confirm("Remove all downloaded PostgreSQL binaries?"):
        clean_binaries()
    else:
        console.print("Cancelled")
