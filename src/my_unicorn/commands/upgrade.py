"""Upgrade command handler for my-unicorn CLI.

This module provides the CLI handler for the `upgrade` command,
which checks for and performs upgrades of the my-unicorn tool.
"""

from argparse import Namespace

from ..logger import get_logger
from ..upgrade import check_for_self_update, perform_self_update
from .base import BaseCommandHandler

logger = get_logger(__name__)


class UpgradeHandler(BaseCommandHandler):
    """Handler for upgrade command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the upgrade command.

        Args:
            args: Parsed command-line arguments

        """
        refresh_cache = getattr(args, "refresh_cache", False)

        if getattr(args, "check_only", False):
            await self._check_for_upgrades(refresh_cache)
        else:
            await self._perform_upgrade(refresh_cache)

    async def _check_for_upgrades(self, refresh_cache: bool = False) -> None:
        """Check for available upgrades without installing them.

        Args:
            refresh_cache: Whether to bypass cache and fetch fresh data

        """
        print("🔍 Checking for my-unicorn upgrade...")

        try:
            has_update = await check_for_self_update(refresh_cache)

            if has_update:
                print("\nRun 'my-unicorn upgrade' to install the upgrade.")
            else:
                print("✅ my-unicorn is up to date")

        except Exception as e:
            logger.error("Failed to check for upgrades: %s", e, exc_info=True)
            print(f"❌ Failed to check for updates: {e}")

    async def _perform_upgrade(self, refresh_cache: bool = False) -> None:
        """Perform upgrade if available.

        Args:
            refresh_cache: Whether to bypass cache and fetch fresh data

        """
        print("🔍 Checking for my-unicorn upgrade...")

        try:
            has_update = await check_for_self_update(refresh_cache)

            if not has_update:
                print("✅ my-unicorn is already up to date")
                return

            print("\n🚀 Starting upgrade...")
            success = await perform_self_update(refresh_cache)

            if success:
                print("✅ Upgrade completed successfully!")
                print(
                    "Please restart your terminal refresh the command cache."
                )
            else:
                print(
                    "❌ Upgrade failed. Please try again or update manually."
                )

        except Exception as e:
            logger.error("Upgrade failed: %s", e, exc_info=True)
            print(f"❌ Upgrade failed: {e}")
