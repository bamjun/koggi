"""
Embedded PostgreSQL binaries management.

Provides automatic detection and fallback for PostgreSQL client tools:
1. Environment variables (KOGGI_PG_DUMP, etc.)
2. Embedded binaries in package (_bin/<os>-<arch>/)
3. User cache directory (~/.cache/koggi/bin/<tag>/)
4. System PATH
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Optional

__all__ = [
    "get_pg_dump_path",
    "get_psql_path", 
    "get_pg_restore_path",
    "get_platform_tag",
    "find_binary"
]


def get_platform_tag() -> str:
    """Get platform tag for binary directory (e.g., windows-x86_64)."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Normalize machine names
    if machine in ("amd64", "x86_64"):
        machine = "x86_64"
    elif machine in ("i386", "i686", "x86"):
        machine = "x86"
    elif machine in ("aarch64", "arm64"):
        machine = "arm64"
    
    return f"{system}-{machine}"


def get_cache_dir() -> Path:
    """Get user cache directory for binaries."""
    if platform.system() == "Windows":
        cache_base = Path(os.environ.get("LOCALAPPDATA", "~\\AppData\\Local"))
    else:
        cache_base = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache"))
    
    return (cache_base / "koggi" / "bin" / get_platform_tag()).expanduser()


def get_embedded_dir() -> Path:
    """Get embedded binaries directory in package."""
    return Path(__file__).parent.parent / "_bin" / get_platform_tag()


def find_binary(name: str, env_var: Optional[str] = None) -> Optional[Path]:
    """
    Find PostgreSQL binary with fallback priority:
    1. Environment variable
    2. Embedded binaries 
    3. User cache
    4. System PATH
    """
    exe_name = f"{name}.exe" if platform.system() == "Windows" else name
    
    # 1. Environment variable override
    if env_var and (env_path := os.environ.get(env_var)):
        env_binary = Path(env_path)
        if env_binary.is_file():
            return env_binary
    
    # 2. Embedded binaries in package
    embedded_binary = get_embedded_dir() / exe_name
    if embedded_binary.is_file():
        return embedded_binary
    
    # 3. User cache directory
    cache_binary = get_cache_dir() / exe_name  
    if cache_binary.is_file():
        return cache_binary
    
    # 4. System PATH
    if system_path := shutil.which(name):
        return Path(system_path)
    
    return None


def get_pg_dump_path() -> Path:
    """Get pg_dump binary path with fallbacks."""
    if binary := find_binary("pg_dump", "KOGGI_PG_DUMP"):
        return binary
    
    # If not found, return expected cache location for download
    return get_cache_dir() / ("pg_dump.exe" if platform.system() == "Windows" else "pg_dump")


def get_psql_path() -> Path:
    """Get psql binary path with fallbacks.""" 
    if binary := find_binary("psql", "KOGGI_PSQL"):
        return binary
        
    return get_cache_dir() / ("psql.exe" if platform.system() == "Windows" else "psql")


def get_pg_restore_path() -> Path:
    """Get pg_restore binary path with fallbacks."""
    if binary := find_binary("pg_restore", "KOGGI_PG_RESTORE"):
        return binary
        
    return get_cache_dir() / ("pg_restore.exe" if platform.system() == "Windows" else "pg_restore")


def ensure_binaries_available() -> bool:
    """Check if all required binaries are available."""
    required_tools = ["pg_dump", "psql", "pg_restore"]
    
    for tool in required_tools:
        if not find_binary(tool):
            return False
    
    return True


def get_binary_info() -> dict[str, str]:
    """Get information about resolved binary paths."""
    return {
        "pg_dump": str(get_pg_dump_path()),
        "psql": str(get_psql_path()),
        "pg_restore": str(get_pg_restore_path()),
        "platform": get_platform_tag(),
        "embedded_dir": str(get_embedded_dir()),
        "cache_dir": str(get_cache_dir()),
    }