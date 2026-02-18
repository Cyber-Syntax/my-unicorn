"""Helper functions for desktop entry management."""

from pathlib import Path
from typing import Any

from my_unicorn.config import ConfigManager
from my_unicorn.core.desktop_entry.entry import DesktopEntry


def create_desktop_entry_for_app(
    app_name: str,
    appimage_path: Path,
    icon_path: Path | None = None,
    comment: str = "",
    categories: list[str] | None = None,
    config_manager: ConfigManager | None = None,
    **kwargs: Any,
) -> Path:
    """Convenience function to create or update desktop entry for an app.

    This function automatically detects when desktop entries need updating
    by comparing the existing content with what would be generated. Updates
    only when there are actual changes to important fields like icon paths,
    exec paths, MIME types, etc.

    Args:
        app_name: Name of the application (will be normalized to lowercase)
        appimage_path: Path to the AppImage file (should use clean name without version)
        icon_path: Optional path to icon file
        comment: Application description
        categories: List of application categories
        config_manager: Configuration manager for directory paths
        **kwargs: Additional desktop entry options

    Returns:
        Path to desktop file (existing, newly created, or updated)

    """
    desktop_entry = DesktopEntry(
        app_name, appimage_path, icon_path, config_manager
    )
    return desktop_entry.create_desktop_file(
        comment=comment, categories=categories, **kwargs
    )


def remove_desktop_entry_for_app(
    app_name: str, config_manager: ConfigManager | None = None
) -> bool:
    """Convenience function to remove desktop entry for an app.

    Args:
        app_name: Name of the application
        config_manager: Configuration manager for directory paths

    Returns:
        True if desktop file was removed

    """
    # Create a dummy DesktopEntry to use the removal logic
    dummy_path = Path("/dev/null")
    desktop_entry = DesktopEntry(
        app_name, dummy_path, config_manager=config_manager
    )
    return desktop_entry.remove_desktop_file()
