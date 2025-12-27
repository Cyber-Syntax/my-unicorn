"""List command handler for my-unicorn CLI.

This module handles the listing of installed AppImages and available
catalog apps, providing comprehensive information about versions and
installation dates.
"""

from argparse import Namespace
from datetime import datetime

from my_unicorn.commands.base import BaseCommandHandler
from my_unicorn.logger import get_logger

logger = get_logger(__name__)

# Display constants
MAX_VERSION_DISPLAY_LENGTH = 16


class ListHandler(BaseCommandHandler):
    """Handler for list command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the list command."""
        if args.available:
            await self._list_available_apps()
        else:
            await self._list_installed_apps()

    async def _list_available_apps(self) -> None:
        """List available apps from catalog."""
        apps = self.config_manager.list_catalog_apps()
        logger.info("Listing %d available apps from catalog", len(apps))
        print("📋 Available AppImages:")

        if not apps:
            print("  None found")
            return

        for app in sorted(apps):
            print(f"  {app}")

    async def _list_installed_apps(self) -> None:
        """List installed apps with version and date information."""
        apps = self.config_manager.list_installed_apps()
        logger.info("Listing %d installed apps", len(apps))
        print("📦 Installed AppImages:")

        if not apps:
            print("  None found")
            return

        for app in sorted(apps):
            try:
                config = self.config_manager.load_app_config(app)
            except ValueError as e:
                if "migrate" not in str(e).lower():
                    raise
                logger.info(
                    "Detected v1 config for app '%s', prompting migration", app
                )
                print(f"  {app:<20} (v1 config: run 'my-unicorn migrate')")
                continue
            if config:
                if "state" in config:
                    # v2 format
                    version = config["state"]["version"]  # type: ignore[typeddict-item]
                    installed_date = config["state"].get(  # type: ignore[typeddict-item]
                        "installed_date", "Unknown"
                    )
                else:
                    # v1 format detected, prompt migration
                    print(f"  {app:<20} (v1 config: run 'my-unicorn migrate')")
                    continue

                # Format installation date
                if installed_date != "Unknown":
                    try:
                        date_obj = datetime.fromisoformat(
                            installed_date.replace("Z", "+00:00")
                        )
                        installed_date = date_obj.strftime("%Y-%m-%d")
                    except ValueError:
                        pass

                formatted_version = self._format_version_display(version)
                print(
                    f"  {app:<20} {formatted_version:<16} ({installed_date})"
                )
            else:
                logger.warning("Config not found for app '%s'", app)
                print(f"  {app:<20} (config error)")

    def _format_version_display(self, version: str) -> str:
        """Format version information for display."""
        # Truncate long version strings for better display
        if len(version) > MAX_VERSION_DISPLAY_LENGTH:
            return version[:13] + "..."
        return version
