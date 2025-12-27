#!/usr/bin/env python3
"""Migrate catalog files from v1 to v2 format.

This script converts all catalog JSON files in src/my_unicorn/catalog/
from v1.0.0 format to v2.0.0 format with proper structure and naming.
"""

import json
from pathlib import Path

CATALOG_DIR = Path("src/my_unicorn/catalog")


def migrate_catalog_v1_to_v2(old_catalog: dict) -> dict:
    """Convert v1 catalog to v2.

    Args:
        old_catalog: v1 catalog entry

    Returns:
        v2 catalog entry

    """
    # Determine verification method
    verification_method = _get_verification_method(old_catalog)

    # Build icon config
    icon_config = _get_icon_config(old_catalog)

    # Get appimage config
    appimage_old = old_catalog.get("appimage", {})
    github_old = old_catalog.get("github", {})

    return {
        "config_version": "2.0.0",
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
        "verification": {"method": verification_method},
        "icon": icon_config,
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
        "method": "extraction" if icon.get("extraction") else "download",
        "filename": icon.get("name", ""),
    }
    if icon.get("url"):
        config["download_url"] = icon["url"]
    return config


def main():
    """Migrate all catalog files."""
    if not CATALOG_DIR.exists():
        print(f"Error: Catalog directory {CATALOG_DIR} not found")
        return 1

    catalog_files = list(CATALOG_DIR.glob("*.json"))
    if not catalog_files:
        print(f"No catalog files found in {CATALOG_DIR}")
        return 0

    print(f"Found {len(catalog_files)} catalog files to migrate")
    print()

    migrated_count = 0
    error_count = 0

    for catalog_file in catalog_files:
        try:
            print(f"Migrating {catalog_file.name}...", end=" ")

            # Read old catalog
            with open(catalog_file, encoding="utf-8") as f:
                old_catalog = json.load(f)

            # Check if already v2
            if old_catalog.get("config_version") == "2.0.0":
                print("already v2.0.0, skipping")
                continue

            # Create backup
            backup_file = catalog_file.with_suffix(".json.backup")
            catalog_file.rename(backup_file)

            # Migrate to v2
            new_catalog = migrate_catalog_v1_to_v2(old_catalog)

            # Write new catalog
            with open(catalog_file, "w", encoding="utf-8") as f:
                json.dump(new_catalog, f, indent=2)
                f.write("\n")

            print(f"✓ migrated (backup: {backup_file.name})")
            migrated_count += 1

        except Exception as e:
            print(f"✗ error: {e}")
            error_count += 1
            # Restore from backup if it exists
            if backup_file.exists():
                backup_file.rename(catalog_file)

    print()
    print("Migration complete:")
    print(f"  ✓ Migrated: {migrated_count}")
    print(f"  ✗ Errors: {error_count}")
    print(f"  - Skipped: {len(catalog_files) - migrated_count - error_count}")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
