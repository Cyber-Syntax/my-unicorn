"""Backup command handler for AppImage backup and restore operations.

This module provides the command interface for creating backups and restoring
AppImages using the enhanced backup service with versioning support.
"""

from argparse import Namespace
from pathlib import Path

from ..backup import BackupService
from ..logger import get_logger
from .base import BaseCommandHandler

logger = get_logger(__name__)


class BackupHandler(BaseCommandHandler):
    """Handler for backup command operations."""

    def __init__(self, config_manager, auth_manager, update_manager) -> None:
        """Initialize backup handler with dependencies.

        Args:
            config_manager: Configuration manager instance
            auth_manager: GitHub authentication manager
            update_manager: Update manager instance

        """
        super().__init__(config_manager, auth_manager, update_manager)
        self.backup_service = BackupService(config_manager, self.global_config)

    async def execute(self, args: Namespace) -> None:
        """Execute the backup command based on provided arguments.

        Args:
            args: Command line arguments containing backup operation details

        """
        self._ensure_directories()

        # Validate arguments
        if not self._validate_arguments(args):
            return

        if args.restore_last:
            await self._handle_restore_last(args.app_name)
        elif args.restore_version:
            await self._handle_restore_version(args.app_name, args.restore_version)
        elif args.list_backups:
            await self._handle_list_backups(args.app_name)
        elif args.cleanup:
            await self._handle_cleanup(args.app_name)
        elif args.info:
            await self._handle_info(args.app_name)
        elif args.migrate:
            await self._handle_migrate()
        else:
            # Default action: create backup
            await self._handle_create_backup(args.app_name)

    def _validate_arguments(self, args: Namespace) -> bool:
        """Validate command arguments.

        Args:
            args: Command line arguments

        Returns:
            True if arguments are valid, False otherwise

        """
        # Operations that don't require app_name
        if args.migrate or (args.cleanup and not args.app_name):
            return True

        # All other operations require app_name
        if not args.app_name:
            logger.error("❌ App name is required for this operation")
            logger.info("💡 Usage: backup <app_name> [options]")
            logger.info("💡 For global operations, use: backup --cleanup or backup --migrate")
            return False

        # Validate app_name format (basic sanitization)
        if not args.app_name.replace("-", "").replace("_", "").replace(".", "").isalnum():
            logger.error("❌ Invalid app name: %s", args.app_name)
            logger.info(
                "💡 App names should contain only letters, numbers, hyphens, underscores, and dots"
            )
            return False

        return True

    async def _handle_restore_last(self, app_name: str) -> None:
        """Handle restore last backup operation.

        Args:
            app_name: Name of the application to restore

        """
        logger.info("🔄 Restoring latest backup for %s...", app_name)

        # Check if app is installed
        app_config = self.config_manager.load_app_config(app_name)
        if not app_config:
            logger.error("❌ App '%s' is not installed", app_name)
            logger.info("💡 Use 'list' to see installed applications")
            return

        try:
            destination_dir = Path(self.global_config["directory"]["storage"])
            restored_path = self.backup_service.restore_latest_backup(
                app_name, destination_dir
            )

            if restored_path:
                logger.info("✅ Successfully restored %s from latest backup", app_name)
                logger.info("📁 Restored to: %s", restored_path)

                # Show updated app config info
                updated_config = self.config_manager.load_app_config(app_name)
                if updated_config:
                    restored_version = updated_config["appimage"]["version"]
                    logger.info(
                        "📝 App configuration updated to version: %s", restored_version
                    )
                    logger.info("💡 The app is now ready to use with the restored version")
                    logger.info(
                        "🔄 Use 'update' command to check for newer versions if needed"
                    )
            else:
                logger.error("❌ No backups found for %s", app_name)
                logger.info("💡 Create a backup first using the backup command")

        except Exception as e:
            logger.error("❌ Failed to restore %s: %s", app_name, e)

    async def _handle_restore_version(self, app_name: str, version: str) -> None:
        """Handle restore specific version operation.

        Args:
            app_name: Name of the application to restore
            version: Specific version to restore

        """
        logger.info("🔄 Restoring %s version %s...", app_name, version)

        # Check if app is installed
        app_config = self.config_manager.load_app_config(app_name)
        if not app_config:
            logger.error("❌ App '%s' is not installed", app_name)
            logger.info("💡 Use 'list' to see installed applications")
            return

        try:
            destination_dir = Path(self.global_config["directory"]["storage"])
            restored_path = self.backup_service.restore_specific_version(
                app_name, version, destination_dir
            )

            if restored_path:
                logger.info("✅ Successfully restored %s v%s", app_name, version)
                logger.info("📁 Restored to: %s", restored_path)

                # Show updated app config info
                updated_config = self.config_manager.load_app_config(app_name)
                if updated_config:
                    logger.info("📝 App configuration updated to version: %s", version)
                    logger.info("💡 The app is now ready to use with the restored version")
                    logger.info(
                        "🔄 Use 'update' command to check for newer versions if needed"
                    )
            else:
                logger.error("❌ Version %s not found for %s", version, app_name)
                logger.info(
                    "💡 Use 'backup %s --list-backups' to see available versions", app_name
                )

        except Exception as e:
            logger.error("❌ Failed to restore %s v%s: %s", app_name, version, e)

    async def _handle_create_backup(self, app_name: str) -> None:
        """Handle create backup operation.

        Args:
            app_name: Name of the application to backup

        """
        logger.info("💾 Creating backup for %s...", app_name)

        # Check if app is installed
        app_config = self.config_manager.load_app_config(app_name)
        if not app_config:
            logger.error("❌ App '%s' is not installed", app_name)
            logger.info("💡 Use 'list' to see installed applications")
            return

        try:
            # Get the current AppImage path
            storage_dir = Path(self.global_config["directory"]["storage"])
            appimage_name = app_config["appimage"]["name"]
            appimage_path = storage_dir / appimage_name

            if not appimage_path.exists():
                logger.error("❌ AppImage file not found: %s", appimage_path)
                return

            # Create backup
            version = app_config["appimage"]["version"]
            backup_path = self.backup_service.create_backup(appimage_path, app_name, version)

            if backup_path:
                logger.info("✅ Successfully created backup for %s v%s", app_name, version)
                logger.info("📁 Backup saved to: %s", backup_path)
            else:
                logger.error("❌ Failed to create backup for %s", app_name)

        except Exception as e:
            logger.error("❌ Failed to create backup for %s: %s", app_name, e)

    async def _handle_list_backups(self, app_name: str) -> None:
        """Handle list backups operation for a specific app.

        Args:
            app_name: Name of the application

        """
        await self._list_backups_for_app(app_name)

    async def _list_backups_for_app(self, app_name: str) -> None:
        """List backups for a specific app.

        Args:
            app_name: Name of the application

        """
        logger.info("📋 Listing backups for %s...", app_name)

        try:
            backups = self.backup_service.get_backup_info(app_name)

            if not backups:
                print(f"No backups found for {app_name}")
                return

            print(f"\n📋 Available backups for {app_name}:")
            print("=" * 60)

            for backup in backups:
                version = backup["version"]
                size_mb = backup["size"] / (1024 * 1024) if backup["size"] else 0
                created = (
                    backup["created"].strftime("%Y-%m-%d %H:%M:%S")
                    if backup["created"]
                    else "Unknown"
                )
                exists_symbol = "✅" if backup["exists"] else "❌"

                print(f"  {exists_symbol} v{version}")
                print(f"     📁 File: {backup['filename']}")
                print(f"     📏 Size: {size_mb:.1f} MB")
                print(f"     📅 Created: {created}")
                if backup.get("sha256"):
                    print(f"     🔐 SHA256: {backup['sha256'][:16]}...")
                print("")

        except Exception as e:
            logger.error("❌ Failed to list backups for %s: %s", app_name, e)

    async def _handle_cleanup(self, app_name: str | None = None) -> None:
        """Handle cleanup old backups operation.

        Args:
            app_name: Specific app to clean up, or None for all apps

        """
        if app_name:
            print(f"🧹 Cleaning up old backups for {app_name}...")
        else:
            print("🧹 Cleaning up old backups for all apps...")

        try:
            self.backup_service.cleanup_old_backups(app_name)

            max_backups = self.global_config["max_backup"]
            if max_backups == 0:
                print("✅ All backups removed (max_backup=0)")
            else:
                print(f"✅ Cleanup completed (keeping {max_backups} most recent backups)")

        except Exception as e:
            logger.error("❌ Failed to cleanup backups: %s", e)

    async def _handle_info(self, app_name: str) -> None:
        """Handle show backup info operation.

        Args:
            app_name: Name of the application

        """
        print(f"ℹ️  Backup information for {app_name}...")

        try:
            backups = self.backup_service.get_backup_info(app_name)

            if not backups:
                print(f"No backup information available for {app_name}")
                return

            print(f"\n📊 Backup Statistics for {app_name}:")
            print("=" * 60)

            total_backups = len(backups)
            total_size = sum(b["size"] for b in backups if b["size"])
            total_size_mb = total_size / (1024 * 1024)

            oldest_backup = backups[-1] if backups else None
            newest_backup = backups[0] if backups else None

            print(f"  📦 Total backups: {total_backups}")
            print(f"  📏 Total size: {total_size_mb:.1f} MB")

            if newest_backup:
                latest_created = (
                    newest_backup["created"].strftime("%Y-%m-%d %H:%M:%S")
                    if newest_backup["created"]
                    else "Unknown"
                )
                print(f"  🆕 Latest version: v{newest_backup['version']} ({latest_created})")

            if oldest_backup:
                oldest_created = (
                    oldest_backup["created"].strftime("%Y-%m-%d %H:%M:%S")
                    if oldest_backup["created"]
                    else "Unknown"
                )
                print(f"  📜 Oldest version: v{oldest_backup['version']} ({oldest_created})")

            # Backup configuration
            max_backups = self.global_config["max_backup"]
            backup_dir = self.global_config["directory"]["backup"]

            print("\n⚙️  Configuration:")
            print(f"  📁 Backup directory: {backup_dir}")
            print(f"  🔄 Max backups kept: {max_backups if max_backups > 0 else 'unlimited'}")

        except Exception as e:
            logger.error("❌ Failed to get backup info for %s: %s", app_name, e)

    async def _handle_migrate(self) -> None:
        """Handle migration of old backup format."""
        print("🔄 Migrating old backup files to new format...")

        try:
            migrated_count = self.backup_service.migrate_old_backups()

            if migrated_count > 0:
                print(f"✅ Successfully migrated {migrated_count} backup files")
            else:
                print("ℹ️  No old backup files found to migrate")

        except Exception as e:
            logger.error("❌ Failed to migrate old backups: %s", e)
