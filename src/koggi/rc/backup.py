import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import box

from ..exceptions import KoggiError
from .config import RcConfig

console = Console()

def run_backup(config: RcConfig, dry_run: bool = False, verbose: Optional[bool] = None) -> None:
    """Run rclone backup for the given config."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_base = f"{config.remote}:{config.project_name}/{timestamp}"
    
    console.print(f"\n[bold blue]Starting Rclone Backup[/bold blue]")
    console.print(f"Remote: [cyan]{remote_base}[/cyan]")
    if dry_run:
        console.print("[yellow]WARNING: DRY RUN MODE - No files will be uploaded[/yellow]")
        
    if verbose is None:
        from rich.prompt import Confirm
        verbose = Confirm.ask("Do you want to see detailed backup progress log?", default=False)
    
    table = Table(box=box.SIMPLE_HEAD)
    table.add_column("Local Path", style="cyan")
    table.add_column("Remote Path", style="green")
    table.add_column("Status")
    
    # Check if rclone exists
    import shutil
    if not shutil.which("rclone"):
        raise KoggiError(
            "rclone not found. Please install rclone to use this feature.\n"
            "Download: https://rclone.org/downloads/"
        )
    
    success_count = 0
    fail_count = 0
    
    # Process each pattern in 'files'
    cwd = Path.cwd()
    for pattern in config.files:
        # Resolve glob
        # If it's a direct file or dir that exists, we just use it, 
        # but to support glob, we use Path.glob.
        # Note: glob doesn't support absolute paths well, so we assume relative to cwd.
        matched_paths = list(cwd.glob(pattern))
        
        if not matched_paths:
            table.add_row(pattern, "[dim]N/A[/dim]", "[yellow]No match[/yellow]")
            console.print(f"[yellow]Warning:[/yellow] No files matched pattern '{pattern}'")
            continue
            
        for path in matched_paths:
            # Calculate relative path to preserve directory structure on remote
            try:
                rel_path = path.relative_to(cwd)
            except ValueError:
                # If outside cwd, just use the name
                rel_path = Path(path.name)
            
            # For rclone, if it's a directory, we need to copy dir to dir.
            # If it's a file, we MUST use copyto, otherwise rclone will create a directory
            # with the file's name and put the file inside.
            remote_dest = f"{remote_base}/{rel_path}"
            
            # Prepare command
            if path.is_file():
                cmd = ["rclone", "copyto", str(path), remote_dest]
            else:
                cmd = ["rclone", "copy", str(path), remote_dest]
                
            if verbose:
                cmd.append("-P")
                
            if dry_run:
                cmd.append("--dry-run")
            
            try:
                # Run the command
                if verbose:
                    # In verbose mode, do not pipe stdout/stderr so it prints directly to the terminal
                    subprocess.run(
                        cmd, 
                        check=True
                    )
                else:
                    # In quiet mode, pipe stdout/stderr to hide it from terminal and parse only if failed
                    subprocess.run(
                        cmd, 
                        check=True, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        text=True
                    )
                table.add_row(str(rel_path), remote_dest, "[green]Success[/green]")
                success_count += 1
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.strip() if e.stderr else "See console logs above"
                table.add_row(str(rel_path), remote_dest, f"[red]Failed[/red] ({err_msg})")
                fail_count += 1
    
    console.print()
    console.print(table)
    
    if fail_count > 0:
        console.print(f"[red]Warning: Backup completed with {fail_count} errors. ({success_count} succeeded)[/red]")
    elif success_count > 0:
        console.print(f"[green]Backup completed successfully. ({success_count} items)[/green]")
    else:
        console.print("[yellow]No files were backed up.[/yellow]")
