"""Remove command coordinator.

Thin coordinator for removing installed AppImages.
"""

from argparse import Namespace

from my_unicorn.core.workflows.remove import RemoveService
from my_unicorn.logger import get_logger

from .base import BaseCommandHandler

logger = get_logger(__name__)


class RemoveHandler(BaseCommandHandler):
    """Thin coordinator for remove command."""

    async def execute(self, args: Namespace) -> None:
        """Execute the remove command."""
        service = RemoveService(self.config_manager, self.global_config)
        for app_name in args.apps:
            result = await service.remove_app(app_name, args.keep_config)
            self._display_result(result, app_name)

    def _display_result(self, result: dict, app_name: str) -> None:
        """Display removal operation results."""
        if not result or not result.get("success"):
            logger.info(
                "❌ %s", result.get("error", f"Failed to remove {app_name}")
            )
            return

        # Log removed files
        if files := result.get("removed_files"):
            logger.info("✅ Removed AppImage(s): %s", ", ".join(files))

        # Log cache clearance
        if result.get("cache_cleared"):
            app_cfg = self.config_manager.load_app_config(app_name)
            if (
                app_cfg
                and (owner := app_cfg.get("owner"))
                and (repo := app_cfg.get("repo"))
            ):
                logger.info("✅ Removed cache for %s/%s", owner, repo)

        # Log backup removal
        if backup_path := result.get("backup_path"):
            if result.get("backup_removed"):
                logger.info(
                    "✅ Removed all backups and metadata for %s", app_name
                )
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
