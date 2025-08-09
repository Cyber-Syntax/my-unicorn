"""Remove command handler for my-unicorn CLI.

This module handles the removal of installed AppImages, including cleanup of
associated files like desktop entries, icons, and configuration data.
"""

from argparse import Namespace

from ..logger import get_logger
from .base import BaseCommandHandler

logger = get_logger(__name__)


class RemoveHandler(BaseCommandHandler):
    """Handler for remove command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the remove command."""
        for app_name in args.apps:
            await self._remove_single_app(app_name, args.keep_config)

    async def _remove_single_app(self, app_name: str, keep_config: bool) -> None:
        """Remove a single app and its associated files."""
        try:
            app_config = self.config_manager.load_app_config(app_name)
            if not app_config:
                print(f"❌ App '{app_name}' not found")
                return

            # Remove AppImage files
            self._remove_appimage_files(app_config, app_name)

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
            logger.error(f"Failed to remove {app_name}: {e}", exc_info=True)
            print(f"❌ Failed to remove {app_name}: {e}")

    def _remove_appimage_files(self, app_config: dict, app_name: str) -> None:
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

        if removed_files:
            print(f"✅ Removed AppImage(s): {', '.join(removed_files)}")
        else:
            print(f"⚠️  AppImage not found: {appimage_path}")

    def _remove_desktop_entry(self, app_name: str) -> None:
        """Remove desktop entry for the app."""
        try:
            from ..desktop import remove_desktop_entry_for_app

            if remove_desktop_entry_for_app(app_name, self.config_manager):
                print(f"✅ Removed desktop entry for {app_name}")
        except Exception as e:
            logger.warning(f"⚠️  Failed to remove desktop entry: {e}")

    def _remove_icon(self, app_config: dict) -> None:
        """Remove icon file if it exists."""
        icon_config = app_config.get("icon", {})
        if not icon_config.get("installed"):
            return

        icon_dir = self.global_config["directory"]["icon"]
        icon_path = icon_dir / icon_config["name"]

        if icon_path.exists():
            icon_path.unlink()
            print(f"✅ Removed icon: {icon_path}")
