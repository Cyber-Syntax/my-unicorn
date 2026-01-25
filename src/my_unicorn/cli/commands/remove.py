"""Remove command coordinator.

Thin coordinator for removing installed AppImages.
"""

from argparse import Namespace

from my_unicorn.core.remove import RemoveService
from my_unicorn.logger import get_logger

from .base import BaseCommandHandler
from .helpers import parse_targets

logger = get_logger(__name__)


class RemoveHandler(BaseCommandHandler):
    """Thin coordinator for remove command."""

    async def execute(self, args: Namespace) -> None:
        """Execute the remove command."""
        service = RemoveService(self.config_manager, self.global_config)
        targets = parse_targets(args.apps)

        for app_name in targets:
            result = await service.remove_app(app_name, args.keep_config)
            if not result.success:
                error_msg = result.error or "Unknown error"
                if "not found" in error_msg.lower():
                    logger.error("❌ %s", error_msg)
                else:
                    raise RuntimeError(error_msg)
