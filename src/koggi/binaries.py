from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from importlib.resources import files as pkg_files  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    from importlib_resources import files as pkg_files  # type: ignore[no-redef]

from .exceptions import KoggiError


@dataclass(frozen=True)
class PlatformInfo:
    os_name: str
    arch: str

    @property
    def tag(self) -> str:
        return f"{self.os_name}-{self.arch}"

    @property
    def exe_suffix(self) -> str:
        return ".exe" if self.os_name == "windows" else ""


def _normalize_arch(raw: str) -> str:
    r = raw.lower()
    if r in {"x86_64", "amd64", "x64"}:
        return "x86_64"
    if r in {"aarch64", "arm64"}:
        return "arm64"
    if r in {"armv7l", "armv7"}:
        return "armv7"
    return r


def detect_platform() -> PlatformInfo:
    sys_plat = sys.platform
    if sys_plat.startswith("win"):
        os_name = "windows"
    elif sys_plat.startswith("darwin"):
        os_name = "darwin"
    elif sys_plat.startswith("linux"):
        os_name = "linux"
    else:
        os_name = sys_plat
    arch = _normalize_arch(platform.machine())
    return PlatformInfo(os_name=os_name, arch=arch)


def _env_override(var: str) -> Optional[Path]:
    val = os.environ.get(var)
    if val:
        p = Path(val)
        if p.exists():
            return p
    return None


def _embedded_dir() -> Path:
    # Try package data directory: koggi/_bin/<tag>
    tag = detect_platform().tag
    root = pkg_files("koggi")
    candidate = root / "_bin" / tag
    try:
        path = Path(str(candidate))
    except Exception:
        path = Path(".") / "koggi" / "_bin" / tag  # fallback
    return path


def _user_cache_dir() -> Path:
    # Where a user might place downloaded binaries without modifying site-packages
    base = os.environ.get("KOGGI_CACHE_DIR")
    if base:
        return Path(base)
    if detect_platform().os_name == "windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "koggi" / "bin" / detect_platform().tag


def _lookup_binary(name: str) -> Optional[Path]:
    info = detect_platform()
    exe = f"{name}{info.exe_suffix}"

    # 1) Environment overrides
    env_map = {
        "pg_dump": "KOGGI_PG_DUMP",
        "psql": "KOGGI_PSQL",
        "pg_restore": "KOGGI_PG_RESTORE",
    }
    if name in env_map:
        p = _env_override(env_map[name])
        if p:
            return p

    # 2) Packaged embedded directory
    emb_dir = _embedded_dir()
    cand = emb_dir / exe
    if cand.exists():
        return cand

    # 3) User cache directory
    cache_dir = _user_cache_dir()
    cand2 = cache_dir / exe
    if cand2.exists():
        return cand2

    # 4) System PATH
    path = shutil.which(name)
    return Path(path) if path else None


def _ensure_executable(p: Path) -> None:
    try:
        if p.exists() and os.name != "nt":
            mode = p.stat().st_mode
            p.chmod(mode | 0o111)
    except Exception:
        pass


def _require(name: str) -> Path:
    p = _lookup_binary(name)
    if not p:
        info = detect_platform()
        hint = (
            f"No '{name}' found. Provide embedded binaries in 'koggi/_bin/{info.tag}/' "
            f"or place them in '{_user_cache_dir()}', or set env var KOGGI_{name.upper()}."
        )
        raise KoggiError(hint)
    _ensure_executable(p)
    return p


def get_pg_dump_path() -> Path:
    return _require("pg_dump")


def get_psql_path() -> Path:
    return _require("psql")


def get_pg_restore_path() -> Path:
    return _require("pg_restore")

