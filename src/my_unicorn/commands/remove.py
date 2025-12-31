"""Remove command handler for my-unicorn CLI.

This module handles the removal of installed AppImages, including cleanup of
associated files like desktop entries, icons, and configuration data.
"""

from argparse import Namespace

from my_unicorn.logger import get_logger, temporary_console_level
from my_unicorn.remove_service import RemoveService

from .base import BaseCommandHandler

logger = get_logger(__name__)


class RemoveHandler(BaseCommandHandler):
    """Handler for remove command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the remove command."""
        with temporary_console_level("INFO"):
            # Create a service receiver to handle removal operations
            service = RemoveService(self.config_manager, self.global_config)
            for app_name in args.apps:
                result = await service.remove_app(app_name, args.keep_config)
                self._display_result(result, app_name)

    def _display_result(self, result: dict, app_name: str) -> None:
        """Display removal operation results to the user."""
        if not result or not result.get("success", False):
            msg = result.get("error") or f"Failed to remove {app_name}"
            logger.info("❌ %s", msg)
            return

        self._log_files_removed(result)
        self._log_cache_cleared(result, app_name)
        self._log_backups_removed(result, app_name)
        self._log_desktop_entry_removed(result, app_name)
        self._log_icon_removed(result)
        self._log_config_status(result, app_name)

    def _log_files_removed(self, result: dict) -> None:
        """Log removed AppImage files."""
        removed_files = result.get("removed_files", [])
        if removed_files:
            files_str = ", ".join(removed_files)
            logger.info("✅ Removed AppImage(s): %s", files_str)

    def _log_cache_cleared(self, result: dict, app_name: str) -> None:
        """Log cache removal status."""
        if not result.get("cache_cleared"):
            return
        app_cfg = self.config_manager.load_app_config(app_name)
        owner = app_cfg.get("owner") if app_cfg else None
        repo = app_cfg.get("repo") if app_cfg else None
        if owner and repo:
            logger.info("✅ Removed cache for %s/%s", owner, repo)

    def _log_backups_removed(self, result: dict, app_name: str) -> None:
        """Log backup removal status."""
        backup_path = result.get("backup_path")
        if not backup_path:
            return
        if result.get("backup_removed"):
            logger.info("✅ Removed all backups and metadata for %s", app_name)
        else:
            logger.info("⚠️  No backups found at: %s", backup_path)

    def _log_desktop_entry_removed(self, result: dict, app_name: str) -> None:
        """Log desktop entry removal status."""
        if result.get("desktop_entry_removed"):
            logger.info("✅ Removed desktop entry for %s", app_name)

    def _log_icon_removed(self, result: dict) -> None:
        """Log icon removal status."""
        icon_path = result.get("icon_path")
        if not icon_path:
            return
        if result.get("icon_removed"):
            logger.info("✅ Removed icon: %s", icon_path)
        else:
            logger.info("⚠️  Icon not found at: %s", icon_path)

    def _log_config_status(self, result: dict, app_name: str) -> None:
        """Log config removal/retention status."""
        if result.get("config_removed"):
            logger.info("✅ Removed config for %s", app_name)
        else:
            logger.info("✅ Kept config for %s", app_name)
