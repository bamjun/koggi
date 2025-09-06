from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .env_loader import DBProfile


def _kv_lines(profile: DBProfile) -> list[str]:
    p = profile.name.upper()
    out: list[str] = [f"# KOGGI profile {p}"]
    out.append(f"KOGGI_{p}_DB_NAME={profile.db_name}")
    out.append(f"KOGGI_{p}_DB_USER={profile.user}")
    if profile.password is not None:
        out.append(f"KOGGI_{p}_DB_PASSWORD={profile.password}")
    out.append(f"KOGGI_{p}_DB_HOST={profile.host}")
    out.append(f"KOGGI_{p}_DB_PORT={profile.port}")
    out.append(f"KOGGI_{p}_SSL_MODE={profile.ssl_mode}")
    out.append(f"KOGGI_{p}_BACKUP_DIR={profile.backup_dir.as_posix()}")
    return out


def _should_remove(line: str, prefix: str, keys: Iterable[str]) -> bool:
    s = line.strip()
    if not s or s.startswith("#"):
        return False
    if "=" not in s:
        return False
    k = s.split("=", 1)[0].strip()
    if not k.startswith(prefix):
        return False
    suffix = k[len(prefix) :]
    return suffix in set(keys)


def upsert_profile_env(env_path: Path, profile: DBProfile) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    lines = existing.splitlines()

    prefix = f"KOGGI_{profile.name.upper()}_"
    keys = (
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_HOST",
        "DB_PORT",
        "SSL_MODE",
        "BACKUP_DIR",
    )

    kept: list[str] = [ln for ln in lines if not _should_remove(ln, prefix, keys)]

    # Ensure trailing blank line
    if kept and kept[-1].strip():
        kept.append("")

    kept.extend(_kv_lines(profile))
    kept.append("")
    env_path.write_text("\n".join(kept), encoding="utf-8")

