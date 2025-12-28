"""Catalog configuration migration module.

Handles migration of catalog definition files (catalog/*.json) from v1 to v2.

This module consolidates all catalog migration logic to eliminate duplication.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from my_unicorn.constants import CATALOG_CONFIG_VERSION
from my_unicorn.migration import base

if TYPE_CHECKING:
    from my_unicorn.config import ConfigManager

from my_unicorn.logger import get_logger

logger = get_logger(__name__)


def migrate_catalog_v1_to_v2(old_catalog: dict) -> dict:
    """Migrate catalog from v1 to v2 structure.

    This function is used by both batch migration and individual migration.

    Args:
        old_catalog: v1 catalog data

    Returns:
        v2 catalog data

    """
    appimage_old = old_catalog.get("appimage", {})
    github_old = old_catalog.get("github", {})

    return {
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
        "verification": {"method": _get_verification_method(old_catalog)},
        "icon": _get_icon_config(old_catalog),
    }


def _get_verification_method(old_catalog: dict) -> str:
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


def _get_icon_config(old_catalog: dict) -> dict:
    """Build icon config from old format.

    Args:
        old_catalog: v1 catalog entry

    Returns:
        Icon config dictionary

    """
    icon = old_catalog.get("icon", {})
    config = {
        "method": "extraction",
        "filename": icon.get("name", ""),
    }
    return config


class CatalogMigrator:
    """Migrate catalog configs from v1 to v2 format."""

    def __init__(self, config_manager: "ConfigManager") -> None:
        """Initialize catalog migrator.

        Args:
            config_manager: Config manager instance for directory access

        """
        self.config_manager = config_manager

    def migrate_all(self) -> dict[str, Any]:
        """Migrate all catalog files in catalog directory.

        Returns:
            dict: {"migrated": int, "errors": int}

        """
        catalog_dir = self.config_manager.directory_manager.catalog_dir
        catalog_files = list(catalog_dir.glob("*.json"))

        if not catalog_files:
            logger.info("No catalog files found")
            return {"migrated": 0, "errors": 0}

        migrated = 0
        errors = 0

        for catalog_file in catalog_files:
            try:
                if self._migrate_catalog_file(catalog_file):
                    migrated += 1
            except Exception as e:
                logger.error("Failed to migrate %s: %s", catalog_file, e)
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
        catalog = base.load_json_file(catalog_file)
        current_version = catalog.get("config_version", "1.0.0")

        # Already migrated
        if not base.needs_migration(current_version, CATALOG_CONFIG_VERSION):
            return False

        # Migrate based on version
        if current_version.startswith("1.") or current_version == "1.0.0":
            migrated = migrate_catalog_v1_to_v2(catalog)
        else:
            msg = f"Unsupported catalog version: {current_version}"
            raise ValueError(msg)

        # Save migrated catalog
        base.save_json_file(catalog_file, migrated)

        logger.info(
            "Migrated catalog %s from v%s to v%s",
            catalog_file.name,
            current_version,
            CATALOG_CONFIG_VERSION,
        )

        return True
