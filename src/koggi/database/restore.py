from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..config.env_loader import DBProfile
from ..exceptions import KoggiError


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


def restore_database(profile: DBProfile, *, backup_file: Optional[Path] = None) -> Path:
    """Restore the database from backup file.

    If backup_file is None, pick the latest file in the profile backup_dir.
    Returns the backup file used.
    """
    pg_restore = shutil.which("pg_restore")
    psql = shutil.which("psql")
    if not (pg_restore and psql):
        # not strictly needed both; but psql is needed for .sql
        pass

    used_file = backup_file or _pick_latest_backup(profile.backup_dir)
    if not used_file or not used_file.exists():
        raise KoggiError("No backup file found to restore.")
    used_file = used_file.resolve()

    env = os.environ.copy()
    if profile.password:
        env["PGPASSWORD"] = profile.password
    env["PGSSLMODE"] = profile.ssl_mode

    suffix = used_file.suffix.lower()
    if suffix in {".backup", ".dump"}:
        if not pg_restore:
            raise KoggiError("pg_restore not found in PATH.")
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
        if not psql:
            raise KoggiError("psql not found in PATH.")
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

