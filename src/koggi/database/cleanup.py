"""
Database cleanup and recreation utilities.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from ..config.env_loader import DBProfile
from ..exceptions import KoggiError
from ..binaries import get_psql_path

console = Console()


def drop_database(profile: DBProfile, database_name: str) -> None:
    """Drop a database using psql."""
    psql_path = get_psql_path()
    
    if not psql_path.exists():
        raise KoggiError(f"psql not found at {psql_path}")
    
    # Connect to 'postgres' database to drop the target database
    cmd = [
        str(psql_path),
        "-h", profile.host,
        "-p", str(profile.port),
        "-U", profile.user,
        "-d", "postgres",  # Connect to postgres DB to drop target
        "-c", f'DROP DATABASE IF EXISTS "{database_name}";'
    ]
    
    env = os.environ.copy()
    if profile.password:
        env["PGPASSWORD"] = profile.password
    env["PGSSLMODE"] = profile.ssl_mode
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        console.print(f"[yellow]🗑️  Dropped database:[/yellow] {database_name}")
    except subprocess.CalledProcessError as e:
        # If database doesn't exist, that's fine
        stderr_text = e.stderr or ""
        if "does not exist" in stderr_text:
            console.print(f"[dim]Database {database_name} did not exist[/dim]")
        else:
            raise KoggiError(f"Failed to drop database: {stderr_text}")


def create_database(profile: DBProfile, database_name: str) -> None:
    """Create a database using psql."""
    psql_path = get_psql_path()
    
    if not psql_path.exists():
        raise KoggiError(f"psql not found at {psql_path}")
    
    # Connect to 'postgres' database to create the target database
    cmd = [
        str(psql_path),
        "-h", profile.host,
        "-p", str(profile.port),
        "-U", profile.user,
        "-d", "postgres",  # Connect to postgres DB to create target
        "-c", f'CREATE DATABASE "{database_name}";'
    ]
    
    env = os.environ.copy()
    if profile.password:
        env["PGPASSWORD"] = profile.password
    env["PGSSLMODE"] = profile.ssl_mode
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        console.print(f"[green]✅ Created database:[/green] {database_name}")
    except subprocess.CalledProcessError as e:
        stderr_text = e.stderr or ""
        if "already exists" in stderr_text:
            console.print(f"[yellow]Database {database_name} already exists[/yellow]")
        else:
            raise KoggiError(f"Failed to create database: {stderr_text}")


def clean_and_recreate_database(profile: DBProfile, confirm: bool = True) -> bool:
    """
    Drop and recreate the database for clean restore.
    
    Returns True if operation completed, False if cancelled.
    """
    database_name = profile.db_name
    
    # Safety confirmation
    if confirm:
        console.print(f"[red]⚠️  WARNING: This will completely delete the database '{database_name}'[/red]")
        console.print(f"Host: {profile.host}:{profile.port}")
        console.print("All data will be permanently lost!")
        
        if not Confirm.ask(f"\nProceed with dropping and recreating '{database_name}'?", default=False):
            console.print("[yellow]Operation cancelled[/yellow]")
            return False
    
    console.print(f"\n[bold]🔄 Cleaning database: {database_name}[/bold]")
    
    # Step 1: Drop database
    with console.status(f"Dropping database {database_name}..."):
        drop_database(profile, database_name)
    
    # Step 2: Recreate database  
    with console.status(f"Creating database {database_name}..."):
        create_database(profile, database_name)
    
    console.print("[green]✅ Database cleaned and ready for restore[/green]")
    return True


def check_database_exists(profile: DBProfile, database_name: str) -> bool:
    """Check if a database exists."""
    psql_path = get_psql_path()
    
    if not psql_path.exists():
        raise KoggiError(f"psql not found at {psql_path}")
    
    cmd = [
        str(psql_path),
        "-h", profile.host,
        "-p", str(profile.port),
        "-U", profile.user,
        "-d", "postgres",
        "-t",  # Tuples only (no headers)
        "-c", f"SELECT 1 FROM pg_database WHERE datname='{database_name}';"
    ]
    
    env = os.environ.copy()
    if profile.password:
        env["PGPASSWORD"] = profile.password
    env["PGSSLMODE"] = profile.ssl_mode
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False


def get_database_size(profile: DBProfile, database_name: str) -> str:
    """Get database size in human readable format."""
    psql_path = get_psql_path()
    
    if not psql_path.exists():
        return "Unknown"
    
    cmd = [
        str(psql_path),
        "-h", profile.host,
        "-p", str(profile.port),
        "-U", profile.user,
        "-d", database_name,
        "-t",
        "-c", "SELECT pg_size_pretty(pg_database_size(current_database()));"
    ]
    
    env = os.environ.copy()
    if profile.password:
        env["PGPASSWORD"] = profile.password
    env["PGSSLMODE"] = profile.ssl_mode
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        return result.stdout.strip() or "Unknown"
    except subprocess.CalledProcessError:
        return "Unknown"