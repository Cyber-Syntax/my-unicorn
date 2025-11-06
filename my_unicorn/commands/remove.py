"""Remove command handler for my-unicorn CLI.

This module handles the removal of installed AppImages, including cleanup of
associated files like desktop entries, icons, and configuration data.
"""

import shutil
from argparse import Namespace
from pathlib import Path

from my_unicorn.config import AppConfig

from ..logger import get_logger
from .base import BaseCommandHandler

logger = get_logger(__name__)


class RemoveHandler(BaseCommandHandler):
    """Handler for remove command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the remove command."""
        for app_name in args.apps:
            await self._remove_single_app(app_name, args.keep_config)

    async def _remove_single_app(
        self, app_name: str, keep_config: bool
    ) -> None:
        """Remove a single app and its associated files."""
        try:
            app_config = self.config_manager.load_app_config(app_name)
            if not app_config:
                print(f"❌ App '{app_name}' not found")
                logger.debug(
                    "App config for '%s' not found. Skipping removal.",
                    app_name,
                )
                return

            # Remove AppImage files
            self._remove_appimage_files(app_config, app_name)

            # Remove associated cache
            try:
                from ..cache import get_cache_manager

                owner = app_config.get("owner")
                repo = app_config.get("repo")
                if owner and repo:
                    cache_manager = get_cache_manager()
                    await cache_manager.clear_cache(owner, repo)
                    print(f"✅ Removed cache for {owner}/{repo}")
                else:
                    logger.debug(
                        "Owner/repo not found in config; skipping cache removal."
                    )
            except Exception as cache_exc:
                logger.warning(
                    "⚠️ Failed to remove cache for %s: %s", app_name, cache_exc
                )

            # Remove all backups and metadata
            try:
                backup_base = self.global_config["directory"]["backup"]
                backup_dir = Path(backup_base) / app_name
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                    print(
                        f"✅ Removed all backups and metadata for {app_name}"
                    )
                else:
                    logger.debug(
                        "No backup directory found for %s; skipping backup removal.",
                        app_name,
                    )
            except Exception as backup_exc:
                logger.warning(
                    "⚠️ Failed to remove backups for %s: %s",
                    app_name,
                    backup_exc,
                )

            # Remove desktop entry
            self._remove_desktop_entry(app_name)

            # Remove icon
            self._remove_icon(app_config)

            # Remove config unless keeping it
            if not keep_config:
                self.config_manager.remove_app_config(app_name)
                print(f"✅ Removed config for {app_name}")
            else:
                print(f"✅ Kept config for {app_name}")

        except Exception as e:
            logger.error("Failed to remove %s: %s", app_name, e, exc_info=True)
            print(f"❌ Failed to remove {app_name}: {e}")

    def _remove_appimage_files(
        self, app_config: AppConfig, app_name: str
    ) -> None:
        """Remove AppImage files from storage directory."""
        storage_dir = self.global_config["directory"]["storage"]
        appimage_path = storage_dir / app_config["appimage"]["name"]

        # Also try clean name format (lowercase .appimage)
        rename_value = app_config["appimage"].get("rename", app_name)
        clean_name = f"{rename_value.lower()}.appimage"
        clean_appimage_path = storage_dir / clean_name

        removed_files = []
        for path in [appimage_path, clean_appimage_path]:
            if path.exists():
                path.unlink()
                removed_files.append(str(path))
                logger.debug("Removed file: %s", path)

        if removed_files:
            print(f"✅ Removed AppImage(s): {', '.join(removed_files)}")
        else:
            print(f"⚠️  AppImage not found: {appimage_path}")
            logger.debug(
                f"AppImage paths checked but not found: {appimage_path}, {clean_appimage_path}"
            )

    def _remove_desktop_entry(self, app_name: str) -> None:
        """Remove desktop entry for the app."""
        try:
            from ..desktop_entry import remove_desktop_entry_for_app

            if remove_desktop_entry_for_app(app_name, self.config_manager):
                print(f"✅ Removed desktop entry for {app_name}")
        except Exception as e:
            logger.debug(
                "Exception occurred while processing app '%s': %s", app_name, e
            )
            logger.warning("⚠️  Failed to remove desktop entry: %s", e)

    def _remove_icon(self, app_config: AppConfig) -> None:
        """Remove icon file if icon config is present."""
        icon_config = app_config.get("icon", {})
        icon_name = icon_config.get("name")
        if not icon_name:
            logger.debug(
                "No icon name found in config; skipping icon removal."
            )
            return

        icon_dir = self.global_config["directory"]["icon"]
        icon_path = icon_dir / icon_name

        if icon_path.exists():
            icon_path.unlink()
            print(f"✅ Removed icon: {icon_path}")
        else:
            logger.debug(
                "Icon file %s does not exist; nothing to remove.", icon_path
            )
