"""
PostgreSQL binaries downloader.

Downloads and extracts PostgreSQL client tools for the current platform.
Copies the whole bin directory to ensure Windows DLL dependencies are present.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Optional

from rich.console import Console
from rich.progress import Progress, DownloadColumn, TransferSpeedColumn

from . import get_cache_dir, get_platform_tag
from ..exceptions import KoggiError

console = Console()

# URL templates for platform-specific binaries (version placeholder: {ver})
BINARY_URL_TEMPLATES: Dict[str, Dict[str, str]] = {
    # Windows x64 (EDB packaged binaries)
    "windows-x86_64": {
        "template": "https://get.enterprisedb.com/postgresql/postgresql-{ver}-1-windows-x64-binaries.zip",
        "extract_path": "pgsql/bin/",
    },
    # Linux x64 (Official PostgreSQL binaries)
    "linux-x86_64": {
        "template": "https://ftp.postgresql.org/pub/binary/v{ver}/linux/postgresql-{ver}-linux-x64-binaries.tar.xz",
        "extract_path": "usr/local/pgsql/bin/",
    },
    # macOS Intel
    "darwin-x86_64": {
        "template": "https://ftp.postgresql.org/pub/binary/v{ver}/macos/postgresql-{ver}-osx-binaries.zip",
        "extract_path": "usr/local/pgsql/bin/",
    },
    # macOS Apple Silicon
    "darwin-arm64": {
        "template": "https://ftp.postgresql.org/pub/binary/v{ver}/macos/postgresql-{ver}-osx-arm64-binaries.zip",
        "extract_path": "usr/local/pgsql/bin/",
    },
}

REQUIRED_TOOLS = ["pg_dump", "psql", "pg_restore"]


def _fetch_latest_version_from_ftp() -> Optional[str]:
    """Fetch latest stable version (e.g., '17.6') from PostgreSQL FTP source listing.

    We use the source directory as authoritative for latest version numbers,
    then compose platform-specific binary URLs using templates above.
    """
    try:
        with urllib.request.urlopen("https://ftp.postgresql.org/pub/source/") as r:  # noqa: S310
            html = r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None
    # Extract version strings like v17.6/
    import re

    versions = re.findall(r">v(\d+\.\d+)/<", html)
    if not versions:
        versions = re.findall(r"v(\d+\.\d+)/", html)
    if not versions:
        return None

    def key(v: str) -> tuple[int, int]:
        parts = v.split(".")
        return (int(parts[0]), int(parts[1]))

    latest = sorted(set(versions), key=key, reverse=True)[0]
    return latest


def get_download_info(version: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Get download info for current platform.

    If version is None, attempts to detect the latest stable version.
    Returns dict with keys: url, extract_path, version.
    """
    platform_tag = get_platform_tag()
    tpl = BINARY_URL_TEMPLATES.get(platform_tag)
    if not tpl:
        return None

    ver = version or _fetch_latest_version_from_ftp() or "17.6"
    url = tpl["template"].format(ver=ver)
    return {
        "url": url,
        "extract_path": tpl["extract_path"],
        "version": ver,
    }


def verify_checksum(file_path: Path, expected_sha256: str) -> bool:
    """Verify file SHA256 checksum."""
    if not expected_sha256:
        return True
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest().lower() == expected_sha256.lower()


