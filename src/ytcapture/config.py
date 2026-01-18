"""Configuration file handling for ytcapture/vidcapture."""

from pathlib import Path
from typing import Any

import yaml


# Default configuration values
DEFAULT_CONFIG: dict[str, Any] = {
    "vault": ".",
    "output": None,
    "interval": 15,
    "max_frames": None,
    "frame_format": "jpg",
    "dedup_threshold": 0.85,
    # ytcapture-specific
    "language": "en",
    "prefer_manual": False,
    "keep_video": False,
    # vidcapture-specific
    "fast": False,
}

# Default config file content
DEFAULT_CONFIG_YAML = """\
# ytcapture/vidcapture configuration
# Location: ~/.ytcapture.yml
#
# Settings can be removed or commented out to use built-in defaults.
# Built-in defaults are noted in [brackets] for each setting.

# Vault root directory for output (~ expanded)
# Relative paths in --output are relative to this
vault: .  # [.]

# Default output directory (vault-relative if not absolute)
# If set, used when --output is not specified on command line
# output: Inbox/VideoCaptures  # [none - uses vault root]

# Frame extraction defaults
interval: 15           # Seconds between frames [15]
# max_frames:          # Maximum frames to extract [none - no limit]
frame_format: jpg      # jpg or png [jpg]
dedup_threshold: 0.85  # 0.0-1.0, higher = more aggressive dedup [0.85]

# ytcapture-specific defaults (YouTube video processing)
language: en           # Transcript language code [en]
prefer_manual: false   # Only use manual transcripts [false]
keep_video: false      # Keep downloaded video file [false]

# vidcapture-specific defaults (local video processing)
fast: false            # Use fast keyframe seeking [false]
"""


def get_config_path() -> Path:
    """Return the default config file path (~/.ytcapture.yml)."""
    return Path.home() / ".ytcapture.yml"


def config_exists(path: Path | None = None) -> bool:
    """Check if config file exists."""
    config_path = path or get_config_path()
    return config_path.exists()


def init_config(path: Path | None = None) -> Path:
    """Initialize default config file. Returns the path to the created file."""
    config_path = path or get_config_path()
    if config_path.exists():
        raise FileExistsError(f"Config file already exists: {config_path}")
    config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
    return config_path


def load_config(path: Path | None = None) -> tuple[dict[str, Any], bool]:
    """Load configuration from file, auto-creating if missing.

    Args:
        path: Optional path to config file. Uses ~/.ytcapture.yml if not specified.

    Returns:
        Tuple of (config dict, was_created flag). was_created is True if
        config file was auto-created on this call.
    """
    config_path = path or get_config_path()
    was_created = False

    # Start with defaults
    config = DEFAULT_CONFIG.copy()

    if not config_path.exists():
        # Auto-create config file
        config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
        was_created = True

    try:
        with open(config_path, encoding="utf-8") as f:
            file_config = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file {config_path}: {e}") from e

    # Merge file config into defaults
    config = _merge_dicts(config, file_config)

    # Expand vault path
    if "vault" in config and config["vault"]:
        config["vault"] = str(Path(config["vault"]).expanduser())

    return config, was_created


def merge_config(
    file_config: dict[str, Any], cli_overrides: dict[str, Any]
) -> dict[str, Any]:
    """Merge CLI overrides into file configuration.

    CLI overrides take precedence over file config.
    """
    return _merge_dicts(file_config, cli_overrides)


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries. Override values take precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def resolve_output_path(folder: str, vault: Path) -> Path:
    """Resolve output folder path relative to vault.

    Args:
        folder: Folder path (relative to vault or absolute)
        vault: Base vault path

    Returns:
        Resolved Path object (directory will be created if needed)
    """
    folder_path = Path(folder).expanduser()

    if folder_path.is_absolute():
        output_path = folder_path
    else:
        output_path = vault / folder_path

    # Create directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    return output_path


# Module-level cached config for CLI defaults
_cached_config: dict[str, Any] | None = None
_config_was_created: bool = False


def get_config_for_defaults() -> dict[str, Any]:
    """Load config once and cache for CLI option defaults.

    This function is designed to be called at module import time
    in cli.py to provide defaults for Click options. It silently
    creates the config file if missing, without printing messages.

    Returns:
        Config dict with all settings (file values merged over defaults).
    """
    global _cached_config, _config_was_created

    if _cached_config is None:
        config_path = get_config_path()

        # Start with defaults
        _cached_config = DEFAULT_CONFIG.copy()

        if not config_path.exists():
            # Auto-create config file silently
            config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
            _config_was_created = True
        else:
            try:
                with open(config_path, encoding="utf-8") as f:
                    file_config = yaml.safe_load(f) or {}
                _cached_config = _merge_dicts(_cached_config, file_config)
            except (yaml.YAMLError, OSError):
                # On error, just use defaults
                pass

        # Expand vault path
        if _cached_config.get("vault"):
            _cached_config["vault"] = str(Path(_cached_config["vault"]).expanduser())

    return _cached_config


def config_was_auto_created() -> bool:
    """Return True if config file was auto-created during this session.

    Call get_config_for_defaults() first to ensure config is loaded.
    """
    return _config_was_created


def clear_config_cache() -> None:
    """Clear the cached config (useful for testing)."""
    global _cached_config, _config_was_created
    _cached_config = None
    _config_was_created = False
