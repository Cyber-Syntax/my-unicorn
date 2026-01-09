"""Update command coordinator.

Thin coordinator that validates input and delegates to
UpdateApplicationService.
"""

from argparse import Namespace

from my_unicorn.logger import get_logger
from my_unicorn.ui.display_update import display_update_error
from my_unicorn.ui.progress import progress_session
from my_unicorn.workflows.services.update_service import (
    UpdateApplicationService,
)
from my_unicorn.workflows.update import UpdateManager

from .base import BaseCommandHandler

logger = get_logger(__name__)


class UpdateHandler(BaseCommandHandler):
    """Thin coordinator for update command."""

    async def execute(self, args: Namespace) -> None:
        """Execute update command."""
        try:
            async with progress_session() as progress:
                # Create UpdateManager with progress service
                update_manager = UpdateManager(
                    config_manager=self.config_manager,
                    progress_service=progress,
                )

                service = UpdateApplicationService(
                    config_manager=self.config_manager,
                    update_manager=update_manager,
                    progress_service=progress,
                )

                app_names = self._parse_targets(args) if args.apps else None
                refresh = getattr(args, "refresh_cache", False)

                if getattr(args, "check_only", False):
                    results = await service.check_for_updates(
                        app_names=app_names, refresh_cache=refresh
                    )
                    self._display_check_results(results)
                else:
                    results = await service.perform_updates(
                        app_names=app_names, refresh_cache=refresh, force=False
                    )
                    self._display_update_results(results)

                self._log_invalid_apps(results.get("invalid_apps", []))
        except Exception as e:
            display_update_error(f"Update operation failed: {e}")
            logger.exception("Update operation failed")

    def _parse_targets(self, args: Namespace) -> list[str]:
        """Parse app names from arguments."""
        return (
            self._expand_comma_separated_targets(args.apps)
            if args.apps
            else []
        )

    def _parse_app_names(self, args: Namespace) -> list[str]:
        """Alias for _parse_targets for backward compatibility."""
        return self._parse_targets(args)

    def _display_check_results(self, results: dict) -> None:
        """Display check results."""
        if results["available_updates"]:
            logger.info("Updates available:")
            for info in results["available_updates"]:
                logger.info(
                    "  %s: %s → %s",
                    info["app_name"],
                    info["current_version"],
                    info["latest_version"],
                )
            logger.info("\nRun 'my-unicorn update' to install updates")
        else:
            logger.info("✅ All apps are up to date")

    def _display_update_results(self, results: dict) -> None:
        """Display update results."""
        if results["updated"]:
            logger.info(
                "✅ Successfully updated: %s", ", ".join(results["updated"])
            )
        if results["failed"]:
            logger.error(
                "❌ Failed to update: %s", ", ".join(results["failed"])
            )
        if results["up_to_date"]:
            logger.info(
                "Already up to date: %s", ", ".join(results["up_to_date"])
            )

    def _log_invalid_apps(self, invalid_apps: list[str]) -> None:
        """Log invalid app names."""
        if invalid_apps:
            logger.warning("⚠️  Apps not found: %s", ", ".join(invalid_apps))
            installed = self.config_manager.list_installed_apps()
            if installed:
                logger.info("   Installed apps: %s", ", ".join(installed))
