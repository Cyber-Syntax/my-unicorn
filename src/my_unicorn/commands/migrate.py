"""Migration command for upgrading app and catalog configs.

Provides manual migration interface for users upgrading configuration files.
Creates backups before migration for safety.
"""

from argparse import Namespace

from my_unicorn.constants import APP_CONFIG_VERSION, CATALOG_CONFIG_VERSION
from my_unicorn.logger import get_logger
from my_unicorn.migration import base
from my_unicorn.migration.app_config import AppConfigMigrator
from my_unicorn.migration.catalog_config import migrate_catalog_v1_to_v2
from my_unicorn.migration.helpers import get_apps_needing_migration

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
        # Check which apps need migration
        apps_to_migrate = get_apps_needing_migration(
            self.config_manager.directory_manager.apps_dir
        )

        if not apps_to_migrate:
            print("ℹ️  All app configs are already up to date")
        else:
            print(
                f"🔄 Found {len(apps_to_migrate)} app(s) to migrate "
                f"to v{APP_CONFIG_VERSION}..."
            )

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

                # Only show apps that were actually migrated
                if result["migrated"]:
                    print(
                        f"✅ {app_name}: v{result['from']} → v{result['to']}"
                    )
                    migrated += 1
                # Silently skip apps already at target version

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
                    catalog = base.load_json_file(catalog_file)
                    current_version = catalog.get("config_version", "1.0.0")

                    if base.needs_migration(
                        current_version, CATALOG_CONFIG_VERSION
                    ):
                        # Migrate and save
                        migrated_catalog = migrate_catalog_v1_to_v2(catalog)
                        base.save_json_file(catalog_file, migrated_catalog)

                        print(
                            f"✅ {catalog_file.stem}: "
                            f"v{current_version} → v{CATALOG_CONFIG_VERSION}"
                        )
                        migrated += 1
                    # Silently skip catalogs already at target version

                except Exception as e:
                    logger.error("Failed to migrate %s: %s", catalog_file, e)
                    print(f"❌ {catalog_file.stem}: {e}")
                    return {"migrated": 0, "errors": 1}

            return {"migrated": migrated, "errors": 0}

        except Exception as e:
            logger.error("Catalog migration failed: %s", e)
            print(f"❌ Catalog migration failed: {e}")
            return {"migrated": 0, "errors": 1}
