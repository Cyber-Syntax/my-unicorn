"""Remove command coordinator.

Thin coordinator for removing installed AppImages via ServiceContainer
for dependency injection.
"""

from argparse import Namespace

from my_unicorn.cli.container import ServiceContainer
from my_unicorn.logger import get_logger

from .base import BaseCommandHandler
from .helpers import parse_targets

logger = get_logger(__name__)


class RemoveHandler(BaseCommandHandler):
    """Thin coordinator for remove command."""

    async def execute(self, args: Namespace) -> None:
        """Execute the remove command using ServiceContainer for DI."""
        container = ServiceContainer(
            config_manager=self.config_manager,
        )

        try:
            service = container.create_remove_service()
            targets = parse_targets(args.apps)

            for app_name in targets:
                result = await service.remove_app(app_name, args.keep_config)
                if not result.success:
                    error_msg = result.error or "Unknown error"
                    if "not found" not in error_msg.lower():
                        raise RuntimeError(error_msg)
        finally:
            await container.cleanup()
