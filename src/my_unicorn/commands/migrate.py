"""Migration command for upgrading app and catalog configs.

This command provides a manual migration interface for users to upgrade
their configuration files to the latest version. It uses the existing
migration logic in config.py for safety and consistency.
"""

from argparse import Namespace

import orjson

from my_unicorn.constants import APP_CONFIG_VERSION, CATALOG_CONFIG_VERSION
from my_unicorn.logger import get_logger

from .base import BaseCommandHandler

logger = get_logger(__name__)


class MigrateHandler(BaseCommandHandler):
    """Migrate app and catalog configs to latest versions.

    Provides explicit migration control for users upgrading from v1 to v2
    configuration formats. Creates backups before migration.
    """

    async def execute(self, args: Namespace) -> None:
        """Execute migration command.

        Args:
            args: Parsed command-line arguments

        """
        print(f"🔄 Migrating configs to v{APP_CONFIG_VERSION}...")

        # Step 1: Migrate app configs
        app_results = await self._migrate_app_configs()

        # Step 2: Migrate catalog configs
        catalog_results = await self._migrate_catalog_configs()

        # Step 3: Report results
        total_migrated = app_results["migrated"] + catalog_results["migrated"]
        total_errors = app_results["errors"] + catalog_results["errors"]

        if total_errors > 0:
            print(f"\n⚠️  Migration completed with {total_errors} errors")
            return

        if total_migrated == 0:
            print("\nℹ️  All configs already up to date")
            return

        print(f"\n✅ Migration complete! Migrated {total_migrated} configs")
        print("Run 'my-unicorn list' to verify.")

    async def _migrate_app_configs(self) -> dict:
        """Migrate all app configs using AppConfigMigrator.

        Returns:
            dict: {"migrated": int, "errors": int}

        """
        from my_unicorn.app_config_migration import AppConfigMigrator

        apps = self.config_manager.app_config_manager.list_installed_apps()

        if not apps:
            print("ℹ️  No apps installed")
            return {"migrated": 0, "errors": 0}

        migrated = 0
        errors = 0
        migrator = AppConfigMigrator(self.config_manager)

        for app_name in apps:
            try:
                result = migrator.migrate_app(app_name)

                if result["migrated"]:
                    print(
                        f"✅ {app_name}: v{result['from']} → v{result['to']}"
                    )
                    migrated += 1
                else:
                    print(f"ℹ️  {app_name}: already at v{APP_CONFIG_VERSION}")

            except Exception as e:
                print(f"❌ {app_name}: {e}")
                logger.error("Failed to migrate %s: %s", app_name, e)
                errors += 1

        return {"migrated": migrated, "errors": errors}

    async def _migrate_catalog_configs(self) -> dict:
        """Migrate all catalog configs.

        Returns:
            dict: {"migrated": int, "errors": int}

        """
        try:
            catalog_dir = self.config_manager.directory_manager.catalog_dir
            catalog_files = list(catalog_dir.glob("*.json"))

            if not catalog_files:
                print("ℹ️  No catalog files found")
                return {"migrated": 0, "errors": 0}

            migrated = 0

            for catalog_file in catalog_files:
                try:
                    with catalog_file.open("rb") as f:
                        catalog = orjson.loads(f.read())

                    current_version = catalog.get("config_version", "1.0.0")

                    if current_version != CATALOG_CONFIG_VERSION:
                        # Need to migrate
                        # Use the migration logic from scripts
                        migrated_catalog = self._migrate_catalog_v1_to_v2(
                            catalog
                        )

                        # Save migrated catalog
                        with catalog_file.open("wb") as f:
                            f.write(
                                orjson.dumps(
                                    migrated_catalog,
                                    option=orjson.OPT_INDENT_2,
                                )
                            )

                        print(
                            f"✅ {catalog_file.stem}: "
                            f"v{current_version} → v{CATALOG_CONFIG_VERSION}"
                        )
                        migrated += 1
                    else:
                        print(
                            f"ℹ️  {catalog_file.stem}: "
                            f"already at v{CATALOG_CONFIG_VERSION}"
                        )

                except Exception as e:
                    logger.error("Failed to migrate %s: %s", catalog_file, e)
                    print(f"❌ {catalog_file.stem}: {e}")
                    return {"migrated": 0, "errors": 1}

            return {"migrated": migrated, "errors": 0}

        except Exception as e:
            logger.error("Catalog migration failed: %s", e)
            print(f"❌ Catalog migration failed: {e}")
            return {"migrated": 0, "errors": 1}

    def _migrate_catalog_v1_to_v2(self, old_catalog: dict) -> dict:
        """Migrate catalog from v1 to v2 structure.

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
            "verification": {
                "method": self._get_verification_method(old_catalog)
            },
            "icon": self._get_icon_config(old_catalog),
        }

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
