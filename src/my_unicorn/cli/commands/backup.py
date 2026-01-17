"""Backup command coordinator.

Thin coordinator that delegates to BackupService and displays results.
"""

from argparse import Namespace
from pathlib import Path

from my_unicorn.core.workflows.backup import BackupService
from my_unicorn.logger import get_logger

from .base import BaseCommandHandler

logger = get_logger(__name__)


class BackupHandler(BaseCommandHandler):
    """Thin coordinator for backup command."""

    async def execute(self, args: Namespace) -> None:
        """Execute the backup command."""
        if not self._validate_arguments(args):
            return

        self._ensure_directories()
        service = BackupService(self.config_manager, self.global_config)

        # Route to appropriate handler
        if args.restore_last:
            await self._restore_last(service, args.app_name)
        elif args.restore_version:
            await self._restore_version(
                service, args.app_name, args.restore_version
            )
        elif args.list_backups:
            await self._list_backups(service, args.app_name)
        elif args.cleanup:
            await self._cleanup(service, args.app_name)
        elif args.info:
            await self._show_info(service, args.app_name)
        else:
            await self._create_backup(service, args.app_name)

    def _validate_arguments(self, args: Namespace) -> bool:
        """Validate command arguments."""
        if args.cleanup and not args.app_name:
            return True  # Global cleanup allowed

        if not args.app_name:
            logger.error("❌ App name is required for this operation")
            logger.info("Usage: backup <app_name> [options]")
            return False

        if (
            not args.app_name.replace("-", "")
            .replace("_", "")
            .replace(".", "")
            .isalnum()
        ):
            logger.error("❌ Invalid app name: %s", args.app_name)
            return False

        return True

    async def _restore_last(
        self, service: BackupService, app_name: str
    ) -> None:
        """Restore latest backup."""
        if not self._check_app_installed(app_name):
            return

        logger.info("🔄 Restoring latest backup for %s...", app_name)
        dest = Path(self.global_config["directory"]["storage"])

        if path := service.restore_latest_backup(app_name, dest):
            config = self.config_manager.load_app_config(app_name)
            version = (
                config.get("state", {}).get("version", "unknown")
                if config
                else "unknown"
            )
            logger.info(
                "✅ Successfully restored %s from latest backup", app_name
            )
            logger.info("Restored to: %s", path)
            logger.info("App configuration updated to version: %s", version)
        else:
            logger.error("❌ No backups found for %s", app_name)

    async def _restore_version(
        self, service: BackupService, app_name: str, version: str
    ) -> None:
        """Restore specific version."""
        if not self._check_app_installed(app_name):
            return

        logger.info("🔄 Restoring %s version %s...", app_name, version)
        dest = Path(self.global_config["directory"]["storage"])

        if path := service.restore_specific_version(app_name, version, dest):
            logger.info("✅ Successfully restored %s v%s", app_name, version)
            logger.info("Restored to: %s", path)
        else:
            logger.error("❌ Version %s not found for %s", version, app_name)

    async def _create_backup(
        self, service: BackupService, app_name: str
    ) -> None:
        """Create backup."""
        if not self._check_app_installed(app_name):
            return

        logger.info("Creating backup for %s...", app_name)
        config = self.config_manager.load_app_config(app_name)
        storage = Path(self.global_config["directory"]["storage"])

        # Get AppImage path
        catalog_ref = config.get("catalog_ref", app_name)
        app_rename = (
            config.get("overrides", {})
            .get("appimage", {})
            .get("rename", catalog_ref)
        )
        appimage_path = storage / f"{app_rename}.AppImage"

        if not appimage_path.exists():
            logger.error("❌ AppImage file not found: %s", appimage_path)
            return

        version = config.get("state", {}).get("version", "unknown")
        if backup_path := service.create_backup(
            appimage_path, app_name, version
        ):
            logger.info(
                "✅ Successfully created backup for %s v%s", app_name, version
            )
            logger.info("Backup saved to: %s", backup_path)
        else:
            logger.error("❌ Failed to create backup for %s", app_name)

    async def _list_backups(
        self, service: BackupService, app_name: str
    ) -> None:
        """List backups."""
        logger.info("Listing backups for %s...", app_name)
        backups = service.get_backup_info(app_name)

        if not backups:
            logger.info("No backups found for %s", app_name)
            return

        logger.info("\nAvailable backups for %s:", app_name)
        logger.info("=" * 60)
        for backup in backups:
            size_mb = backup["size"] / (1024 * 1024) if backup["size"] else 0
            created = (
                backup["created"].strftime("%Y-%m-%d %H:%M:%S")
                if backup["created"]
                else "Unknown"
            )
            symbol = "✅" if backup["exists"] else "❌"
            logger.info("  %s v%s", symbol, backup["version"])
            logger.info("     File: %s", backup["filename"])
            logger.info("     Size: %.1f MB", size_mb)
            logger.info("     Created: %s", created)
            if sha := backup.get("sha256"):
                logger.info("     SHA256: %s...", sha[:16])
            logger.info("")

    async def _cleanup(
        self, service: BackupService, app_name: str | None
    ) -> None:
        """Cleanup old backups."""
        logger.info(
            "🔄 Cleaning up old backups%s...",
            f" for {app_name}" if app_name else " for all apps",
        )
        service.cleanup_old_backups(app_name)
        max_backups = self.global_config["max_backup"]
        if max_backups == 0:
            logger.info("✅ All backups removed (max_backup=0)")
        else:
            logger.info(
                "✅ Cleanup completed (keeping %s most recent backups)",
                max_backups,
            )

    async def _show_info(self, service: BackupService, app_name: str) -> None:
        """Show backup statistics."""
        backups = service.get_backup_info(app_name)

        if not backups:
            logger.info("No backup information available for %s", app_name)
            return

        total_size_mb = sum(b["size"] for b in backups if b["size"]) / (
            1024 * 1024
        )
        logger.info("\n📊 Backup Statistics for %s:", app_name)
        logger.info("=" * 60)
        logger.info("  📦 Total backups: %s", len(backups))
        logger.info("  📏 Total size: %.1f MB", total_size_mb)

        if backups:
            newest = backups[0]
            created = (
                newest["created"].strftime("%Y-%m-%d %H:%M:%S")
                if newest["created"]
                else "Unknown"
            )
            logger.info(
                "  🆕 Latest version: v%s (%s)", newest["version"], created
            )

            if len(backups) > 1:
                oldest = backups[-1]
                created = (
                    oldest["created"].strftime("%Y-%m-%d %H:%M:%S")
                    if oldest["created"]
                    else "Unknown"
                )
                logger.info(
                    "  📜 Oldest version: v%s (%s)",
                    oldest["version"],
                    created,
                )

        logger.info("\n⚙️  Configuration:")
        logger.info(
            "  📁 Backup directory: %s",
            self.global_config["directory"]["backup"],
        )
        max_backups = self.global_config["max_backup"]
        logger.info(
            "  🔄 Max backups kept: %s",
            max_backups if max_backups > 0 else "unlimited",
        )

    def _check_app_installed(self, app_name: str) -> bool:
        """Check if app is installed."""
        if not self.config_manager.load_app_config(app_name):
            logger.error("❌ App '%s' is not installed", app_name)
            logger.info(
                "Use 'my-unicorn catalog' to see installed applications"
            )
            return False
        return True
