"""Catalog service for business logic related to catalog operations.

This service provides catalog-related functionality that can be reused across
different command handlers and UI components.
"""

from datetime import datetime
from typing import Any

from my_unicorn.config import ConfigManager
from my_unicorn.logger import get_logger

logger = get_logger(__name__)

MAX_VERSION_DISPLAY_LENGTH = 16


class CatalogService:
    """Service for catalog-related business logic."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize catalog service.

        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager

    def display_available_apps(self) -> None:
        """Display available catalog apps with descriptions."""
        app_info = self.list_available_with_descriptions()
        logger.info("Listing %d available apps from catalog", len(app_info))

        logger.info("📋 Available AppImages (%d apps):", len(app_info))
        logger.info("")

        if not app_info:
            logger.info("  None found")
            return

        for app, description in app_info:
            logger.info("  %-24s - %s", app, description)

        logger.info("")
        logger.info(
            "💡 Use 'my-unicorn catalog --info <app-name>' "
            "for detailed information"
        )

    def display_app_info(self, app_name: str) -> None:
        """Display detailed information for a specific app."""
        try:
            info = self.get_app_display_info(app_name)
        except (FileNotFoundError, ValueError):
            logger.info("❌ App '%s' not found in catalog", app_name)
            logger.exception("Failed to load catalog entry for %s", app_name)
            return

        is_installed = self.is_app_installed(app_name)
        status = "Installed" if is_installed else "Not installed"

        logger.info("📦 %s", info["display_name"])
        logger.info("")
        logger.info("  %s", info["description"])
        logger.info("")
        logger.info("  Repository:     %s", info["repo_display"])
        if info["repo_url"] != "N/A":
            logger.info("  URL:            %s", info["repo_url"])
        logger.info("  Status:         %s", status)
        logger.info("  Verification:   %s", info["verify_display"])
        logger.info("  Icon:           %s", info["icon_display"])
        logger.info("")

        if is_installed:
            logger.info("  ✓ Already installed")
            logger.info("  📝 Update: my-unicorn update %s", app_name)
        else:
            logger.info("  📥 Install: my-unicorn install %s", app_name)

    def display_installed_apps(self) -> None:
        """Display installed apps with version and date information."""
        app_details = self.list_installed_with_details()
        logger.info("Listing %d installed apps", len(app_details))

        logger.info("📦 Installed AppImages:")

        if not app_details:
            logger.info("  None found")
            return

        for details in app_details:
            app = details["app_name"]
            status = details["status"]

            if status == "migration_needed":
                logger.info(
                    "  %-20s (v1 config: run 'my-unicorn migrate')",
                    app,
                )
            elif status == "config_missing":
                logger.warning("Config not found for app '%s'", app)
                logger.info("  %-20s (config error)", app)
            elif status == "error":
                logger.warning("Failed to load config for app '%s'", app)
                logger.info("  %-20s (config error)", app)
            elif status == "OK":
                version = details["version"]
                installed_date = details["installed_date"]
                formatted_version = self.format_version_for_display(
                    version, MAX_VERSION_DISPLAY_LENGTH
                )
                logger.info(
                    "  %-20s %-16s (%s)",
                    app,
                    formatted_version,
                    installed_date,
                )

    def is_app_installed(self, app_name: str) -> bool:
        """Check if an app is installed.

        Args:
            app_name: Name of the application

        Returns:
            True if app is installed, False otherwise
        """
        installed_apps = self.config_manager.list_installed_apps()
        return app_name in installed_apps

    def get_app_display_info(self, app_name: str) -> dict[str, Any]:
        """Get comprehensive display information for an app.

        Args:
            app_name: Name of the application

        Returns:
            Dictionary with display information including:
            - display_name: Human-readable app name
            - description: App description
            - repo_display: Repository display string (e.g., "owner/repo")
            - repo_url: Full repository URL
            - verify_display: Human-readable verification method
            - icon_display: Human-readable icon method

        Raises:
            FileNotFoundError: If catalog entry doesn't exist
            ValueError: If catalog entry is invalid
        """
        catalog_entry = self.config_manager.load_catalog(app_name)
        entry_dict = catalog_entry  # Already a dict per CatalogEntryV2

        metadata = entry_dict.get("metadata", {})
        source = entry_dict.get("source", {})
        verification = entry_dict.get("verification", {})
        icon = entry_dict.get("icon", {})

        repo_display, repo_url = self._build_repository_display(source)
        verify_display = self._build_verification_display(verification)
        icon_display = self._build_icon_display(icon)

        return {
            "display_name": metadata.get("display_name", app_name),
            "description": metadata.get(
                "description", "No description available"
            ),
            "repo_display": repo_display,
            "repo_url": repo_url,
            "verify_display": verify_display,
            "icon_display": icon_display,
        }

    def list_available_with_descriptions(
        self,
    ) -> list[tuple[str, str]]:
        """List available apps from catalog with descriptions.

        Returns:
            List of (app_name, description) tuples sorted by app name
        """
        apps = self.config_manager.list_catalog_apps()
        app_info = []

        for app in sorted(apps):
            try:
                catalog_entry = self.config_manager.load_catalog(app)
                entry_dict = catalog_entry
                metadata = entry_dict.get("metadata", {})
                description = metadata.get("description", "")
                if not description.strip():
                    description = "No description available"
                app_info.append((app, description))
            except (FileNotFoundError, ValueError):
                # Skip invalid entries
                app_info.append((app, "Error loading catalog entry"))

        return app_info

    def list_installed_with_details(self) -> list[dict[str, str]]:
        """List installed apps with version and date information.

        Returns:
            List of dictionaries containing:
            - app_name: Application name
            - version: Installed version
            - installed_date: Installation date (formatted as YYYY-MM-DD)
            - status: Status message (e.g., "OK", "migration needed")
        """
        apps = self.config_manager.list_installed_apps()
        app_details = []

        for app in sorted(apps):
            try:
                config = self.config_manager.load_app_config(app)
            except ValueError as e:
                if "migrate" in str(e).lower():
                    app_details.append(
                        {
                            "app_name": app,
                            "version": "Unknown",
                            "installed_date": "Unknown",
                            "status": "migration_needed",
                        }
                    )
                else:
                    app_details.append(
                        {
                            "app_name": app,
                            "version": "Unknown",
                            "installed_date": "Unknown",
                            "status": "error",
                        }
                    )
                continue

            if not config:
                app_details.append(
                    {
                        "app_name": app,
                        "version": "Unknown",
                        "installed_date": "Unknown",
                        "status": "config_missing",
                    }
                )
                continue

            # Extract version and date from v2 config
            if "state" in config:
                version = config["state"]["version"]  # type: ignore[typeddict-item]
                installed_date = config["state"].get(  # type: ignore[typeddict-item]
                    "installed_date", "Unknown"
                )

                # Format installation date
                if installed_date != "Unknown":
                    try:
                        date_obj = datetime.fromisoformat(installed_date)
                        installed_date = date_obj.strftime("%Y-%m-%d")
                    except ValueError:
                        pass

                app_details.append(
                    {
                        "app_name": app,
                        "version": version,
                        "installed_date": installed_date,
                        "status": "OK",
                    }
                )
            else:
                # v1 format detected
                app_details.append(
                    {
                        "app_name": app,
                        "version": "Unknown",
                        "installed_date": "Unknown",
                        "status": "migration_needed",
                    }
                )

        return app_details

    @staticmethod
    def format_version_for_display(version: str, max_length: int = 16) -> str:
        """Format version information for display.

        Args:
            version: Version string
            max_length: Maximum display length (default: 16)

        Returns:
            Formatted version string (truncated if necessary)
        """
        if len(version) > max_length:
            return version[: max_length - 3] + "..."
        return version

    @staticmethod
    def _build_repository_display(source: dict[str, Any]) -> tuple[str, str]:
        """Build repository display string and URL.

        Args:
            source: Source configuration dictionary

        Returns:
            Tuple of (repo_display, repo_url)
        """
        if source.get("type") == "github":
            repo_owner = source.get("owner", "")
            repo_name = source.get("repo", "")
            repo_url = f"https://github.com/{repo_owner}/{repo_name}"
            repo_display = f"{repo_owner}/{repo_name}"
        else:
            repo_url = "N/A"
            repo_display = "N/A"
        return repo_display, repo_url

    @staticmethod
    def _build_verification_display(verification: dict[str, Any]) -> str:
        """Build verification method display string.

        Args:
            verification: Verification configuration dictionary

        Returns:
            Human-readable verification method description
        """
        verify_method = verification.get("method", "None")
        if verify_method == "digest":
            return "SHA256 digest (embedded in GitHub release)"
        if verify_method == "checksum_file":
            checksum_file_data = verification.get("checksum_file", {})
            if isinstance(checksum_file_data, dict):
                checksum_file = checksum_file_data.get("name", "Unknown")
                algorithm = str(
                    checksum_file_data.get("algorithm", "SHA256")
                ).upper()
            else:
                checksum_file = "Unknown"
                algorithm = "SHA256"
            return f"{algorithm} checksum ({checksum_file})"
        if verify_method == "skip":
            return "No verification (developer provides no checksums)"
        return "None"

    @staticmethod
    def _build_icon_display(icon: dict[str, Any]) -> str:
        """Build icon method display string.

        Args:
            icon: Icon configuration dictionary

        Returns:
            Human-readable icon method description
        """
        icon_method = icon.get("method", "None")
        if icon_method == "extraction":
            return "Embedded (extracted from AppImage)"
        return "None"
