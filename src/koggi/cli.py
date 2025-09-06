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
pg_app.add_typer(binaries_app, name="binaries")


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
    table.add_column("Restore")
    table.add_column("Backup Dir")

    for name, p in profiles.items():
        restore_status = "✅ Allowed" if p.allow_restore else "❌ Disabled"
        table.add_row(name, p.db_name, p.host, str(p.port), p.ssl_mode, restore_status, str(p.backup_dir))

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


@config_app.command("init")
def config_init(
    profile: str = typer.Option("DEFAULT", "-p", "--profile", help="Profile name"),
    env_path: Path = typer.Option(Path(".env"), "--env-path", help="Path to .env file"),
    save_password: bool = typer.Option(True, help="Save password into .env (plaintext)"),
):
    """Interactive setup to create/update a profile in .env."""
    from .config.init import upsert_profile_env
    from .config.env_loader import DBProfile

    pname = profile.upper()

    db_name = typer.prompt("DB name")
    user = typer.prompt("DB user")
    password = None
    if save_password:
        password = typer.prompt("DB password", hide_input=True, confirmation_prompt=False)
    host = typer.prompt("Host", default="localhost")
    port = int(typer.prompt("Port", default="5432"))
    ssl_mode = typer.prompt("SSL mode", default="prefer")
    backup_dir = Path(typer.prompt("Backup dir", default="./backups")).as_posix()

    prof = DBProfile(
        name=pname,
        db_name=db_name,
        user=user,
        password=password,
        host=host,
        port=port,
        ssl_mode=ssl_mode,
        backup_dir=Path(backup_dir),
    )

    upsert_profile_env(env_path, prof)
    console.print(f"[green]Profile '{pname}' saved to {env_path}[/green]")


@pg_app.command("backup")
def pg_backup(
    profile: str = typer.Option("DEFAULT", "-p", "--profile", help="Profile name"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output file path"),
    fmt: str = typer.Option("custom", "--fmt", help="Backup format: plain|custom"),
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
    backup_file: Optional[Path] = typer.Argument(None, help="Backup file path; if omitted, shows interactive selector"),
    latest: bool = typer.Option(False, "--latest", help="Auto-select latest backup without interaction"),
    clean: bool = typer.Option(False, "-c", "--clean", help="Drop and recreate database before restore (destructive!)"),
):
    """Restore a database from a backup file with interactive file selection."""
    profiles = load_profiles()
    if profile not in profiles:
        console.print(f"[red]Profile '{profile}' not found.[/red]")
        raise typer.Exit(code=1)
    
    # Check restore permission
    profile_config = profiles[profile]
    if not profile_config.allow_restore:
        console.print(f"[red]❌ Restore operation is disabled for profile '{profile}'[/red]")
        console.print(f"[dim]Set KOGGI_{profile}_ALLOW_RESTORE=true in .env to enable restore[/dim]")
        raise typer.Exit(code=1)
    
    try:
        # Interactive mode unless --latest flag or specific file provided
        interactive_mode = backup_file is None and not latest
        
        used_file = restore_database(
            profile_config, 
            backup_file=backup_file, 
            interactive=interactive_mode,
            clean=clean
        )
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


@binaries_app.command("download")
def binaries_download(
    url: Optional[str] = typer.Option(
        None,
        "--url",
        help="URL to a zip/tar archive containing pg_dump, psql, pg_restore",
    ),
    dest: Optional[Path] = typer.Option(
        None,
        "--dest",
        help="Destination directory for binaries (defaults to user cache)",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files"),
):
    """Download and install embedded PostgreSQL client binaries."""
    import tempfile
    import urllib.request
    import zipfile
    import tarfile
    import shutil

    from .binaries import _user_cache_dir, detect_platform

    target_dir = dest or _user_cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    if not url:
        tag = detect_platform().tag
        console.print(
            f"[yellow]No URL provided.[/yellow] Please pass --url to a zip/tar archive for {tag}.\n"
            "Archive must contain pg_dump, psql, pg_restore.\n"
            "Tip: place manually under the printed destination or set KOGGI_* env vars."
        )
        console.print(f"Destination: {target_dir}")
        raise typer.Exit(code=2)

    console.print(f"Downloading from: {url}")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "pkg.bin"
        try:
            with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:  # noqa: S310
                shutil.copyfileobj(r, f)
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Download failed:[/red] {e}")
            raise typer.Exit(code=1)

        extract_dir = Path(td) / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            if zipfile.is_zipfile(tmp):
                with zipfile.ZipFile(tmp) as zf:
                    zf.extractall(extract_dir)
            elif tarfile.is_tarfile(tmp):
                with tarfile.open(tmp) as tf:
                    tf.extractall(extract_dir)  # noqa: S202
            else:
                # Assume single binary? copy as-is
                (extract_dir / tmp.name).write_bytes(tmp.read_bytes())
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Extract failed:[/red] {e}")
            raise typer.Exit(code=1)

        # Find tools within extract_dir
        info = detect_platform()
        names = [f"pg_dump{'.exe' if info.os_name=='windows' else ''}",
                 f"psql{'.exe' if info.os_name=='windows' else ''}",
                 f"pg_restore{'.exe' if info.os_name=='windows' else ''}"]

        found = {}
        for root, _, files in os.walk(extract_dir):
            for n in names:
                if n in files and n not in found:
                    found[n] = Path(root) / n

        if not all(n in found for n in names):
            missing = [n for n in names if n not in found]
            console.print(
                f"[red]Archive missing required tools:[/red] {', '.join(missing)}"
            )
            raise typer.Exit(code=1)

        # Copy to target_dir
        for n, src in found.items():
            dst = target_dir / n
            if dst.exists() and not force:
                console.print(f"[yellow]Skip existing[/yellow]: {dst}")
                continue
            shutil.copy2(src, dst)
            if os.name != "nt":
                mode = dst.stat().st_mode
                dst.chmod(mode | 0o111)

    console.print("[green]Binaries installed to:[/green] " + str(target_dir))
    # Show resolution
    binaries_which()
    
    # Show additional info
    console.print(f"\n📋 Platform: {info['platform']}")
    console.print(f"📁 Embedded dir: {info['embedded_dir']}")
    console.print(f"💾 Cache dir: {info['cache_dir']}")


@binaries_app.command("download")
def binaries_download(
    force: bool = typer.Option(False, "--force", "-f", help="Force re-download even if binaries exist"),
    url: Optional[str] = typer.Option(None, "--url", help="Override download URL (zip/tar archive)"),
    version: Optional[str] = typer.Option(None, "--version", help="PostgreSQL version (e.g., 17.6). Defaults to latest"),
) -> None:
    """Download PostgreSQL binaries for current platform."""
    try:
        if not get_download_info():
            console.print(f"[red]No binaries available for your platform[/red]")
            console.print(f"Platform: {get_platform_tag()}")
            console.print("Please install PostgreSQL client tools manually.")
            raise typer.Exit(1)
            
        download_postgresql_binaries(force=force, url=url, version=version)
        console.print("[green]Binaries ready![/green] Try: koggi binaries which")
        
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

