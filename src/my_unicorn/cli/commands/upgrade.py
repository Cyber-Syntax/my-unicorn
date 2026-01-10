"""Upgrade command coordinator.

Thin coordinator for upgrading my-unicorn itself via the uv package manager.

The upgrade command has two modes:
- Default: Perform the upgrade using uv tool install --upgrade
- --check: Check for available updates without performing the upgrade

Both modes always query GitHub API for the latest version (cache disabled)
to ensure accurate version information.
"""

from argparse import Namespace

from my_unicorn import __version__
from my_unicorn.cli.upgrade import (
    perform_self_update,
    should_perform_self_update,
)
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


class UpgradeHandler:
    """Thin coordinator for upgrade command."""

    async def execute(self, args: Namespace) -> None:
        """Execute the upgrade command."""
        if args.check:
            await self._check_version()
        else:
            await self._perform_upgrade()

    async def _check_version(self) -> None:
        """Check and display current and latest versions.

        Always queries GitHub API for fresh version data (no caching).
        This ensures users see accurate information about available updates.
        Detects development installations and recommends upgrade to production.
        """
        logger.info("🔍 Checking for my-unicorn updates...")

        try:
            should_upgrade, latest_version = await should_perform_self_update(
                __version__
            )

            if latest_version:
                logger.info(
                    "Current: %s, Latest: %s",
                    __version__,
                    latest_version,
                )
                if should_upgrade:
                    logger.info("✅ A newer version is available!")
                else:
                    logger.info("✨ You are running the latest version.")
            else:
                logger.warning(
                    "Could not determine the latest version. Current: %s",
                    __version__,
                )
        except Exception as e:
            logger.exception("Version check failed")
            logger.info("❌ Version check failed: %s", e)

    async def _perform_upgrade(self) -> None:
        """Perform upgrade to the latest version.

        Uses uv tool install --upgrade to update from the official GitHub
        repository. Detects development installations and always upgrades them
        to production (git-based). If already on the latest production version,
        displays a message and returns without performing an upgrade.
        """
        logger.info("🚀 Starting my-unicorn upgrade...")

        try:
            should_upgrade, latest_version = await should_perform_self_update(
                __version__
            )

            if not should_upgrade:
                logger.info(
                    "✨ You are already running the latest my-unicorn (%s).",
                    latest_version or __version__,
                )
                return

            if latest_version:
                logger.info(
                    "Updating my-unicorn from %s to %s",
                    __version__,
                    latest_version,
                )

            if perform_self_update():
                logger.info("✅ Upgrade completed successfully!")
                logger.info(
                    "Please restart your terminal to refresh "
                    "the command cache."
                )
            else:
                logger.info(
                    "❌ Upgrade failed. Please try again or update manually."
                )
        except Exception as e:
            logger.exception("Upgrade failed")
            logger.info("❌ Upgrade failed: %s", e)
