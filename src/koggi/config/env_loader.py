from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv


@dataclass
class DBProfile:
    name: str
    db_name: str
    user: str
    password: str | None
    host: str = "localhost"
    port: int = 5432
    ssl_mode: str = "prefer"
    backup_dir: Path = Path("./backups")

    @property
    def is_production(self) -> bool:
        return self.name.upper() in {"PROD", "PRODUCTION"}


def _get(env: dict, profile: str, key: str, default: str | None = None) -> str | None:
    return env.get(f"KOGGI_{profile}_{key}", default)


def load_profiles() -> Dict[str, DBProfile]:
    """Load profiles from environment (and .env if present).

    Looks for keys like KOGGI_<PROFILE>_DB_NAME, KOGGI_<PROFILE>_DB_USER, etc.
    Recognized keys: DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, SSL_MODE, BACKUP_DIR.
    """
    load_dotenv(override=False)
    env = {k: v for k, v in os.environ.items() if k.startswith("KOGGI_")}
    profiles: dict[str, dict[str, str]] = {}

    for k, v in env.items():
        # Expect form KOGGI_<PROFILE>_<KEY>
        parts = k.split("_", 2)
        if len(parts) != 3:
            continue
        _, profile, suffix = parts
        profiles.setdefault(profile, {})[suffix] = v

    result: Dict[str, DBProfile] = {}
    for profile, values in profiles.items():
        db_name = values.get("DB_NAME")
        user = values.get("DB_USER")
        if not db_name or not user:
            # Incomplete profile; skip
            continue
        password = values.get("DB_PASSWORD")
        host = values.get("DB_HOST", "localhost")
        port = int(values.get("DB_PORT", 5432))
        ssl_mode = values.get("SSL_MODE", "prefer")
        backup_dir = Path(values.get("BACKUP_DIR", "./backups")).resolve()
        result[profile] = DBProfile(
            name=profile,
            db_name=db_name,
            user=user,
            password=password,
            host=host,
            port=port,
            ssl_mode=ssl_mode,
            backup_dir=backup_dir,
        )

    # Ensure DEFAULT exists if partially provided
    if "DEFAULT" in profiles and "DEFAULT" not in result:
        # DEFAULT was present but incomplete; ignore quietly
        pass

    return dict(sorted(result.items(), key=lambda kv: (kv[0] != "DEFAULT", kv[0])))

