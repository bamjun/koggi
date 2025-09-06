from __future__ import annotations

import contextlib
from typing import Tuple

import psycopg2

from ..config.env_loader import DBProfile


def test_connection(profile: DBProfile) -> Tuple[bool, str]:
    """Attempt to connect to the DB and return (ok, message)."""
    dsn = (
        f"dbname={profile.db_name} user={profile.user} host={profile.host} "
        f"port={profile.port} sslmode={profile.ssl_mode}"
    )
    try:
        with contextlib.closing(
            psycopg2.connect(dsn, password=profile.password)
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                ver = cur.fetchone()[0]
                return True, ver
    except Exception as e:  # noqa: BLE001
        return False, str(e)

