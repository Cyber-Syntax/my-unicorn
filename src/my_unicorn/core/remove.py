"""RemoveService: a receiver that handles removal of installed AppImages.

This implementation encapsulates all business logic previously present in
`my_unicorn/commands/remove.py` to respect the Command pattern: commands act
as invokers and services act as receivers that perform the domain logic.
"""

import shutil
from pathlib import Path
from typing import Any

import my_unicorn.core.cache as cache_module
import my_unicorn.core.desktop_entry as desktop_entry_module
from my_unicorn.config import ConfigManager
from my_unicorn.logger import get_logger
from my_unicorn.types import AppConfig, GlobalConfig

logger = get_logger(__name__)


class RemoveService:
    """Service to remove an installed application and related data.

    Responsibilities moved from `RemoveHandler`:
    - Remove AppImage files
    - Remove caches
    - Remove backups
    - Remove desktop entries
    - Remove icon files
    - Remove app config (optionally)
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        global_config: GlobalConfig,
    ) -> None:
        """Create a new RemoveService.

        Args:
            config_manager: Configuration manager used for app config file
                loading and removal.

            global_config: Parsed global configuration mapping with
                directory paths.

        """
        self.config_manager = config_manager
        self.global_config = global_config

    @classmethod
    def create_default(
        cls,
        config_manager: ConfigManager | None = None,
    ) -> "RemoveService":
        """Create RemoveService with default dependencies.

        Factory method for simplified instantiation with sensible defaults.

        Args:
            config_manager: Optional configuration manager (creates new if None)

        Returns:
            Configured RemoveService instance

        """
        config_mgr = config_manager or ConfigManager()
        global_config = config_mgr.load_global_config()

        return cls(
            config_manager=config_mgr,
            global_config=global_config,
        )

    async def remove_app(
        self, app_name: str, keep_config: bool = False
    ) -> dict[str, Any]:
        """Remove an application and its related files.

        Returns a dictionary containing operation results and helpful flags.
        """
        result: dict[str, Any] = {
            "success": True,
            "app_name": app_name,
            "removed_files": [],
            "cache_cleared": False,
            "cache_owner": None,  # For display purposes
            "cache_repo": None,  # For display purposes
            "backup_removed": False,
            "backup_path": None,
            "desktop_entry_removed": False,
            "icon_removed": False,
            "icon_path": None,
            "config_removed": False,
            "error": None,
        }

        try:
            app_config = self.config_manager.load_app_config(app_name)
            if not app_config:
                result["success"] = False
                result["error"] = f"App '{app_name}' not found"
                return result

            # Get effective config for owner/repo and other merged settings
            effective_config = (
                self.config_manager.app_config_manager.get_effective_config(
                    app_name
                )
            )

            # Remove appimage files
            result["removed_files"] = self._remove_appimage_files(app_config)

            # Clear cache if owner/repo present
            cache_cleared, owner, repo = await self._clear_cache(
                effective_config
            )
            result["cache_cleared"] = cache_cleared
            result["cache_owner"] = owner
            result["cache_repo"] = repo

            # Remove backup folder if configured
            result["backup_removed"], result["backup_path"] = (
                self._remove_backups(app_name)
            )

            # Remove desktop entry
            result["desktop_entry_removed"] = self._remove_desktop_entry(
                app_name
            )

            # Remove icon
            icon_removed, icon_path = self._remove_icon(app_config)
            result["icon_removed"] = icon_removed
            result["icon_path"] = icon_path

            # Remove config unless keeping it
            if not keep_config:
                result["config_removed"] = self._remove_config(app_name)

            return result

        except Exception as e:
            logger.error("Failed to remove app %s: %s", app_name, e)
            result["success"] = False
            result["error"] = str(e)
            return result

    def _remove_appimage_files(self, app_config: AppConfig) -> list[str]:
        """Remove appimage files recorded in app config from storage dir.

        Returns a list of removed file paths.
        """
        removed: list[str] = []

        # v2 config: installed_path is in state
        state = app_config.get("state", {})
        installed_path_str = state.get("installed_path")

        if not installed_path_str:
            logger.debug("No installed_path in state; skipping file remove")
            return removed

        appimage_path = Path(installed_path_str)

        try:
            if appimage_path.exists():
                appimage_path.unlink()
                removed.append(str(appimage_path))
                logger.debug("Removed AppImage: %s", appimage_path)
        except Exception as unlink_exc:  # pragma: no cover - logging
            logger.warning(
                "Failed to remove AppImage %s: %s",
                appimage_path,
                unlink_exc,
            )

        if removed:
            logger.debug("Removed AppImage(s): %s", removed)
        else:
            logger.debug("No AppImage file found at: %s", appimage_path)

        return removed

    async def _clear_cache(
        self, effective_config: dict
    ) -> tuple[bool, str | None, str | None]:
        """Clear cache for app if owner/repo available.

        Args:
            effective_config: Merged effective configuration with source dict

        Returns:
            Tuple of (cache_cleared: bool, owner: str|None, repo: str|None)
        """
        try:
            source = effective_config.get("source", {})
            owner = source.get("owner")
            repo = source.get("repo")

            if owner and repo:
                cache_manager = cache_module.get_cache_manager()
                await cache_manager.clear_cache(owner, repo)
                logger.debug("Removed cache for %s/%s", owner, repo)
                return True, owner, repo

            logger.debug("Owner/repo missing in source; skip cache removal")
            return False, None, None
        except Exception as cache_exc:  # pragma: no cover - logging branch
            logger.warning("Failed to remove cache: %s", cache_exc)
            return False, None, None

    def _remove_backups(self, app_name: str) -> tuple[bool, str | None]:
        """Remove backups directory for app and return status and path.

        Returns (removed: bool, path: str|None)
        """
        try:
            backup_base = self.global_config["directory"].get("backup")
            if not backup_base:
                logger.debug(
                    "No backup_dir configured; skip backup removal for %s",
                    app_name,
                )
                return False, None

            backup_dir = Path(backup_base) / app_name
            # Always record backup path for user-facing messages
            backup_path = str(backup_dir)
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
                logger.debug("Removed backups for %s", app_name)
                return True, backup_path

            return False, backup_path
        except Exception as backup_exc:  # pragma: no cover - logging
            logger.warning(
                "Failed to remove backups for %s: %s",
                app_name,
                backup_exc,
            )
            return False, None

    def _remove_desktop_entry(self, app_name: str) -> bool:
        """Attempt to remove a desktop entry for the app.

        Returns True if removal succeeded, otherwise False.
        """
        try:
            removed = desktop_entry_module.remove_desktop_entry_for_app(
                app_name,
                self.config_manager,
            )
            if removed:
                logger.debug("Removed desktop entry for %s", app_name)
            return bool(removed)
        except Exception as desk_exc:  # pragma: no cover - logging
            logger.warning(
                "Failed to remove desktop entry for %s: %s",
                app_name,
                desk_exc,
            )
            return False

    def _remove_icon(self, app_config: AppConfig) -> tuple[bool, str | None]:
        """Remove icon file from icon directory if configured.

        Returns (removed: bool, icon_path: str|None).
        """
        try:
            # v2 config: icon path is in state.icon.path
            state = app_config.get("state", {})
            icon_state = state.get("icon", {})
            icon_path_str = icon_state.get("path")

            if not icon_path_str:
                logger.debug("No icon path in state; skip icon removal")
                return False, None

            icon_path = Path(icon_path_str)

            if icon_path.exists():
                icon_path.unlink()
                logger.debug("Removed icon: %s", icon_path)
                return True, icon_path_str

            logger.debug("Icon file not found: %s", icon_path)
            return False, icon_path_str
        except Exception as icon_exc:  # pragma: no cover - logging
            logger.warning("Failed to remove icon: %s", icon_exc)
            return False, None

    def _remove_config(self, app_name: str) -> bool:
        """Remove app config file from settings if present.

        Returns True if removed, False otherwise.
        """
        try:
            removed = self.config_manager.remove_app_config(app_name)
            if removed:
                logger.debug("Removed config for %s", app_name)
            return bool(removed)
        except Exception as cfg_exc:  # pragma: no cover - logging
            logger.warning(
                "Failed to remove config for %s: %s",
                app_name,
                cfg_exc,
            )
            return False


def display_removal_result(
    result: dict,
    app_name: str,
) -> None:
    """Display results of a removal operation.

    Args:
        result: Result dictionary from RemoveService.remove_app()
        app_name: Name of the app being removed

    """
    if not result:
        logger.info("❌ Failed to remove %s", app_name)
        return

    if not result.get("success"):
        logger.info(
            "❌ %s", result.get("error", f"Failed to remove {app_name}")
        )
        return

    # Log removed files
    if files := result.get("removed_files"):
        logger.info("✅ Removed AppImage(s): %s", ", ".join(files))

    # Log cache clearance
    if result.get("cache_cleared"):
        owner = result.get("cache_owner")
        repo = result.get("cache_repo")
        if owner and repo:
            logger.info("✅ Removed cache for %s/%s", owner, repo)

    # Log backup removal
    if backup_path := result.get("backup_path"):
        if result.get("backup_removed"):
            logger.info("✅ Removed all backups and metadata for %s", app_name)
        else:
            logger.info("⚠️  No backups found at: %s", backup_path)

    # Log desktop entry and icon
    if result.get("desktop_entry_removed"):
        logger.info("✅ Removed desktop entry for %s", app_name)

    if icon_path := result.get("icon_path"):
        if result.get("icon_removed"):
            logger.info("✅ Removed icon: %s", icon_path)
        else:
            logger.info("⚠️  Icon not found at: %s", icon_path)

    # Log config status
    logger.info(
        "✅ %s config for %s",
        "Removed" if result.get("config_removed") else "Kept",
        app_name,
    )
