from __future__ import annotations

import datetime as dt
import os
import subprocess
import threading
import time
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ..config.env_loader import DBProfile
from ..exceptions import KoggiError
from ..binaries import get_pg_dump_path, find_binary


console = Console()


def backup_database(
    profile: DBProfile,
    *,
    output: Path | None = None,
    fmt: str = "custom",
    compress: bool = False,
) -> Path:
    """Run pg_dump to create a backup for the given profile.
    
    Default format is 'custom' which creates .backup files with compression support.
    Returns the output file path.
    """
    pg_dump_path = get_pg_dump_path()
    
    # Check if pg_dump binary exists
    if not pg_dump_path.exists():
        raise KoggiError(
            f"pg_dump not found at {pg_dump_path}. "
            "Install PostgreSQL client tools or use 'koggi binaries download' to get embedded binaries."
        )
    
    pg_dump = str(pg_dump_path)

    profile.backup_dir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = ".backup" if fmt.lower() in {"custom", "c"} else ".sql"
    default_name = f"{profile.db_name}_{ts}{ext}"
    out = (output or (profile.backup_dir / default_name)).resolve()

    cmd = [
        pg_dump,
        "-h",
        profile.host,
        "-p",
        str(profile.port),
        "-U",
        profile.user,
        "-d",
        profile.db_name,
        "-f",
        str(out),
    ]

    if fmt.lower() in {"custom", "c"}:
        cmd.extend(["-F", "c"])  # custom format

    if compress and fmt.lower() in {"custom", "c"}:
        cmd.extend(["-Z", "9"])  # compression level for custom format

    env = os.environ.copy()
    if profile.password:
        env["PGPASSWORD"] = profile.password
    env["PGSSLMODE"] = profile.ssl_mode

    # Execute backup with progress tracking
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold green]Creating backup..."),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("Backing up", total=None)  # Indeterminate progress
        
        try:
            # Run the backup process
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # Start progress animation in background
            progress_active = True
            def update_progress():
                while progress_active and process.poll() is None:
                    progress.advance(task)
                    time.sleep(0.2)
            
            # Threading already imported at top
            progress_thread = threading.Thread(target=update_progress, daemon=True)
            progress_thread.start()
            
            # Wait for process to complete and get outputs
            stdout, stderr = process.communicate(timeout=300)  # 5 minute timeout
            progress_active = False  # Stop progress animation
            return_code = process.returncode
            
            # Filter error/warning lines from stderr
            error_lines = []
            if stderr:
                for line in stderr.split('\n'):
                    line = line.strip()
                    if line and ('error' in line.lower() or 'failed' in line.lower() or 'warning' in line.lower()):
                        error_lines.append(line)
            
            # Check for errors
            if return_code != 0:
                error_msg = f"Backup failed with exit code {return_code}"
                if error_lines:
                    error_msg += f"\nErrors:\n" + "\n".join(error_lines)
                elif stderr:
                    error_msg += f"\nOutput: {stderr}"
                raise KoggiError(error_msg)
                
            # Show any warnings/errors that occurred during backup
            if error_lines:
                console.print("\n[yellow]⚠️  Warnings/Errors during backup:[/yellow]")
                for line in error_lines:
                    console.print(f"[dim]  {line}[/dim]")
                    
        except subprocess.TimeoutExpired:
            progress_active = False
            if process:
                process.kill()
                process.wait()
            raise KoggiError("Backup operation timed out (5 minutes)")
        except Exception as e:
            progress_active = False
            if process and process.poll() is None:
                process.kill()
                process.wait()
            raise KoggiError(f"Backup failed: {e}") from e

    return out
