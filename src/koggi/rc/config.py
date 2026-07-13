import json
from pathlib import Path
from pydantic import BaseModel, Field

from ..exceptions import KoggiError


class RcConfig(BaseModel):
    """Configuration for rclone backup."""
    project_name: str = Field(description="Remote project name for path separation")
    remote: str = Field(description="Rclone remote name")
    files: list[str] = Field(description="List of paths or glob patterns to backup")
    exclude: list[str] = Field(default=[], description="List of glob patterns to exclude from backup")


def get_rc_config_path() -> Path:
    """Returns the default setting.json path in current directory."""
    return Path.cwd() / ".koggi" / "rclone" / "setting.json"


def load_rc_config() -> RcConfig:
    """Load configuration from setting.json."""
    config_path = get_rc_config_path()
    if not config_path.exists():
        raise KoggiError(
            f"Config not found at {config_path}\n"
            "Run 'koggi rc init' first."
        )
    
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return RcConfig(**data)
    except Exception as e:
        raise KoggiError(f"Failed to load rclone config: {e}")


def save_rc_config(config: RcConfig) -> None:
    """Save configuration to setting.json."""
    config_path = get_rc_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    config_json = config.model_dump_json(indent=2)
    config_path.write_text(config_json, encoding="utf-8")


def find_rc_config() -> Path:
    """
    Ensure the .koggi/rclone/setting.json exists in the *current* directory.
    If not, raises KoggiError.
    """
    config_path = get_rc_config_path()
    if not config_path.exists():
        raise KoggiError(
            "[red]Error:[/red] .koggi/rclone/setting.json not found in current directory.\n"
            "   Run [green]'koggi rc init'[/green] first to create the configuration."
        )
    return config_path
