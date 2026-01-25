"""RemoveService: a receiver that handles removal of installed AppImages.

This implementation encapsulates all business logic previously present in
`my_unicorn/commands/remove.py` to respect the Command pattern: commands act
as invokers and services act as receivers that perform the domain logic.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import my_unicorn.core.cache as cache_module
import my_unicorn.core.desktop_entry as desktop_entry_module
from my_unicorn.config import ConfigManager
from my_unicorn.logger import get_logger
from my_unicorn.types import AppConfig, GlobalConfig

logger = get_logger(__name__)


@dataclass
class RemovalOperation:
    """Result of a single removal operation."""

    success: bool
    files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RemovalResult:
    """Result of a removal operation."""

    success: bool
    app_name: str
    removed_files: list[str]
    cache_cleared: bool
    cache_owner: str | None
    cache_repo: str | None
    backup_removed: bool
    backup_path: str | None
    desktop_entry_removed: bool
    icon_removed: bool
    icon_path: str | None
    config_removed: bool
    error: str | None = None


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
    ) -> RemoveService:
        """Create RemoveService with default dependencies.

        Factory method for simplified instantiation with sensible defaults.

        Args:
            config_manager: Optional configuration manager
                (creates new if None)

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
    ) -> RemovalResult:
        """Remove an application and its related files.

        Returns a RemovalResult containing operation results and helpful flags.
        """
        try:
            app_config = self.config_manager.load_app_config(app_name)
            if not app_config:
                return RemovalResult(
                    success=False,
                    app_name=app_name,
                    removed_files=[],
                    cache_cleared=False,
                    cache_owner=None,
                    cache_repo=None,
                    backup_removed=False,
                    backup_path=None,
                    desktop_entry_removed=False,
                    icon_removed=False,
                    icon_path=None,
                    config_removed=False,
                    error=f"App '{app_name}' not found",
                )

            effective_config = (
                self.config_manager.app_config_manager.get_effective_config(
                    app_name
                )
            )

            # Execute removal operations
            appimage_op = self._remove_appimage_files(app_config)
            cache_op = await self._clear_cache(effective_config)
            backup_op = self._remove_backups(app_name)
            desktop_op = self._remove_desktop_entry(app_name)
            icon_op = self._remove_icon(app_config)
            config_op = (
                self._remove_config(app_name)
                if not keep_config
                else RemovalOperation(success=True)
            )

            # Log results
            self._log_removal_results(
                app_name,
                appimage_op,
                cache_op,
                backup_op,
                desktop_op,
                icon_op,
                keep_config,
            )

            # Build result dictionary
            return self._build_result(
                app_name,
                appimage_op,
                cache_op,
                backup_op,
                desktop_op,
                icon_op,
                config_op,
                keep_config,
            )

        except Exception:
            logger.exception("Failed to remove app %s", app_name)
            return RemovalResult(
                success=False,
                app_name=app_name,
                removed_files=[],
                cache_cleared=False,
                cache_owner=None,
                cache_repo=None,
                backup_removed=False,
                backup_path=None,
                desktop_entry_removed=False,
                icon_removed=False,
                icon_path=None,
                config_removed=False,
                error="Removal operation failed",
            )

    def _log_removal_results(
        self,
        app_name: str,
        appimage_op: RemovalOperation,
        cache_op: RemovalOperation,
        backup_op: RemovalOperation,
        desktop_op: RemovalOperation,
        icon_op: RemovalOperation,
        keep_config: bool,
    ) -> None:
        """Log user-facing results of removal operations."""
        if appimage_op.files:
            files_str = ", ".join(appimage_op.files)
            logger.info("✅ Removed AppImage(s): %s", files_str)

        if cache_op.metadata.get("owner") and cache_op.metadata.get("repo"):
            logger.info(
                "✅ Removed cache for %s/%s",
                cache_op.metadata["owner"],
                cache_op.metadata["repo"],
            )

        if backup_path := backup_op.metadata.get("path"):
            if backup_op.files:
                logger.info(
                    "✅ Removed all backups and metadata for %s",
                    app_name,
                )
            else:
                logger.info("⚠️  No backups found at: %s", backup_path)

        if desktop_op.success:
            logger.info("✅ Removed desktop entry for %s", app_name)

        if icon_path := icon_op.metadata.get("path"):
            if icon_op.files:
                logger.info("✅ Removed icon: %s", icon_path)
            else:
                logger.info("⚠️  Icon not found at: %s", icon_path)

        if keep_config:
            logger.info("✅ Kept config for %s", app_name)
        else:
            logger.info("✅ Removed config for %s", app_name)

    def _build_result(
        self,
        app_name: str,
        appimage_op: RemovalOperation,
        cache_op: RemovalOperation,
        backup_op: RemovalOperation,
        desktop_op: RemovalOperation,
        icon_op: RemovalOperation,
        config_op: RemovalOperation,
        keep_config: bool,
    ) -> RemovalResult:
        """Build result from removal operations."""
        return RemovalResult(
            success=True,
            app_name=app_name,
            removed_files=appimage_op.files,
            cache_cleared=bool(cache_op.metadata),
            cache_owner=cache_op.metadata.get("owner"),
            cache_repo=cache_op.metadata.get("repo"),
            backup_removed=bool(backup_op.files),
            backup_path=backup_op.metadata.get("path"),
            desktop_entry_removed=desktop_op.success,
            icon_removed=bool(icon_op.files),
            icon_path=icon_op.metadata.get("path"),
            config_removed=config_op.success if not keep_config else False,
            error=None,
        )

    def _remove_appimage_files(
        self, app_config: AppConfig
    ) -> RemovalOperation:
        """Remove appimage files recorded in app config from storage dir."""
        state = app_config.get("state", {})
        installed_path_str = state.get("installed_path")

        if not installed_path_str:
            logger.debug("No installed_path in state; skipping file remove")
            return RemovalOperation(success=True, files=[])

        appimage_path = Path(installed_path_str)

        try:
            if appimage_path.exists():
                appimage_path.unlink()
                logger.debug("Removed AppImage: %s", appimage_path)
                return RemovalOperation(
                    success=True, files=[str(appimage_path)]
                )
            logger.debug("No AppImage file found at: %s", appimage_path)
            return RemovalOperation(success=True, files=[])
        except Exception as unlink_exc:  # pragma: no cover - logging
            logger.warning(
                "Failed to remove AppImage %s: %s",
                appimage_path,
                unlink_exc,
            )
            return RemovalOperation(success=False, files=[])

    async def _clear_cache(self, effective_config: dict) -> RemovalOperation:
        """Clear cache for app if owner/repo available."""
        try:
            source = effective_config.get("source", {})
            owner = source.get("owner")
            repo = source.get("repo")

            if owner and repo:
                cache_manager = cache_module.get_cache_manager()
                await cache_manager.clear_cache(owner, repo)
                logger.debug("Removed cache for %s/%s", owner, repo)
                return RemovalOperation(
                    success=True,
                    metadata={"owner": owner, "repo": repo},
                )

            logger.debug("Owner/repo missing in source; skip cache removal")
            return RemovalOperation(success=True, metadata={})
        except Exception as cache_exc:  # pragma: no cover - logging branch
            logger.warning("Failed to remove cache: %s", cache_exc)
            return RemovalOperation(success=False, metadata={})

    def _remove_backups(self, app_name: str) -> RemovalOperation:
        """Remove backups directory for app."""
        try:
            backup_base = self.global_config["directory"].get("backup")
            if not backup_base:
                logger.debug(
                    "No backup_dir configured; skip backup removal for %s",
                    app_name,
                )
                return RemovalOperation(success=True, metadata={})

            backup_dir = Path(backup_base) / app_name
            backup_path = str(backup_dir)

            if backup_dir.exists():
                shutil.rmtree(backup_dir)
                logger.debug("Removed backups for %s", app_name)
                return RemovalOperation(
                    success=True,
                    files=[backup_path],
                    metadata={"path": backup_path},
                )

            return RemovalOperation(
                success=True, metadata={"path": backup_path}
            )
        except Exception as backup_exc:  # pragma: no cover - logging
            logger.warning(
                "Failed to remove backups for %s: %s",
                app_name,
                backup_exc,
            )
            return RemovalOperation(success=False, metadata={})

    def _remove_desktop_entry(self, app_name: str) -> RemovalOperation:
        """Attempt to remove a desktop entry for the app."""
        try:
            removed = desktop_entry_module.remove_desktop_entry_for_app(
                app_name,
                self.config_manager,
            )
            if removed:
                logger.debug("Removed desktop entry for %s", app_name)
            return RemovalOperation(success=bool(removed))
        except Exception as desk_exc:  # pragma: no cover - logging
            logger.warning(
                "Failed to remove desktop entry for %s: %s",
                app_name,
                desk_exc,
            )
            return RemovalOperation(success=False)

    def _remove_icon(self, app_config: AppConfig) -> RemovalOperation:
        """Remove icon file from icon directory if configured."""
        try:
            state = app_config.get("state", {})
            icon_state = state.get("icon", {})
            icon_path_str = icon_state.get("path")

            if not icon_path_str:
                logger.debug("No icon path in state; skip icon removal")
                return RemovalOperation(success=True, metadata={})

            icon_path = Path(icon_path_str)

            if icon_path.exists():
                icon_path.unlink()
                logger.debug("Removed icon: %s", icon_path)
                return RemovalOperation(
                    success=True,
                    files=[icon_path_str],
                    metadata={"path": icon_path_str},
                )

            logger.debug("Icon file not found: %s", icon_path)
            return RemovalOperation(
                success=True, metadata={"path": icon_path_str}
            )
        except Exception as icon_exc:  # pragma: no cover - logging
            logger.warning("Failed to remove icon: %s", icon_exc)
            return RemovalOperation(success=False, metadata={})

    def _remove_config(self, app_name: str) -> RemovalOperation:
        """Remove app config file from settings if present."""
        try:
            removed = self.config_manager.remove_app_config(app_name)
            if removed:
                logger.debug("Removed config for %s", app_name)
            return RemovalOperation(success=bool(removed))
        except Exception:  # pragma: no cover - logging
            return RemovalOperation(success=False)
