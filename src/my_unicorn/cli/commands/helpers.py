"""Shared helper functions for CLI command handlers.

This module provides small, reusable functions for common parsing and setup
tasks across command handlers. Functions here should be used by 2+ handlers
to avoid over-engineering (YAGNI principle).
"""

from pathlib import Path

from my_unicorn.config import ConfigManager
from my_unicorn.types import GlobalConfig


def parse_targets(targets: list[str] | None) -> list[str]:
    """Parse and expand comma-separated target strings into a flat list.

    Args:
        targets: List of target strings that may contain comma-separated
            values, or None

    Returns:
        Flattened list of unique targets with duplicates removed.
        Returns empty list if targets is None.

    Examples:
        >>> parse_targets(["app1", "app2,app3", "app1"])
        ['app1', 'app2', 'app3']
        >>> parse_targets(None)
        []
        >>> parse_targets([])
        []

    """
    if not targets:
        return []

    all_targets = []
    for target in targets:
        if not target or not target.strip():
            continue
        if "," in target:
            all_targets.extend(
                [t.strip() for t in target.split(",") if t.strip()]
            )
        else:
            all_targets.append(target.strip())

    # Remove duplicates while preserving order
    seen = set()
    unique_targets = []
    for target in all_targets:
        target_lower = target.lower()
        if target_lower not in seen:
            seen.add(target_lower)
            unique_targets.append(target)

    return unique_targets


def get_install_paths(global_config: GlobalConfig) -> tuple[Path, Path]:
    """Extract installation paths from global configuration.

    Args:
        global_config: Global configuration

    Returns:
        Tuple of (install_dir, download_dir) as Path objects

    Raises:
        KeyError: If required configuration keys are missing

    """
    install_dir = Path(global_config["directory"]["storage"])
    download_dir = Path(
        global_config["directory"].get("download", install_dir)
    )
    return install_dir, download_dir


def ensure_app_directories(
    config_manager: ConfigManager, global_config: GlobalConfig
) -> None:
    """Ensure required application directories exist.

    This is a thin wrapper around ConfigManager.ensure_directories_from_config
    for clarity and consistency across command handlers.

    Args:
        config_manager: Configuration manager instance
        global_config: Global configuration

    """
    config_manager.ensure_directories_from_config(global_config)
