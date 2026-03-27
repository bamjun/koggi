import typer
from pathlib import Path
from rich.console import Console

from ..exceptions import KoggiError
from .config import RcConfig, load_rc_config, save_rc_config, find_rc_config
from .backup import run_backup
from .restore import run_restore
from .delete import run_delete

console = Console()
rc_app = typer.Typer(help="Cloud backup via Rclone")

@rc_app.command("init")
def rc_init() -> None:
    """Create a new .koggi/rclone/setting.json configuration."""
    from rich.prompt import Prompt
    
    config_path = Path.cwd() / ".koggi" / "rclone" / "setting.json"
    
    if config_path.exists():
        from rich.prompt import Confirm
        if not Confirm.ask("Configuration already exists. Overwrite?"):
            console.print("Cancelled.")
            raise typer.Exit()
            
    project_name = Prompt.ask("Project name", default=Path.cwd().name)
    remote_name = Prompt.ask("Rclone remote name", default="gdrive")
    
    console.print("\n[cyan]Enter paths to backup (press Enter with empty line to finish).[/cyan]")
    console.print("[dim]Supports glob patterns, e.g., 'data', 'configs/*.yml', '**/*.py'[/dim]")
    
    files = []
    while True:
        path = Prompt.ask("Path to backup").strip()
        if not path:
            break
        files.append(path)
        
    if not files:
        console.print("[red]At least one path is required.[/red]")
        raise typer.Exit(1)
        
    config = RcConfig(
        project_name=project_name,
        remote=remote_name,
        files=files
    )
    
    try:
        save_rc_config(config)
        console.print(f"[green]OK: Configuration saved to {config_path.relative_to(Path.cwd())}[/green]")
    except KoggiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@rc_app.command("backup")
def rc_backup(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would be transferred without uploading")
) -> None:
    """Backup configured files to remote storage."""
    try:
        find_rc_config()  # check if exists
        config = load_rc_config()
        run_backup(config, dry_run=dry_run)
    except KoggiError as e:
        console.print(f"{e}")
        raise typer.Exit(1)


@rc_app.command("restore")
def rc_restore(
    dest: Path = typer.Option(Path.cwd(), "--dest", "-d", help="Destination path to restore files to")
) -> None:
    """Restore from remote backup (Interactive)."""
    try:
        find_rc_config()
        config = load_rc_config()
        run_restore(config, dest)
    except KoggiError as e:
        console.print(f"{e}")
        raise typer.Exit(1)


@rc_app.command("delete")
def rc_delete() -> None:
    """Delete backups from remote storage (Interactive)."""
    try:
        find_rc_config()
        config = load_rc_config()
        run_delete(config)
    except KoggiError as e:
        console.print(f"{e}")
        raise typer.Exit(1)
