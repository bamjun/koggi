from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

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

    with Progress(transient=True) as progress:
        task = progress.add_task("Creating backup...", total=None)
        try:
            subprocess.run(cmd, env=env, check=True)
        except subprocess.CalledProcessError as e:  # noqa: TRY003
            raise KoggiError(f"Backup failed: {e}") from e
        finally:
            progress.update(task, completed=1)

    return out
