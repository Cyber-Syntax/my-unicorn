"""Update command coordinator.

Thin coordinator that validates input and delegates to
UpdateApplicationService via ServiceContainer for dependency injection.
"""

from argparse import Namespace

from my_unicorn.cli.container import ServiceContainer
from my_unicorn.core.progress.progress import ProgressDisplay
from my_unicorn.logger import get_logger
from my_unicorn.ui.display_update import (
    display_check_results,
    display_invalid_apps,
    display_update_error,
    display_update_results,
)

from .base import BaseCommandHandler
from .helpers import parse_targets

logger = get_logger(__name__)


class UpdateHandler(BaseCommandHandler):
    """Thin coordinator for update command."""

    async def execute(self, args: Namespace) -> None:
        """Execute update command using ServiceContainer for DI."""
        try:
            progress_display = ProgressDisplay()

            container = ServiceContainer(
                config_manager=self.config_manager,
                progress_reporter=progress_display,
            )

            try:
                # Estimate operations: check mode uses API fetching,
                # update mode uses download/verify/icon/install per app
                # Use a reasonable default; actual count may vary
                total_operations = 10

                async with progress_display.session(total_operations):
                    service = container.create_update_application_service()

                    app_names = parse_targets(args.apps) if args.apps else None
                    refresh = getattr(args, "refresh_cache", False)

                    if getattr(args, "check_only", False):
                        results = await service.check_for_updates(
                            app_names=app_names, refresh_cache=refresh
                        )
                    else:
                        results = await service.perform_updates(
                            app_names=app_names,
                            refresh_cache=refresh,
                            force=False,
                        )
            finally:
                await container.cleanup()

            # Display results after cleanup
            if getattr(args, "check_only", False):
                display_check_results(results)
            else:
                display_update_results(results)

            display_invalid_apps(
                results.get("invalid_apps", []), self.config_manager
            )
        except Exception as e:
            display_update_error(f"Update operation failed: {e}")
            logger.exception("Update operation failed")