def download_file(url: str, dest_path: Path, expected_size: Optional[int] = None) -> None:
    """Download file with progress bar."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    console.print("Downloading PostgreSQL binaries...")
    console.print(f"   URL: {url}")
    console.print(f"   Destination: {dest_path}")

    with Progress(
        *Progress.get_default_columns(),
        DownloadColumn(),
        TransferSpeedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading...", total=expected_size)

        def progress_hook(block_num: int, block_size: int, total_size: int) -> None:
            if total_size > 0 and not progress.tasks[task].total:
                progress.update(task, total=total_size)
            progress.update(task, advance=block_size)

        try:
            urllib.request.urlretrieve(url, dest_path, progress_hook)  # noqa: S310
        except Exception as e:  # noqa: BLE001
            raise KoggiError(f"Download failed: {e}") from e


def extract_archive(archive_path: Path, extract_to: Path, extract_path: str) -> None:
    """Extract archive and copy required tools and dependencies."""
    console.print("Extracting binaries...")

    temp_extract = extract_to / "temp_extract"
    temp_extract.mkdir(parents=True, exist_ok=True)

    try:
        name = archive_path.name.lower()
        if name.endswith(".zip"):
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(temp_extract)
        elif name.endswith((".tar.gz", ".tgz", ".tar.xz")):
            with tarfile.open(archive_path) as tf:
                tf.extractall(temp_extract)
        else:
            raise KoggiError(f"Unsupported archive format: {archive_path.suffix}")

        # Locate bin directory
        source_bin_dir = temp_extract / extract_path
        if not source_bin_dir.exists():
            for path in temp_extract.rglob("bin"):
                if path.is_dir():
                    source_bin_dir = path
                    break
        if not source_bin_dir.exists():
            raise KoggiError("Could not find bin directory in extracted archive")

        # Copy all files from bin directory to cache (exe + dll + etc)
        extract_to.mkdir(parents=True, exist_ok=True)
        for item in source_bin_dir.iterdir():
            if item.is_file():
                dst = extract_to / item.name
                shutil.copy2(item, dst)
                if platform.system() != "Windows":
                    try:
                        dst.chmod(0o755)
                    except Exception:
                        pass

        # Verify required tools are present
        missing = []
        for tool in REQUIRED_TOOLS:
            exe = f"{tool}.exe" if platform.system() == "Windows" else tool
            if not (extract_to / exe).exists():
                missing.append(tool)
        if missing:
            raise KoggiError("Archive missing required tools: " + ", ".join(missing))

        console.print(f"Successfully extracted {len(REQUIRED_TOOLS)} tools")

    finally:
        if temp_extract.exists():
            shutil.rmtree(temp_extract, ignore_errors=True)


def download_postgresql_binaries(
    force: bool = False,
    url: Optional[str] = None,
    version: Optional[str] = None,
) -> None:
    """Download and install PostgreSQL binaries for current platform."""
    platform_tag = get_platform_tag()
    console.print(f"Platform: {platform_tag}")

    info = get_download_info(version=version)
    if not info and not url:
        raise KoggiError(f"No PostgreSQL binaries available for platform: {platform_tag}. Provide --url to download a specific version.")

    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Fast-path if already installed
    if not force:
        if all((cache_dir / (f"{t}.exe" if platform.system() == "Windows" else t)).exists() for t in REQUIRED_TOOLS):
            console.print("✅ PostgreSQL binaries already installed")
            return

    final_url = url or info["url"]
    archive_path = cache_dir / Path(final_url).name

    # Download
    if force and archive_path.exists():
        try:
            archive_path.unlink()
        except Exception:
            pass
    if force or not archive_path.exists():
        download_file(final_url, archive_path)

    # Optionally verify checksum
    sha = (info or {}).get("sha256") or ""
    if sha and not verify_checksum(archive_path, sha):
        raise KoggiError("Downloaded file checksum verification failed")

    # Extract to cache/bin/<tag>
    extract_path = (info or {}).get("extract_path") or ""
    if not extract_path:
        # Try to autodetect within archive later; for now require extract_path via mapping
        # Fallback to common subdir names used by published archives
        extract_path = "pgsql/bin/"
    extract_archive(archive_path, cache_dir, extract_path)

    # Cleanup archive
    try:
        archive_path.unlink()
        console.print(f"Cleaned up download file: {archive_path.name}")
    except Exception:
        pass

    console.print("PostgreSQL binaries installation completed!")


def check_binaries_status() -> Dict[str, bool]:
    """Check which required binaries are available in cache dir."""
    cache_dir = get_cache_dir()
    status: Dict[str, bool] = {}
    for tool in REQUIRED_TOOLS:
        exe = f"{tool}.exe" if platform.system() == "Windows" else tool
        status[tool] = (cache_dir / exe).exists()
    return status


def clean_binaries() -> None:
    """Remove cached binaries (executables and DLLs)."""
    cache_dir = get_cache_dir()
    if not cache_dir.exists():
        console.print("No binaries cache found")
        return
    removed = 0
    for p in cache_dir.iterdir():
        try:
            if p.is_file():
                p.unlink()
                removed += 1
        except Exception:
            pass
    try:
        cache_dir.rmdir()
    except Exception:
        pass
    console.print(f"Removed {removed} files from {cache_dir}")
