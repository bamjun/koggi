import subprocess
from rich.console import Console
from rich.table import Table
from rich.prompt import IntPrompt, Confirm
from rich import box

from ..exceptions import KoggiError
from .config import RcConfig
from .restore import list_backups, check_rclone

console = Console()

def run_delete(config: RcConfig) -> None:
    """Interactive delete process."""
    console.print(f"\n[bold blue]Starting Rclone Delete[/bold blue]")
    
    backups = list_backups(config)
    
    if not backups:
        console.print("[yellow]No backups found on remote.[/yellow]")
        return
        
    table = Table(title=f"Available Backups in {config.project_name}", box=box.SIMPLE_HEAD)
    table.add_column("No.", justify="right", style="cyan")
    table.add_column("Timestamp", style="green")
    
    for i, b in enumerate(backups, 1):
        table.add_row(str(i), b)
        
    console.print(table)
    
    console.print("\n[bold]Options:[/bold]")
    console.print("  [cyan]1.[/cyan] Delete specific backup")
    console.print("  [cyan]2.[/cyan] Delete ALL backups")
    console.print("  [cyan]3.[/cyan] Keep recent N and delete the rest")
    console.print("  [cyan]0.[/cyan] Cancel")
    
    choice = IntPrompt.ask("Select an option", default=0, show_default=True)
    
    if choice == 0:
        console.print("[yellow]Delete cancelled.[/yellow]")
        return
        
    if choice == 1:
        _delete_specific(config, backups)
    elif choice == 2:
        _delete_all(config, backups)
    elif choice == 3:
        _delete_keep_n(config, backups)
    else:
        console.print("[red]Invalid option.[/red]")


def _delete_specific(config: RcConfig, backups: list[str]) -> None:
    choice = IntPrompt.ask(
        "Select backup number to delete (0 to cancel)", 
        default=0
    )
    
    if choice == 0:
        console.print("[yellow]Cancelled.[/yellow]")
        return
        
    if not (1 <= choice <= len(backups)):
        console.print("[red]Invalid selection![/red]")
        return
        
    selected = backups[choice - 1]
    
    if not Confirm.ask(f"\n[bold red]Delete backup '{selected}'?[/bold red] This cannot be undone."):
        console.print("[yellow]Cancelled.[/yellow]")
        return
        
    remote_path = f"{config.remote}:{config.project_name}/{selected}"
    _execute_purge(remote_path)


def _delete_all(config: RcConfig, backups: list[str]) -> None:
    if not Confirm.ask(
        f"\n[bold red]Warning: Delete ALL {len(backups)} backups in {config.project_name}?[/bold red]\n"
        "This cannot be undone.",
        default=False
    ):
        console.print("[yellow]Cancelled.[/yellow]")
        return
        
    # Simply purge the project directory on remote
    remote_path = f"{config.remote}:{config.project_name}"
    _execute_purge(remote_path)


def _delete_keep_n(config: RcConfig, backups: list[str]) -> None:
    keep_n = IntPrompt.ask(f"How many recent backups to keep? (Total currently: {len(backups)})", default=3)
    
    if keep_n >= len(backups):
        console.print(f"[yellow]Keeping {keep_n} backups means nothing will be deleted.[/yellow]")
        return
        
    to_delete = backups[keep_n:]
    console.print(f"\n[cyan]Keeping top {keep_n}:[/cyan] {', '.join(backups[:keep_n])}")
    console.print(f"[red]Will delete {len(to_delete)} backups:[/red] {', '.join(to_delete)}")
    
    if not Confirm.ask("\n[bold red]Proceed with deletion?[/bold red]"):
        console.print("[yellow]Cancelled.[/yellow]")
        return
        
    success = 0
    fail = 0
    for b in to_delete:
        remote_path = f"{config.remote}:{config.project_name}/{b}"
        try:
            console.print(f"Deleting {b}...")
            subprocess.run(
                ["rclone", "purge", remote_path],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            success += 1
        except subprocess.CalledProcessError:
            console.print(f"[red]Failed to delete {b}[/red]")
            fail += 1
            
    console.print(f"[green]Deleted {success} backups. ({fail} failed)[/green]")


def _execute_purge(remote_path: str) -> None:
    """Execute rclone purge."""
    try:
        console.print(f"Executing: rclone purge {remote_path}")
        subprocess.run(
            ["rclone", "purge", remote_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        console.print("[green]Delete completed successfully![/green]")
    except subprocess.CalledProcessError as e:
        raise KoggiError(f"Delete failed: {e.stderr.strip()}")
