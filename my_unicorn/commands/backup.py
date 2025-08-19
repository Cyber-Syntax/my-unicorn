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
        if (
            args.migrate
            or (args.list_backups and not args.app_name)
            or (args.cleanup and not args.app_name)
        ):
            return True

        # All other operations require app_name
        if not args.app_name:
            logger.error("❌ App name is required for this operation")
            logger.info("💡 Usage: backup <app_name> [options]")
            logger.info(
                "💡 For global operations, use: backup --list-backups, backup --cleanup, or backup --migrate"
            )
            return False

        # Validate app_name format (basic sanitization)
        if not args.app_name.replace("-", "").replace("_", "").replace(".", "").isalnum():
            logger.error(f"❌ Invalid app name: {args.app_name}")
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
        logger.info(f"🔄 Restoring latest backup for {app_name}...")

        # Check if app is installed
        app_config = self.config_manager.load_app_config(app_name)
        if not app_config:
            logger.error(f"❌ App '{app_name}' is not installed")
            logger.info("💡 Use 'list' to see installed applications")
            return

        try:
            destination_dir = Path(self.global_config["directory"]["storage"])
            restored_path = self.backup_service.restore_latest_backup(
                app_name, destination_dir
            )

            if restored_path:
                logger.info(f"✅ Successfully restored {app_name} from latest backup")
                logger.info(f"📁 Restored to: {restored_path}")

                # Show updated app config info
                updated_config = self.config_manager.load_app_config(app_name)
                if updated_config:
                    restored_version = updated_config["appimage"]["version"]
                    logger.info(f"📝 App configuration updated to version: {restored_version}")
                    logger.info("💡 The app is now ready to use with the restored version")
                    logger.info(
                        "🔄 Use 'update' command to check for newer versions if needed"
                    )
            else:
                logger.error(f"❌ No backups found for {app_name}")
                logger.info("💡 Create a backup first using the backup command")

        except Exception as e:
            logger.error(f"❌ Failed to restore {app_name}: {e}")

    async def _handle_restore_version(self, app_name: str, version: str) -> None:
        """Handle restore specific version operation.

        Args:
            app_name: Name of the application to restore
            version: Specific version to restore

        """
        logger.info(f"🔄 Restoring {app_name} version {version}...")

        # Check if app is installed
        app_config = self.config_manager.load_app_config(app_name)
        if not app_config:
            logger.error(f"❌ App '{app_name}' is not installed")
            logger.info("💡 Use 'list' to see installed applications")
            return

        try:
            destination_dir = Path(self.global_config["directory"]["storage"])
            restored_path = self.backup_service.restore_specific_version(
                app_name, version, destination_dir
            )

            if restored_path:
                logger.info(f"✅ Successfully restored {app_name} v{version}")
                logger.info(f"📁 Restored to: {restored_path}")

                # Show updated app config info
                updated_config = self.config_manager.load_app_config(app_name)
                if updated_config:
                    logger.info(f"📝 App configuration updated to version: {version}")
                    logger.info("💡 The app is now ready to use with the restored version")
                    logger.info(
                        "🔄 Use 'update' command to check for newer versions if needed"
                    )
            else:
                logger.error(f"❌ Version {version} not found for {app_name}")
                logger.info(
                    f"💡 Use 'backup {app_name} --list-backups' to see available versions"
                )

        except Exception as e:
            logger.error(f"❌ Failed to restore {app_name} v{version}: {e}")

    async def _handle_create_backup(self, app_name: str) -> None:
        """Handle create backup operation.

        Args:
            app_name: Name of the application to backup

        """
        logger.info(f"💾 Creating backup for {app_name}...")

        # Check if app is installed
        app_config = self.config_manager.load_app_config(app_name)
        if not app_config:
            logger.error(f"❌ App '{app_name}' is not installed")
            logger.info("💡 Use 'list' to see installed applications")
            return

        try:
            # Get the current AppImage path
            storage_dir = Path(self.global_config["directory"]["storage"])
            appimage_name = app_config["appimage"]["name"]
            appimage_path = storage_dir / appimage_name

            if not appimage_path.exists():
                logger.error(f"❌ AppImage file not found: {appimage_path}")
                return

            # Create backup
            version = app_config["appimage"]["version"]
            backup_path = self.backup_service.create_backup(appimage_path, app_name, version)

            if backup_path:
                logger.info(f"✅ Successfully created backup for {app_name} v{version}")
                logger.info(f"📁 Backup saved to: {backup_path}")
            else:
                logger.error(f"❌ Failed to create backup for {app_name}")

        except Exception as e:
            logger.error(f"❌ Failed to create backup for {app_name}: {e}")

    async def _handle_list_backups(self, app_name: str | None = None) -> None:
        """Handle list backups operation.

        Args:
            app_name: Name of specific app or None to list all apps with backups

        """
        if app_name:
            await self._list_backups_for_app(app_name)
        else:
            await self._list_all_apps_with_backups()

    async def _list_backups_for_app(self, app_name: str) -> None:
        """List backups for a specific app.

        Args:
            app_name: Name of the application

        """
        logger.info(f"📋 Listing backups for {app_name}...")

        try:
            backups = self.backup_service.get_backup_info(app_name)

            if not backups:
                logger.info(f"No backups found for {app_name}")
                return

            logger.info(f"\n📦 Available backups for {app_name}:")
            logger.info("=" * 60)

            for backup in backups:
                version = backup["version"]
                size_mb = backup["size"] / (1024 * 1024) if backup["size"] else 0
                created = (
                    backup["created"].strftime("%Y-%m-%d %H:%M:%S")
                    if backup["created"]
                    else "Unknown"
                )
                exists_symbol = "✅" if backup["exists"] else "❌"

                logger.info(f"  {exists_symbol} v{version}")
                logger.info(f"     📁 File: {backup['filename']}")
                logger.info(f"     📏 Size: {size_mb:.1f} MB")
                logger.info(f"     📅 Created: {created}")
                if backup.get("sha256"):
                    logger.info(f"     🔐 SHA256: {backup['sha256'][:16]}...")
                logger.info("")

        except Exception as e:
            logger.error(f"❌ Failed to list backups for {app_name}: {e}")

    async def _list_all_apps_with_backups(self) -> None:
        """List all apps that have backups."""
        logger.info("📋 Listing all apps with backups...")

        try:
            apps_with_backups = self.backup_service.list_apps_with_backups()

            if not apps_with_backups:
                logger.info("No apps with backups found")
                logger.info("💡 Create backups using 'backup <app_name>'")
                return

            logger.info(f"\n📦 Apps with backups ({len(apps_with_backups)}):")
            logger.info("=" * 60)

            for app_name in apps_with_backups:
                backups = self.backup_service.get_backup_info(app_name)
                backup_count = len(backups)
                latest_version = backups[0]["version"] if backups else "Unknown"

                logger.info(f"  📱 {app_name}")
                logger.info(f"     📊 Backups: {backup_count}")
                logger.info(f"     🔄 Latest: v{latest_version}")
                logger.info("")

            logger.info("💡 Use 'backup <app_name> --list-backups' for detailed info")

        except Exception as e:
            logger.error(f"❌ Failed to list apps with backups: {e}")

    async def _handle_cleanup(self, app_name: str | None = None) -> None:
        """Handle cleanup old backups operation.

        Args:
            app_name: Specific app to clean up, or None for all apps

        """
        if app_name:
            logger.info(f"🧹 Cleaning up old backups for {app_name}...")
        else:
            logger.info("🧹 Cleaning up old backups for all apps...")

        try:
            self.backup_service.cleanup_old_backups(app_name)

            max_backups = self.global_config["max_backup"]
            if max_backups == 0:
                logger.info("✅ All backups removed (max_backup=0)")
            else:
                logger.info(
                    f"✅ Cleanup completed (keeping {max_backups} most recent backups)"
                )

        except Exception as e:
            logger.error(f"❌ Failed to cleanup backups: {e}")

    async def _handle_info(self, app_name: str) -> None:
        """Handle show backup info operation.

        Args:
            app_name: Name of the application

        """
        logger.info(f"ℹ️  Backup information for {app_name}...")

        try:
            backups = self.backup_service.get_backup_info(app_name)

            if not backups:
                logger.info(f"No backup information available for {app_name}")
                return

            logger.info(f"\n📊 Backup Statistics for {app_name}:")
            logger.info("=" * 60)

            total_backups = len(backups)
            total_size = sum(b["size"] for b in backups if b["size"])
            total_size_mb = total_size / (1024 * 1024)

            oldest_backup = backups[-1] if backups else None
            newest_backup = backups[0] if backups else None

            logger.info(f"  📦 Total backups: {total_backups}")
            logger.info(f"  📏 Total size: {total_size_mb:.1f} MB")

            if newest_backup:
                latest_created = (
                    newest_backup["created"].strftime("%Y-%m-%d %H:%M:%S")
                    if newest_backup["created"]
                    else "Unknown"
                )
                logger.info(
                    f"  🆕 Latest version: v{newest_backup['version']} ({latest_created})"
                )

            if oldest_backup:
                oldest_created = (
                    oldest_backup["created"].strftime("%Y-%m-%d %H:%M:%S")
                    if oldest_backup["created"]
                    else "Unknown"
                )
                logger.info(
                    f"  📜 Oldest version: v{oldest_backup['version']} ({oldest_created})"
                )

            # Backup configuration
            max_backups = self.global_config["max_backup"]
            backup_dir = self.global_config["directory"]["backup"]

            logger.info("\n⚙️  Configuration:")
            logger.info(f"  📁 Backup directory: {backup_dir}")
            logger.info(
                f"  🔄 Max backups kept: {max_backups if max_backups > 0 else 'unlimited'}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to get backup info for {app_name}: {e}")

    async def _handle_migrate(self) -> None:
        """Handle migration of old backup format."""
        logger.info("🔄 Migrating old backup files to new format...")

        try:
            migrated_count = self.backup_service.migrate_old_backups()

            if migrated_count > 0:
                logger.info(f"✅ Successfully migrated {migrated_count} backup files")
            else:
                logger.info("ℹ️  No old backup files found to migrate")

        except Exception as e:
            logger.error(f"❌ Failed to migrate old backups: {e}")
