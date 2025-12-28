"""Catalog command handler for my-unicorn CLI.

This module handles the catalog browsing functionality including listing
installed AppImages, showing available apps with descriptions, and displaying
detailed information about specific applications.
"""

from argparse import Namespace
from datetime import datetime
from typing import Any, cast

from my_unicorn.commands.base import BaseCommandHandler
from my_unicorn.logger import get_logger

logger = get_logger(__name__)

# Display constants
MAX_VERSION_DISPLAY_LENGTH = 16
DESCRIPTION_COLUMN_START = 26  # App name column width + spacing


class CatalogHandler(BaseCommandHandler):
    """Handler for catalog command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the catalog command."""
        # Handle --info argument (mutually exclusive)
        if hasattr(args, "info") and args.info:
            await self._show_app_info(args.info)
        # Handle --available argument
        elif hasattr(args, "available") and args.available:
            await self._list_available_apps()
        # Handle --installed argument or default
        elif hasattr(args, "installed") and args.installed:
            await self._list_installed_apps()
        else:
            # Default: show installed apps
            await self._list_installed_apps()

    async def _list_available_apps(self) -> None:
        """List available apps from catalog with descriptions."""
        apps = self.config_manager.list_catalog_apps()
        logger.info("Listing %d available apps from catalog", len(apps))
        print(f"📋 Available AppImages ({len(apps)} apps):\n")

        if not apps:
            print("  None found")
            return

        # Load catalog entries with descriptions
        app_info = []
        for app in sorted(apps):
            try:
                catalog_entry = self.config_manager.load_catalog_entry(app)
                if catalog_entry is None:
                    app_info.append((app, "Error loading catalog entry"))
                    continue
                # Cast to dict to access v2 fields
                entry_dict = cast("dict[str, Any]", catalog_entry)
                metadata = entry_dict.get("metadata", {})
                description = (
                    metadata.get("description", "")
                    or "No description available"
                )
                app_info.append((app, description))
            except (ValueError, KeyError) as e:
                logger.warning(
                    "Failed to load catalog entry for %s: %s", app, e
                )
                app_info.append((app, "Error loading catalog entry"))

        # Display apps with descriptions
        for app, description in app_info:
            print(f"  {app:<24} - {description}")

        print(
            "\n💡 Use 'my-unicorn catalog --info <app-name>' for detailed information"
        )

    async def _show_app_info(self, app_name: str) -> None:
        """Show detailed information about a specific app.

        Args:
            app_name: The name of the app to show information for.

        """
        try:
            catalog_entry = self.config_manager.load_catalog_entry(app_name)
            if catalog_entry is None:
                print(f"❌ App '{app_name}' not found in catalog")
                return
        except ValueError as e:
            print(f"❌ App '{app_name}' not found in catalog")
            logger.error(
                "Failed to load catalog entry for %s: %s", app_name, e
            )
            return

        # Check if app is installed
        installed_apps = self.config_manager.list_installed_apps()
        is_installed = app_name in installed_apps
        status = "Installed" if is_installed else "Not installed"

        # Extract catalog information - cast to dict for v2 access
        entry_dict = cast("dict[str, Any]", catalog_entry)
        metadata = entry_dict.get("metadata", {})
        source = entry_dict.get("source", {})
        verification = entry_dict.get("verification", {})
        icon = entry_dict.get("icon", {})

        display_name = metadata.get("display_name", app_name)
        description = metadata.get("description", "No description available")

        # Build repository information
        if source.get("type") == "github":
            repo_owner = source.get("owner", "")
            repo_name = source.get("repo", "")
            repo_url = f"https://github.com/{repo_owner}/{repo_name}"
            repo_display = f"{repo_owner}/{repo_name}"
        else:
            repo_url = "N/A"
            repo_display = "N/A"

        # Build verification information
        verify_method = verification.get("method", "None")
        if verify_method == "digest":
            verify_display = "SHA256 digest (embedded in GitHub release)"
        elif verify_method == "checksum_file":
            checksum_file_data = verification.get("checksum_file", {})
            if isinstance(checksum_file_data, dict):
                checksum_file = checksum_file_data.get("name", "Unknown")
                algorithm = str(
                    checksum_file_data.get("algorithm", "SHA256")
                ).upper()
            else:
                checksum_file = "Unknown"
                algorithm = "SHA256"
            verify_display = f"{algorithm} checksum ({checksum_file})"
        elif verify_method == "skip":
            verify_display = (
                "No verification (developer provides no checksums)"
            )
        else:
            verify_display = "None"

        # Build icon information
        icon_method = (
            icon.get("method", "None") if isinstance(icon, dict) else "None"
        )
        if icon_method == "extraction":
            icon_display = "Embedded (extracted from AppImage)"
        else:
            icon_display = "None"

        # Display information
        print(f"📦 {display_name}")
        print()
        print(f"  {description}")
        print()
        print(f"  Repository:     {repo_display}")
        if repo_url != "N/A":
            print(f"  URL:            {repo_url}")
        print(f"  Status:         {status}")
        print(f"  Verification:   {verify_display}")
        print(f"  Icon:           {icon_display}")
        print()

        if is_installed:
            print("  ✓ Already installed")
            print(f"  📝 Update: my-unicorn update {app_name}")
        else:
            print(f"  📥 Install: my-unicorn install {app_name}")

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
