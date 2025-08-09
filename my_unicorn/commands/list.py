"""List command handler for my-unicorn CLI.

This module handles the listing of installed AppImages and available catalog apps,
providing comprehensive information about versions and installation dates.
"""

from argparse import Namespace
from datetime import datetime

from ..logger import get_logger
from .base import BaseCommandHandler

logger = get_logger(__name__)


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
        print("📋 Available AppImages:")

        if not apps:
            print("  None found")
            return

        for app in sorted(apps):
            print(f"  {app}")

    async def _list_installed_apps(self) -> None:
        """List installed apps with version and date information."""
        apps = self.config_manager.list_installed_apps()
        print("📦 Installed AppImages:")

        if not apps:
            print("  None found")
            return

        for app in sorted(apps):
            config = self.config_manager.load_app_config(app)
            if config:
                version = config["appimage"]["version"]
                installed_date = config["appimage"].get("installed_date", "Unknown")

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
                print(f"  {app:<20} {formatted_version:<16} ({installed_date})")
            else:
                print(f"  {app:<20} (config error)")

    def _format_version_display(self, version: str) -> str:
        """Format version information for display."""
        # Truncate long version strings for better display
        if len(version) > 16:
            return version[:13] + "..."
        return version
