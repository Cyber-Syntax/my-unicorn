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
        # Use command line branch option or fall back to configured preference
        branch_type = getattr(args, "branch", None)
        if branch_type is None:
            # Use configured preference as default
            branch_type = self.global_config["self_update"]["preferred_branch"]

        if args.check_only:
            await self._check_for_self_updates(branch_type)
        else:
            await self._perform_self_update(branch_type)

    async def _check_for_self_updates(self, branch_type: str = "stable") -> None:
        """Check for available self-updates without installing them."""
        branch_desc = "stable" if branch_type == "stable" else "development"
        print(f"🔍 Checking for my-unicorn updates on {branch_desc} branch...")

        try:
            has_update = await check_for_self_update(branch_type)

            if has_update:
                print("\nRun 'my-unicorn self-update' to install the update.")
            else:
                print("✅ my-unicorn is up to date")

        except Exception as e:
            logger.error("Failed to check for self-updates: %s", e)
            print(f"❌ Failed to check for updates: {e}")

    async def _perform_self_update(self, branch_type: str = "stable") -> None:
        """Perform self-update if available."""
        branch_desc = "stable" if branch_type == "stable" else "development"
        print(f"🔍 Checking for my-unicorn updates on {branch_desc} branch...")

        try:
            has_update = await check_for_self_update(branch_type)

            if not has_update:
                print("✅ my-unicorn is already up to date")
                return

            print("\n🚀 Starting self-update...")
            success = await perform_self_update(branch_type)

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
