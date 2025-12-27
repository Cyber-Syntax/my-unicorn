"""App configuration migration module.

This module provides migration functionality for app state configs (apps/*.json)
and catalog configs (catalog/*.json), separate from the global settings migration.

Architecture:
- AppConfigMigrator: Handles migration of app state files
- CatalogMigrator: Handles migration of catalog definition files
- Both support v1 → v2 migration with backup mechanisms
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import orjson

from my_unicorn.constants import APP_CONFIG_VERSION, CATALOG_CONFIG_VERSION

if TYPE_CHECKING:
    from my_unicorn.config import ConfigManager


class AppConfigMigrator:
    """Migrate app configs from v1 to v2 format.

    Handles migration of individual app state files with:
    - Version validation
    - Backup creation
    - v1 flat structure → v2 hybrid structure conversion
    """

    def __init__(self, config_manager: "ConfigManager") -> None:
        """Initialize app config migrator.

        Args:
            config_manager: Config manager instance for directory access

        """
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)

    def needs_migration(self, config: dict) -> bool:
        """Check if config needs migration.

        Args:
            config: Config dictionary to check

        Returns:
            True if migration needed

        """
        current = config.get("config_version", "1.0.0")
        return current != APP_CONFIG_VERSION

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
        # Load config directly from file without version validation
        # (cannot use load_app_config as it rejects v1 configs)
        app_file = (
            self.config_manager.directory_manager.apps_dir / f"{app_name}.json"
        )

        if not app_file.exists():
            msg = f"Config file not found for {app_name}"
            raise FileNotFoundError(msg)

        with open(app_file, "rb") as f:
            config = orjson.loads(f.read())

        current_version = config.get("config_version", "1.0.0")

        # Check if migration needed
        if current_version == APP_CONFIG_VERSION:
            return {
                "migrated": False,
                "from": current_version,
                "to": APP_CONFIG_VERSION,
            }

        # Create backup
        self._backup_config(app_name, config)

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

        self.logger.info(
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

    def _backup_config(self, app_name: str, config: dict) -> None:
        """Create backup of config before migration.

        Args:
            app_name: Name of app being backed up
            config: Config data to backup

        """
        backup_dir = self.config_manager.directory_manager.apps_dir / "backups"
        backup_dir.mkdir(exist_ok=True)

        backup_file = backup_dir / f"{app_name}.json.backup"

        with open(backup_file, "wb") as f:
            f.write(orjson.dumps(config, option=orjson.OPT_INDENT_2))

        self.logger.info("Created backup: %s", backup_file)

    def _migrate_v1_to_v2(self, old_config: dict, app_name: str) -> dict:
        """Migrate v1 flat structure to v2 hybrid structure.

        Args:
            old_config: v1.x config data
            app_name: Name of the app being migrated

        Returns:
            v2.0.0 config data

        """
        source = old_config.get("source", "catalog")

        # Determine catalog reference
        # For catalog installs, use app_name (matches catalog filename)
        # For URL installs, catalog_ref is None
        catalog_ref = app_name if source == "catalog" else None

        # Build state section from old config
        appimage_old = old_config.get("appimage", {})
        icon_old = old_config.get("icon", {})
        verification_old = old_config.get("verification", {})

        # Migrate verification to new format
        verification_methods = []
        if verification_old.get("skip", False):
            verification_methods.append({"type": "skip", "status": "skipped"})

        # Check if digest verification was done
        if appimage_old.get("digest"):
            digest_str = appimage_old["digest"]
            algorithm = "sha256"  # default
            digest_hash = digest_str

            # Parse "sha256:hash" format
            if ":" in digest_str:
                algorithm, digest_hash = digest_str.split(":", 1)

            verification_methods.append(
                {
                    "type": "digest",
                    "status": "passed",
                    "algorithm": algorithm,
                    "expected": digest_hash,
                    "computed": digest_hash,
                    "source": "github_api",
                }
            )

        new_config = {
            "config_version": APP_CONFIG_VERSION,
            "source": source,
            "catalog_ref": catalog_ref,
            "state": {
                "version": appimage_old.get("version", "unknown"),
                "installed_date": appimage_old.get("installed_date", ""),
                "installed_path": old_config.get("path", ""),
                "verification": {
                    "passed": not verification_old.get("skip", False),
                    "methods": verification_methods,
                },
                "icon": {
                    "installed": icon_old.get("installed", False),
                    "method": "download"
                    if icon_old.get("url")
                    else "extraction",
                    "path": icon_old.get("path", ""),
                },
            },
        }

        # Add overrides only for URL installs
        # Catalog apps get their config from the catalog
        if source == "url":
            github_old = old_config.get("github", {})
            new_config["overrides"] = {
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
                    "method": "skip"
                    if verification_old.get("skip")
                    else "digest"
                },
                "icon": {
                    "method": "download"
                    if icon_old.get("url")
                    else "extraction",
                    "filename": icon_old.get("name", ""),
                },
            }

            # Add URL if download method
            if icon_old.get("url"):
                new_config["overrides"]["icon"]["download_url"] = icon_old[
                    "url"
                ]

        return new_config


class CatalogMigrator:
    """Migrate catalog configs from v1 to v2 format.

    Handles migration of catalog definition files with:
    - Batch migration support
    - v1 structure → v2 structure conversion
    - Verification and icon config migration
    """

    def __init__(self, config_manager: "ConfigManager") -> None:
        """Initialize catalog migrator.

        Args:
            config_manager: Config manager instance for directory access

        """
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)

    def migrate_all(self) -> dict[str, Any]:
        """Migrate all catalog files.

        Returns:
            dict: {"migrated": int, "errors": int}

        """
        from my_unicorn.constants import CATALOG_DIR

        catalog_files = list(Path(CATALOG_DIR).glob("*.json"))
        migrated = 0
        errors = 0

        for catalog_file in catalog_files:
            try:
                if self._migrate_catalog_file(catalog_file):
                    migrated += 1
            except Exception as e:
                self.logger.error("Failed to migrate %s: %s", catalog_file, e)
                errors += 1

        return {"migrated": migrated, "errors": errors}

    def _migrate_catalog_file(self, catalog_file: Path) -> bool:
        """Migrate single catalog file.

        Args:
            catalog_file: Path to catalog file

        Returns:
            True if migrated, False if already up to date

        Raises:
            ValueError: If unsupported catalog version

        """
        with open(catalog_file, "rb") as f:
            catalog = orjson.loads(f.read())

        current_version = catalog.get("config_version", "1.0.0")

        # Already migrated
        if current_version == CATALOG_CONFIG_VERSION:
            return False

        # Migrate based on version
        if current_version.startswith("1.") or current_version == "1.0.0":
            migrated = self._migrate_catalog_v1_to_v2(catalog)
        else:
            msg = f"Unsupported catalog version: {current_version}"
            raise ValueError(msg)

        # Save migrated catalog
        with open(catalog_file, "wb") as f:
            f.write(orjson.dumps(migrated, option=orjson.OPT_INDENT_2))

        self.logger.info(
            "Migrated catalog %s from v%s to v%s",
            catalog_file.name,
            current_version,
            CATALOG_CONFIG_VERSION,
        )

        return True

    def _migrate_catalog_v1_to_v2(self, old_catalog: dict) -> dict:
        """Migrate catalog from v1 to v2 structure.

        Args:
            old_catalog: v1 catalog data

        Returns:
            v2 catalog data

        """
        appimage_old = old_catalog.get("appimage", {})
        github_old = old_catalog.get("github", {})

        # Build v2 structure
        new_catalog = {
            "config_version": CATALOG_CONFIG_VERSION,
            "metadata": {
                "name": old_catalog.get("repo", ""),
                "display_name": old_catalog.get("repo", ""),
                "description": "",
            },
            "source": {
                "type": "github",
                "owner": old_catalog.get("owner", ""),
                "repo": old_catalog.get("repo", ""),
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
                "method": self._get_verification_method(old_catalog)
            },
            "icon": self._get_icon_config(old_catalog),
        }

        return new_catalog

    def _get_verification_method(self, old_catalog: dict) -> str:
        """Determine verification method from old config.

        Args:
            old_catalog: v1 catalog entry

        Returns:
            Verification method string

        """
        verification = old_catalog.get("verification", {})
        if verification.get("skip"):
            return "skip"
        if verification.get("digest"):
            return "digest"
        if verification.get("checksum_file"):
            return "checksum_file"
        return "skip"

    def _get_icon_config(self, old_catalog: dict) -> dict:
        """Build icon config from old format.

        Args:
            old_catalog: v1 catalog entry

        Returns:
            Icon config dictionary

        """
        icon = old_catalog.get("icon", {})
        config = {
            "method": "extraction" if icon.get("extraction") else "download",
            "filename": icon.get("name", ""),
        }
        if icon.get("url"):
            config["download_url"] = icon["url"]
        return config
