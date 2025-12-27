"""App configuration migration module.

Handles migration of app state files (apps/*.json) from v1 to v2 format.

v1 Format (flat structure):
    - All fields in one level
    - Catalog and URL installs stored identically

v2 Format (hybrid structure):
    - Catalog apps: state + catalog_ref only
    - URL apps: state + full config in overrides
    - Clear source field distinguishes types
"""

from typing import TYPE_CHECKING, Any

from my_unicorn.constants import APP_CONFIG_VERSION
from my_unicorn.migration import base

if TYPE_CHECKING:
    from my_unicorn.config import ConfigManager

from my_unicorn.logger import get_logger

logger = get_logger(__name__)


class AppConfigMigrator:
    """Migrate app configs from v1 to v2 format."""

    def __init__(self, config_manager: "ConfigManager") -> None:
        """Initialize app config migrator.

        Args:
            config_manager: Config manager instance for directory access

        """
        self.config_manager = config_manager

    def migrate_app(self, app_name: str) -> dict[str, Any]:
        """Migrate single app config.

        Args:
            app_name: Name of app to migrate

        Returns:
            dict: {"migrated": bool, "from": str, "to": str}

        Raises:
            FileNotFoundError: If app config not found
            ValueError: If unsupported config version

        """
        # Load config file directly (bypass version validation)
        app_file = (
            self.config_manager.directory_manager.apps_dir / f"{app_name}.json"
        )
        config = base.load_json_file(app_file)

        current_version = config.get("config_version", "1.0.0")

        # Check if migration needed
        if not base.needs_migration(current_version, APP_CONFIG_VERSION):
            return {
                "migrated": False,
                "from": current_version,
                "to": APP_CONFIG_VERSION,
            }

        # Create backup before migration
        backup_dir = self.config_manager.directory_manager.apps_dir / "backups"
        base.create_backup(app_file, backup_dir)

        # Migrate based on version
        if current_version.startswith("1."):
            migrated_config = self._migrate_v1_to_v2(config, app_name)
        else:
            msg = f"Unsupported config version: {current_version}"
            raise ValueError(msg)

        # Save migrated config
        self.config_manager.app_config_manager.save_app_config(
            app_name, migrated_config
        )

        logger.info(
            "Migrated %s from v%s to v%s",
            app_name,
            current_version,
            APP_CONFIG_VERSION,
        )

        return {
            "migrated": True,
            "from": current_version,
            "to": APP_CONFIG_VERSION,
        }

    def _migrate_v1_to_v2(self, old_config: dict, app_name: str) -> dict:
        """Migrate v1 flat structure to v2 hybrid structure.

        Args:
            old_config: v1.x config data
            app_name: Name of the app being migrated

        Returns:
            v2.0.0 config data

        """
        source = old_config.get("source", "catalog")
        catalog_ref = app_name if source == "catalog" else None

        # Build new config with state section
        new_config = {
            "config_version": APP_CONFIG_VERSION,
            "source": source,
            "catalog_ref": catalog_ref,
            "state": self._build_state_section(old_config),
        }

        # Add overrides only for URL installs
        if source == "url":
            new_config["overrides"] = self._build_overrides_section(old_config)

        return new_config

    def _build_state_section(self, old_config: dict) -> dict:
        """Build state section from v1 config.

        Args:
            old_config: v1 config data

        Returns:
            State section for v2 config

        """
        appimage_old = old_config.get("appimage", {})
        icon_old = old_config.get("icon", {})

        return {
            "version": appimage_old.get("version", "unknown"),
            "installed_date": appimage_old.get("installed_date", ""),
            "installed_path": old_config.get("installed_path", ""),
            "verification": self._build_verification_state(
                old_config, appimage_old
            ),
            "icon": self._build_icon_state(icon_old),
        }

    def _build_verification_state(
        self, old_config: dict, appimage_old: dict
    ) -> dict:
        """Build verification state from v1 config.

        Args:
            old_config: v1 config data
            appimage_old: v1 appimage section

        Returns:
            Verification state for v2 config

        """
        verification_old = old_config.get("verification", {})
        methods = []

        if verification_old.get("skip", False):
            methods.append({"type": "skip", "status": "skipped"})
        elif appimage_old.get("digest"):
            # Parse digest string (e.g., "sha256:hash")
            digest_str = appimage_old["digest"]
            algorithm = "sha256"  # default
            digest_hash = digest_str

            if ":" in digest_str:
                algorithm, digest_hash = digest_str.split(":", 1)

            methods.append(
                {
                    "type": "digest",
                    "status": "passed",
                    "algorithm": algorithm,
                    "expected": digest_hash,
                    "computed": digest_hash,
                    "source": "github_api",
                }
            )

        return {
            "passed": not verification_old.get("skip", False),
            "methods": methods,
        }

    def _build_icon_state(self, icon_old: dict) -> dict:
        """Build icon state from v1 config.

        Args:
            icon_old: v1 icon section

        Returns:
            Icon state for v2 config

        """
        return {
            "installed": icon_old.get("installed", False),
            "method": "download" if icon_old.get("url") else "extraction",
            "path": icon_old.get("path", ""),
        }

    def _build_overrides_section(self, old_config: dict) -> dict:
        """Build overrides section for URL installs.

        Args:
            old_config: v1 config data

        Returns:
            Overrides section for v2 config

        """
        github_old = old_config.get("github", {})
        appimage_old = old_config.get("appimage", {})
        icon_old = old_config.get("icon", {})
        verification_old = old_config.get("verification", {})

        overrides = {
            "metadata": {
                "name": old_config.get("repo", ""),
                "display_name": old_config.get("repo", ""),
                "description": "",
            },
            "source": {
                "type": "github",
                "owner": old_config.get("owner", ""),
                "repo": old_config.get("repo", ""),
                "prerelease": github_old.get("prerelease", False),
            },
            "appimage": {
                "naming": {
                    "template": appimage_old.get("name_template", ""),
                    "target_name": appimage_old.get("rename", ""),
                    "architectures": ["amd64", "x86_64"],
                }
            },
            "verification": {
                "method": "skip" if verification_old.get("skip") else "digest"
            },
            "icon": {
                "method": "download" if icon_old.get("url") else "extraction",
                "filename": icon_old.get("name", ""),
            },
        }

        # Add URL if download method
        if icon_old.get("url"):
            overrides["icon"]["download_url"] = icon_old["url"]

        return overrides
