"""Remove command coordinator.

Thin coordinator for removing installed AppImages.
"""

from argparse import Namespace

from my_unicorn.core.remove import RemoveService
from my_unicorn.ui.display_remove import display_removal_result

from .base import BaseCommandHandler
from .helpers import parse_targets


class RemoveHandler(BaseCommandHandler):
    """Thin coordinator for remove command."""

    async def execute(self, args: Namespace) -> None:
        """Execute the remove command."""
        service = RemoveService(self.config_manager, self.global_config)
        targets = parse_targets(args.apps)

        for app_name in targets:
            result = await service.remove_app(app_name, args.keep_config)
            display_removal_result(result, app_name, self.config_manager)
