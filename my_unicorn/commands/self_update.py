"""Self-update command handler for my-unicorn CLI.

This module handles the self-updating functionality of the my-unicorn package,
allowing users to check for and install updates to the tool itself.
"""

from argparse import Namespace

from ..logger import get_logger
from ..repo import check_for_self_update, perform_self_update
from .base import BaseCommandHandler

logger = get_logger(__name__)


class SelfUpdateHandler(BaseCommandHandler):
    """Handler for self-update command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the self-update command.

        Args:
            args: Parsed command-line arguments

        """
        if args.check_only:
            await self._check_for_self_updates()
        else:
            await self._perform_self_update()

    async def _check_for_self_updates(self) -> None:
        """Check for available self-updates without installing them."""
        print("🔍 Checking for my-unicorn updates...")

        try:
            has_update = await check_for_self_update()

            if has_update:
                print("\nRun 'my-unicorn self-update' to install the update.")
            else:
                print("✅ my-unicorn is up to date")

        except Exception as e:
            logger.error("Failed to check for self-updates: %s", e)
            print(f"❌ Failed to check for updates: {e}")

    async def _perform_self_update(self) -> None:
        """Perform self-update if available."""
        print("🔍 Checking for my-unicorn updates...")

        try:
            has_update = await check_for_self_update()

            if not has_update:
                print("✅ my-unicorn is already up to date")
                return

            print("\n🚀 Starting self-update...")
            success = await perform_self_update()

            if success:
                print("✅ Self-update completed successfully!")
                print(
                    "Please restart your terminal or run 'hash -r' to refresh the command cache."
                )
            else:
                print("❌ Self-update failed. Please try again or update manually.")

        except Exception as e:
            logger.error("Self-update failed: %s", e)
            print(f"❌ Self-update failed: {e}")
