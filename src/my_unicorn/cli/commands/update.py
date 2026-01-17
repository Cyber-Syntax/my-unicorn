"""Update command coordinator.

Thin coordinator that validates input and delegates to
UpdateApplicationService.
"""

from argparse import Namespace

from my_unicorn.core.workflows.services.update_service import (
    UpdateApplicationService,
)
from my_unicorn.core.workflows.update import UpdateManager
from my_unicorn.logger import get_logger
from my_unicorn.ui.display_update import (
    display_check_results,
    display_invalid_apps,
    display_update_error,
    display_update_results,
)
from my_unicorn.ui.progress import progress_session

from .base import BaseCommandHandler
from .helpers import parse_targets

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

                app_names = parse_targets(args.apps) if args.apps else None
                refresh = getattr(args, "refresh_cache", False)

                if getattr(args, "check_only", False):
                    results = await service.check_for_updates(
                        app_names=app_names, refresh_cache=refresh
                    )
                else:
                    results = await service.perform_updates(
                        app_names=app_names, refresh_cache=refresh, force=False
                    )

            # Display results after progress session ends
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
