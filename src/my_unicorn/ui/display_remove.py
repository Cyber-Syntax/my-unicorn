"""Remove-specific display functions for CLI output.

This module provides display functions for removal operations,
keeping the presentation layer separate from command handlers.

Uses print() and logger directly for output to ensure messages
are visible regardless of progress display state.
"""

from my_unicorn.config import ConfigManager
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


def display_removal_result(
    result: dict,
    app_name: str,
    config_manager: ConfigManager,
) -> None:
    """Display results of a removal operation.

    Args:
        result: Result dictionary from RemoveService.remove_app()
        app_name: Name of the app being removed
        config_manager: ConfigManager instance for loading app config

    """
    if not result:
        logger.info("❌ Failed to remove %s", app_name)
        return

    if not result.get("success"):
        logger.info(
            "❌ %s", result.get("error", f"Failed to remove {app_name}")
        )
        return

    # Log removed files
    if files := result.get("removed_files"):
        logger.info("✅ Removed AppImage(s): %s", ", ".join(files))

    # Log cache clearance
    if result.get("cache_cleared"):
        app_cfg = config_manager.load_app_config(app_name)
        if (
            app_cfg
            and (owner := app_cfg.get("owner"))
            and (repo := app_cfg.get("repo"))
        ):
            logger.info("✅ Removed cache for %s/%s", owner, repo)

    # Log backup removal
    if backup_path := result.get("backup_path"):
        if result.get("backup_removed"):
            logger.info("✅ Removed all backups and metadata for %s", app_name)
        else:
            logger.info("⚠️  No backups found at: %s", backup_path)

    # Log desktop entry and icon
    if result.get("desktop_entry_removed"):
        logger.info("✅ Removed desktop entry for %s", app_name)

    if icon_path := result.get("icon_path"):
        if result.get("icon_removed"):
            logger.info("✅ Removed icon: %s", icon_path)
        else:
            logger.info("⚠️  Icon not found at: %s", icon_path)

    # Log config status
    logger.info(
        "✅ %s config for %s",
        "Removed" if result.get("config_removed") else "Kept",
        app_name,
    )
