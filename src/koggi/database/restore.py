from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.live import Live

from ..config.env_loader import DBProfile
from ..exceptions import KoggiError
from ..binaries import get_pg_restore_path, get_psql_path
from ..ui.backup_selector import interactive_backup_selector, quick_latest_selector
from .cleanup import clean_and_recreate_database, check_database_exists, get_database_size


def _pick_latest_backup(backup_dir: Path) -> Optional[Path]:
    if not backup_dir.exists():
        return None
    candidates = [
        p
        for p in backup_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".sql", ".backup", ".dump"}
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def restore_database(
    profile: DBProfile, 
    *, 
    backup_file: Optional[Path] = None, 
    interactive: bool = True, 
    clean: bool = False
) -> Path:
    """Restore the database from backup file.

    If backup_file is None, pick the latest file in the profile backup_dir.
    If clean=True, drops and recreates the database before restore.
    Returns the backup file used.
    """
    pg_restore_path = get_pg_restore_path()
    psql_path = get_psql_path()
    
    # Check if required binaries exist
    if not pg_restore_path.exists() and not psql_path.exists():
        raise KoggiError(
            f"Neither pg_restore ({pg_restore_path}) nor psql ({psql_path}) found. "
            "Install PostgreSQL client tools or use 'koggi binaries download' to get embedded binaries."
        )
    
    pg_restore = str(pg_restore_path)
    psql = str(psql_path)

    # Determine which file to use
    if backup_file:
        # Specific file provided
        used_file = backup_file
    elif interactive:
        # Interactive selection
        used_file = interactive_backup_selector(profile.backup_dir)
        if not used_file:
            raise KoggiError("No backup file selected.")
    else:
        # Auto-select latest (non-interactive mode)
        used_file = quick_latest_selector(profile.backup_dir)
        if not used_file:
            raise KoggiError("No backup files found in backup directory.")
    
    if not used_file.exists():
        raise KoggiError(f"Backup file does not exist: {used_file}")
    
    used_file = used_file.resolve()

    # Clean database if requested
    if clean:
        console = Console()
        
        # Show current database info before cleaning
        if check_database_exists(profile, profile.db_name):
            db_size = get_database_size(profile, profile.db_name)
            console.print(f"📊 Current database size: {db_size}")
        
        # Perform clean operation (skip confirmation when --clean flag is used)
        if not clean_and_recreate_database(profile, confirm=False):
            raise KoggiError("Database cleanup was cancelled")

    env = os.environ.copy()
    if profile.password:
        env["PGPASSWORD"] = profile.password
    env["PGSSLMODE"] = profile.ssl_mode

    suffix = used_file.suffix.lower()
    if suffix in {".backup", ".dump"}:
        # Use pg_restore for custom format backups
        if not pg_restore_path.exists():
            raise KoggiError(f"pg_restore required for {suffix} files but not found at {pg_restore_path}")
        
        cmd = [
            pg_restore,
            "-h",
            profile.host,
            "-p",
            str(profile.port),
            "-U",
            profile.user,
            "-d",
            profile.db_name,
            "--no-password",
            str(used_file),
        ]
    else:
        # Use psql for SQL text files
        if not psql_path.exists():
            raise KoggiError(f"psql required for {suffix} files but not found at {psql_path}")
            
        cmd = [
            psql,
            "-h",
            profile.host,
            "-p",
            str(profile.port),
            "-U",
            profile.user,
            "-d",
            profile.db_name,
            "-f",
            str(used_file),
        ]

    # Execute restore with progress tracking
    console = Console()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Restoring database..."),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("Restoring", total=None)  # Indeterminate progress
        
        try:
            # Run the restore process
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
                error_msg = f"Restore failed with exit code {return_code}"
                if error_lines:
                    error_msg += f"\nErrors:\n" + "\n".join(error_lines)
                elif stderr:
                    error_msg += f"\nOutput: {stderr}"
                raise KoggiError(error_msg)
                
            # Show any warnings/errors that occurred during restore
            if error_lines:
                console.print("\n[yellow]⚠️  Warnings/Errors during restore:[/yellow]")
                for line in error_lines:
                    console.print(f"[dim]  {line}[/dim]")
                    
        except subprocess.TimeoutExpired:
            progress_active = False
            if process:
                process.kill()
                process.wait()
            raise KoggiError("Restore operation timed out (5 minutes)")
        except Exception as e:
            progress_active = False
            if process and process.poll() is None:
                process.kill()
                process.wait()
            raise KoggiError(f"Restore failed: {e}") from e

    return used_file
