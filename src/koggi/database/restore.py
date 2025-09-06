from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

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
        from rich.console import Console
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
            "-v",
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

    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:  # noqa: TRY003
        raise KoggiError(f"Restore failed: {e}") from e

    return used_file
