"""Remove command handler for my-unicorn CLI.

This module handles the removal of installed AppImages, including cleanup of
associated files like desktop entries, icons, and configuration data.
"""

from argparse import Namespace

from my_unicorn.remove_service import RemoveService

from ..logger import get_logger
from .base import BaseCommandHandler

logger = get_logger(__name__)


class RemoveHandler(BaseCommandHandler):
    """Handler for remove command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the remove command."""
        # Create a service receiver to handle removal operations
        service = RemoveService(self.config_manager, self.global_config)
        for app_name in args.apps:
            result = await service.remove_app(app_name, args.keep_config)
            # Print simple CLI feedback similar to the previous behavior
            if not result or not result.get("success", False):
                msg = result.get("error") or f"Failed to remove {app_name}"
                print(f"❌ {msg}")
            else:
                removed_files = result.get("removed_files", [])
                if removed_files:
                    files_str = ", ".join(removed_files)
                    print(f"✅ Removed AppImage(s): {files_str}")
                if result.get("cache_cleared"):
                    # Attempt to get owner/repo from config for useful message
                    app_cfg = self.config_manager.load_app_config(app_name)
                    owner = app_cfg.get("owner") if app_cfg else None
                    repo = app_cfg.get("repo") if app_cfg else None
                    if owner and repo:
                        print(f"✅ Removed cache for {owner}/{repo}")
                else:
                    print("ℹ️  No cache cleared for this app")
                backup_path = result.get("backup_path")
                if backup_path:
                    if result.get("backup_removed"):
                        print(
                            f"✅ Removed all backups and metadata for {app_name}"
                        )
                    else:
                        print(f"⚠️  No backups found at: {backup_path}")
                else:
                    print("ℹ️  No backup directory configured")
                if result.get("desktop_entry_removed"):
                    print(f"✅ Removed desktop entry for {app_name}")
                else:
                    print("ℹ️  No desktop entry removed")
                icon_path = result.get("icon_path")
                if icon_path:
                    if result.get("icon_removed"):
                        print(f"✅ Removed icon: {icon_path}")
                    else:
                        print(f"⚠️  Icon not found at: {icon_path}")
                else:
                    print("ℹ️  No icon configured for this app")
                if result.get("config_removed"):
                    print(f"✅ Removed config for {app_name}")
                else:
                    print(f"✅ Kept config for {app_name}")

    # Old implementation methods were removed; RemoveService handles
    # the domain logic and this handler acts as a CLI invoker.
