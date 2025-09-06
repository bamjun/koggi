"""
Interactive backup file selector with pagination.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

console = Console()


def get_backup_files(backup_dir: Path) -> List[Tuple[Path, datetime, int]]:
    """Get list of backup files with metadata (path, modified_time, size)."""
    if not backup_dir.exists():
        return []
    
    backup_files = []
    for file_path in backup_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in {".sql", ".backup", ".dump"}:
            try:
                stat = file_path.stat()
                modified_time = datetime.fromtimestamp(stat.st_mtime)
                size = stat.st_size
                backup_files.append((file_path, modified_time, size))
            except (OSError, ValueError):
                continue
    
    # Sort by modification time (newest first)
    backup_files.sort(key=lambda x: x[1], reverse=True)
    return backup_files


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def format_time_ago(file_time: datetime) -> str:
    """Format how long ago the file was created."""
    now = datetime.now()
    diff = now - file_time
    
    if diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours}h ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes}m ago"
    else:
        return "just now"


def display_backup_page(
    backup_files: List[Tuple[Path, datetime, int]], 
    page: int, 
    page_size: int
) -> None:
    """Display a page of backup files."""
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(backup_files))
    page_files = backup_files[start_idx:end_idx]
    
    total_pages = (len(backup_files) + page_size - 1) // page_size
    
    console.clear()
    console.print(f"\n[bold blue]📦 Available Backup Files[/bold blue]")
    console.print(f"[dim]Page {page + 1} of {total_pages} • Total: {len(backup_files)} files[/dim]\n")
    
    if not page_files:
        console.print("[yellow]No backup files found[/yellow]")
        return
    
    table = Table(box=box.SIMPLE_HEAD)
    table.add_column("#", style="cyan", width=3)
    table.add_column("File Name", style="green")
    table.add_column("Size", style="magenta", justify="right")
    table.add_column("Modified", style="blue")
    table.add_column("Age", style="dim", justify="right")
    
    for i, (file_path, modified_time, size) in enumerate(page_files):
        idx = start_idx + i + 1
        name = file_path.name
        size_str = format_file_size(size)
        time_str = modified_time.strftime("%Y-%m-%d %H:%M")
        age_str = format_time_ago(modified_time)
        
        table.add_row(
            str(idx),
            name,
            size_str,
            time_str,
            age_str
        )
    
    console.print(table)
    console.print()


def get_single_keypress() -> str:
    """Get a single keypress without requiring Enter."""
    if os.name == 'nt':  # Windows
        import msvcrt
        return msvcrt.getch().decode('utf-8').lower()
    else:  # Unix/Linux/macOS
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            char = sys.stdin.read(1).lower()
            return char
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def show_help() -> None:
    """Show help instructions."""
    console.print("\n[bold]📋 Navigation Help:[/bold]")
    console.print("• [green]1-9[/green] - Select backup file by number")
    console.print("• [blue]n[/blue] - Next page")
    console.print("• [blue]p[/blue] - Previous page")  
    console.print("• [yellow]h[/yellow] - Show this help")
    console.print("• [red]q[/red] - Quit without selecting")
    console.print("\nPress any key to continue...")
    get_single_keypress()


def interactive_backup_selector(backup_dir: Path, page_size: int = 10) -> Optional[Path]:
    """
    Interactive backup file selector with pagination.
    
    Returns selected file path or None if cancelled.
    """
    backup_files = get_backup_files(backup_dir)
    
    if not backup_files:
        console.print(f"[yellow]No backup files found in {backup_dir}[/yellow]")
        return None
    
    current_page = 0
    total_pages = (len(backup_files) + page_size - 1) // page_size
    
    while True:
        display_backup_page(backup_files, current_page, page_size)
        
        # Show navigation instructions
        console.print("[dim]Navigation: [blue]n[/blue]ext • [blue]p[/blue]rev • [yellow]h[/yellow]elp • [red]q[/red]uit • [green]1-9[/green] select[/dim]")
        console.print("Select backup file: ", end="", style="bold")
        
        try:
            key = get_single_keypress()
            
            if key == 'q':
                console.print("q")
                console.print("[yellow]Cancelled[/yellow]")
                return None
            
            elif key == 'n':
                console.print("n")
                if current_page < total_pages - 1:
                    current_page += 1
                else:
                    console.print("[yellow]Already on last page[/yellow]")
                    console.print("Press any key to continue...")
                    get_single_keypress()
            
            elif key == 'p':
                console.print("p")
                if current_page > 0:
                    current_page -= 1
                else:
                    console.print("[yellow]Already on first page[/yellow]")
                    console.print("Press any key to continue...")
                    get_single_keypress()
            
            elif key == 'h':
                console.print("h")
                show_help()
            
            elif key.isdigit():
                console.print(key)
                choice = int(key)
                start_idx = current_page * page_size
                
                if 1 <= choice <= min(page_size, len(backup_files) - start_idx):
                    selected_idx = start_idx + choice - 1
                    selected_file = backup_files[selected_idx][0]
                    
                    console.print(f"\n[green]✅ Selected:[/green] {selected_file.name}")
                    return selected_file
                else:
                    console.print(f"[red]Invalid selection. Choose 1-{min(page_size, len(backup_files) - start_idx)}[/red]")
                    console.print("Press any key to continue...")
                    get_single_keypress()
            
            else:
                console.print(key)
                console.print("[yellow]Invalid key. Press 'h' for help.[/yellow]")
                console.print("Press any key to continue...")
                get_single_keypress()
                
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled[/yellow]")
            return None
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            console.print("Press any key to continue...")
            get_single_keypress()


def quick_latest_selector(backup_dir: Path) -> Optional[Path]:
    """Quick selector that returns the latest backup file."""
    backup_files = get_backup_files(backup_dir)
    
    if not backup_files:
        return None
    
    # Return the most recent file (first in sorted list)
    return backup_files[0][0]