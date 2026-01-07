"""Upgrade command coordinator.

Thin coordinator for upgrading my-unicorn itself.
"""

from argparse import Namespace

from my_unicorn.logger import get_logger, temporary_console_level
from my_unicorn.workflows.upgrade import (
    check_for_self_update,
    perform_self_update,
)

from .base import BaseCommandHandler

logger = get_logger(__name__)


class UpgradeHandler(BaseCommandHandler):
    """Thin coordinator for upgrade command."""

    async def execute(self, args: Namespace) -> None:
        """Execute the upgrade command."""
        refresh = getattr(args, "refresh_cache", False)

        if getattr(args, "check_only", False):
            await self._check_for_upgrades(refresh)
        else:
            await self._perform_upgrade(refresh)

    async def _check_for_upgrades(self, refresh: bool = False) -> None:
        """Check for available upgrades."""
        with temporary_console_level("INFO"):
            logger.info("🔍 Checking for my-unicorn upgrade...")

            try:
                if await check_for_self_update(refresh):
                    logger.info("")
                    logger.info(
                        "Run 'my-unicorn upgrade' to install the upgrade."
                    )
                else:
                    logger.info("✅ my-unicorn is up to date")
            except Exception as e:
                logger.exception("Failed to check for upgrades")
                logger.info("❌ Failed to check for updates: %s", e)

    async def _perform_upgrade(self, refresh: bool = False) -> None:
        """Perform upgrade if available."""
        with temporary_console_level("INFO"):
            logger.info("🔍 Checking for my-unicorn upgrade...")

            try:
                if not await check_for_self_update(refresh):
                    logger.info("✅ my-unicorn is already up to date")
                    return

                logger.info("")
                logger.info("🚀 Starting upgrade...")
                if await perform_self_update(refresh):
                    logger.info("✅ Upgrade completed successfully!")
                    logger.info(
                        "Please restart your terminal to refresh "
                        "the command cache."
                    )
                else:
                    logger.info(
                        "❌ Upgrade failed. Please try again or "
                        "update manually."
                    )
            except Exception as e:
                logger.exception("Upgrade failed")
                logger.info("❌ Upgrade failed: %s", e)
