import subprocess
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import IntPrompt, Confirm
from rich import box

from ..exceptions import KoggiError
from .config import RcConfig

console = Console()

def check_rclone():
    if not shutil.which("rclone"):
        raise KoggiError(
            "rclone not found. Please install rclone to use this feature.\n"
            "Download: https://rclone.org/downloads/"
        )

def list_backups(config: RcConfig) -> list[str]:
    """List available backups on the remote."""
    check_rclone()
    
    remote_dir = f"{config.remote}:{config.project_name}"
    
    try:
        # Use lsf to get just the directory names
        result = subprocess.run(
            ["rclone", "lsf", "--dirs-only", remote_dir],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        
        # Parse output: rclone lsf returns names with trailing '/'
        dirs = [d.strip("/") for d in result.stdout.splitlines() if d.strip()]
        
        # Sort in descending order (newest first assuming YYYYMMDD_HHMMSS format)
        dirs.sort(reverse=True)
        return dirs
        
    except subprocess.CalledProcessError as e:
        if "directory not found" in e.stderr.lower():
            return []
        raise KoggiError(f"Failed to list remote backups: {e.stderr.strip()}")

def run_restore(config: RcConfig, dest: Path) -> None:
    """Interactive restore process."""
    console.print(f"\n[bold blue]Starting Rclone Restore[/bold blue]")
    
    backups = list_backups(config)
    
    if not backups:
        console.print("[yellow]No backups found on remote.[/yellow]")
        return
        
    # Display table
    table = Table(title=f"Available Backups in {config.project_name}", box=box.SIMPLE_HEAD)
    table.add_column("No.", style="cyan", justify="right")
    table.add_column("Timestamp", style="green")
    
    for i, b in enumerate(backups, 1):
        table.add_row(str(i), b)
        
    console.print(table)
    
    # Ask user to select
    choice = IntPrompt.ask(
        "Select backup number to restore (0 to cancel)", 
        default=0,
        show_default=True
    )
    
    if choice == 0:
        console.print("[yellow]Restore cancelled.[/yellow]")
        return
        
    if not (1 <= choice <= len(backups)):
        console.print("[red]Invalid selection![/red]")
        return
        
    selected_backup = backups[choice - 1]
    
    console.print(f"\n[cyan]Selected:[/cyan] {selected_backup}")
    console.print(f"[cyan]Destination:[/cyan] {dest.absolute()}")
    
    if not Confirm.ask("\n[bold]Proceed with restore?[/bold]", default=True):
        console.print("[yellow]Restore cancelled.[/yellow]")
        return
        
    remote_src = f"{config.remote}:{config.project_name}/{selected_backup}"
    
    dest.mkdir(parents=True, exist_ok=True)
    
    # ---------------------------------------------------------
    # Handle conflicts: archive existing files before overwrite
    # ---------------------------------------------------------
    try:
        console.print("[cyan]Checking for conflicts with local files...[/cyan]")
        lsf_cmd = ["rclone", "lsf", "-R", "--files-only", remote_src]
        lsf_res = subprocess.run(
            lsf_cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        remote_files = [f.strip() for f in lsf_res.stdout.splitlines() if f.strip()]
        
        conflicts = []
        for file_rel in remote_files:
            local_path = dest / file_rel
            if local_path.exists() and local_path.is_file():
                conflicts.append(local_path)
                
        if conflicts:
            now_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_zip_dir = dest / ".koggi" / "backup"
            backup_zip_dir.mkdir(parents=True, exist_ok=True)
            zip_path = backup_zip_dir / f"restore-{now_ts}.zip"
            
            console.print(f"[yellow]Archiving {len(conflicts)} conflicting local files to .koggi/backup/restore-{now_ts}.zip...[/yellow]")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for conflict_file in conflicts:
                    arcname = conflict_file.relative_to(dest)
                    zf.write(conflict_file, arcname)
                    
            # Delete archived files securely
            for conflict_file in conflicts:
                try:
                    conflict_file.unlink()
                except OSError as e:
                    console.print(f"[red]Warning: Could not remove {conflict_file.name} ({e})[/red]")
                    
            console.print("[green]Conflict resolution complete.[/green]")
    except Exception as e:
        console.print(f"[red]Warning: Failed to process conflicts: {e}[/red]")
    # ---------------------------------------------------------
    
    # Run rclone copy from remote to local dest
    cmd = ["rclone", "copy", remote_src, str(dest)]
    
    try:
        console.print(f"Executing: {' '.join(cmd)}")
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        console.print("[green]Restore completed successfully![/green]")
    except subprocess.CalledProcessError as e:
        raise KoggiError(f"Restore failed: {e.stderr.strip()}")
