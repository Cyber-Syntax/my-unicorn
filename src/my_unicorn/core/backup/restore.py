"""Backup restore workflow functions for version recovery.

This module provides functions for:
- Restoring latest or specific backup versions
- Atomic file restoration with temporary files
- Configuration updates after restore
- Current version backup before restore
"""

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from my_unicorn.constants import APP_CONFIG_VERSION, BACKUP_TEMP_SUFFIX
from my_unicorn.core.backup.helpers import (
    validate_backup_exists,
    validate_backup_integrity,
)
from my_unicorn.core.backup.metadata import BackupMetadata
from my_unicorn.logger import get_logger
from my_unicorn.utils.datetime_utils import get_current_datetime_local_iso

if TYPE_CHECKING:
    from my_unicorn.config.config import ConfigManager
    from my_unicorn.types import AppStateConfig, GlobalConfig

logger = get_logger(__name__)


def restore_latest_backup(
    app_name: str,
    destination_dir: Path,
    config_manager: "ConfigManager",
    global_config: "GlobalConfig",
) -> Path | None:
    """Restore the latest backup version for an app.

    This function performs the following operations:
    1. Backs up the current version (if different from restore version)
    2. Restores the specified backup version to the proper location
    3. Updates the app configuration with the restored version info
    4. Makes the restored file executable

    Args:
        app_name: Name of the application
        destination_dir: Directory to restore the backup to
        config_manager: Configuration manager for app configs
        global_config: Global configuration dictionary

    Returns:
        Path to restored file or None if no backup exists

    """
    backup_base_dir = Path(global_config["directory"]["backup"])
    app_backup_dir = backup_base_dir / app_name

    if not app_backup_dir.exists():
        logger.warning("No backup directory found for %s", app_name)
        return None

    # Get latest version from metadata
    metadata = BackupMetadata(app_backup_dir)
    latest_version = metadata.get_latest_version()

    if not latest_version:
        logger.warning("No backup versions found for %s", app_name)
        return None

    return _restore_specific_version(
        app_name,
        latest_version,
        destination_dir,
        config_manager,
        global_config,
    )


def restore_specific_version(
    app_name: str,
    version: str,
    destination_dir: Path,
    config_manager: "ConfigManager",
    global_config: "GlobalConfig",
) -> Path | None:
    """Restore a specific version backup for an app.

    This function performs the same workflow as restore_latest_backup
    but for a specific version rather than the latest available.

    Args:
        app_name: Name of the application
        version: Specific version to restore
        destination_dir: Directory to restore the backup to
        config_manager: Configuration manager for app configs
        global_config: Global configuration dictionary

    Returns:
        Path to restored file or None if backup doesn't exist

    """
    return _restore_specific_version(
        app_name, version, destination_dir, config_manager, global_config
    )


def _backup_current_version(
    destination_path: Path,
    app_name: str,
    current_version: str,
    config_manager: "ConfigManager",
    global_config: "GlobalConfig",
) -> None:
    """Backup current version before restore if it exists.

    Args:
        destination_path: Path to current AppImage
        app_name: Name of the application
        current_version: Current version to backup
        config_manager: Configuration manager for app configs
        global_config: Global configuration dictionary

    """
    if not destination_path.exists():
        return

    logger.info(
        "Backing up current version %s before restore...", current_version
    )
    try:
        # Import here to avoid circular dependency
        from my_unicorn.core.backup.service import BackupService

        backup_service = BackupService(
            config_manager=config_manager,
            global_config=global_config,
        )
        # Skip cleanup during restore - will cleanup after restore succeeds
        current_backup_path = backup_service.create_backup(
            destination_path, app_name, current_version, skip_cleanup=True
        )
        if current_backup_path:
            logger.info(
                "Current version backed up to: %s", current_backup_path
            )
        else:
            logger.warning(
                "Failed to backup current version, continuing with restore..."
            )
    except OSError:
        logger.exception(
            "Failed to backup current version, continuing with restore"
        )


def _perform_atomic_restore(
    backup_path: Path,
    destination_path: Path,
    destination_dir: Path,
    appimage_name: str,
) -> None:
    """Restore file atomically using temporary file.

    Args:
        backup_path: Path to backup file
        destination_path: Final destination path
        destination_dir: Destination directory
        appimage_name: Name of the AppImage

    Raises:
        Exception: If restore fails

    """
    with tempfile.NamedTemporaryFile(
        dir=destination_dir,
        prefix=f".{appimage_name}_",
        suffix=BACKUP_TEMP_SUFFIX,
        delete=False,
    ) as tmp_file:
        temp_path = Path(tmp_file.name)

    try:
        shutil.copy2(backup_path, temp_path)
        temp_path.replace(destination_path)
        destination_path.chmod(0o755)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _update_config_after_restore(
    app_name: str,
    version: str,
    version_info: dict[str, Any],
    app_config: dict[str, Any],
    config_manager: "ConfigManager",
) -> None:
    """Update app config with restored version info.

    Args:
        app_name: Name of the application
        version: Restored version
        version_info: Version metadata from backup
        app_config: App configuration dictionary (v2 format)
        config_manager: Configuration manager for persisting changes

    """
    # v2 config: update state section
    state = app_config.get("state", {})
    state["version"] = version
    state["installed_date"] = get_current_datetime_local_iso()

    # Update verification if we have sha256
    if version_info.get("sha256"):
        verification = state.get("verification", {})
        methods = verification.get("methods", [])

        # Update or add digest verification method
        digest_method_found = False
        for method in methods:
            if method.get("type") == "digest":
                method["expected"] = version_info["sha256"]
                method["computed"] = version_info["sha256"]
                method["status"] = "passed"
                digest_method_found = True
                break

        if not digest_method_found:
            methods.append(
                {
                    "type": "digest",
                    "status": "passed",
                    "algorithm": "sha256",
                    "expected": version_info["sha256"],
                    "computed": version_info["sha256"],
                    "source": "backup_restore",
                }
            )

        verification["methods"] = methods
        verification["passed"] = True
        state["verification"] = verification

    app_config["state"] = state

    try:
        config_manager.save_app_config(
            app_name, cast("AppStateConfig", app_config), skip_validation=True
        )
        logger.debug(
            "Updated app config for %s with version %s", app_name, version
        )
    except (ValueError, OSError):
        logger.exception("Failed to update app config for %s", app_name)


def _validate_version_info_and_backup(
    app_name: str,
    version: str,
    app_backup_dir: Path,
) -> tuple[dict[str, Any], Path] | None:
    """Validate version info and backup file exist.

    Args:
        app_name: Name of the application
        version: Version to restore
        app_backup_dir: Application backup directory

    Returns:
        Tuple of (version_info, backup_path) or None if validation fails

    """
    metadata = BackupMetadata(app_backup_dir)
    version_info = metadata.get_version_info(version)

    if not version_info:
        logger.error("Version %s not found for %s", version, app_name)
        return None

    backup_filename = version_info["filename"]
    backup_path = app_backup_dir / backup_filename

    try:
        validate_backup_exists(backup_path)
        validate_backup_integrity(metadata, version, backup_path)
    except (FileNotFoundError, ValueError):
        return None

    return version_info, backup_path


def _load_and_check_app_config(
    app_name: str,
    config_manager: "ConfigManager",
) -> dict[str, Any] | None:
    """Load and validate app config version.

    Args:
        app_name: Name of the application
        config_manager: Configuration manager for app configs

    Returns:
        App configuration or None if validation fails

    """
    app_config = config_manager.load_app_config(app_name)
    if not app_config:
        logger.error("App configuration not found for %s", app_name)
        return None

    config_version = app_config.get("config_version", "1.0.0")
    if config_version != APP_CONFIG_VERSION:
        logger.error(
            "App configuration for %s uses old v%s format",
            app_name,
            config_version,
        )
        logger.info("")
        logger.info("⚠️  Old Configuration Format Detected")
        logger.info("")
        logger.info(
            "The app '%s' uses config version %s (current: %s).",
            app_name,
            config_version,
            APP_CONFIG_VERSION,
        )
        logger.info("Please run the migration command to upgrade to v2:")
        logger.info("")
        logger.info("  my-unicorn migrate")
        logger.info("")
        return None

    return app_config


def _determine_app_path_and_rename(
    app_name: str,
    app_config: dict[str, Any],
    destination_dir: Path,
) -> tuple[str, Path] | None:
    """Determine app rename and destination path from config.

    Args:
        app_name: Name of the application
        app_config: App configuration
        destination_dir: Base directory for restore

    Returns:
        Tuple of (app_rename, destination_path) or None if not found

    """
    catalog_ref = app_config.get("catalog_ref")

    if catalog_ref:
        app_rename = app_name
    else:
        overrides = cast("dict[str, Any]", app_config.get("overrides", {}))
        appimage_config = cast("dict[str, Any]", overrides.get("appimage", {}))
        app_rename = appimage_config.get("rename", app_name)

    if not app_rename:
        app_rename = app_name

    appimage_name = f"{app_rename}.AppImage"
    destination_path = destination_dir / appimage_name
    destination_dir.mkdir(parents=True, exist_ok=True)

    return app_rename, destination_path


def _restore_specific_version(
    app_name: str,
    version: str,
    destination_dir: Path,
    config_manager: "ConfigManager",
    global_config: "GlobalConfig",
) -> Path | None:
    """Internal function to restore a specific version.

    Args:
        app_name: Name of the application
        version: Version to restore
        destination_dir: Directory to restore to
        config_manager: Configuration manager for app configs
        global_config: Global configuration dictionary

    Returns:
        Path to restored file or None if restore failed

    """
    backup_base_dir = Path(global_config["directory"]["backup"])
    app_backup_dir = backup_base_dir / app_name

    if not app_backup_dir.exists():
        logger.error("No backup directory found for %s", app_name)
        return None

    backup_info = _validate_version_info_and_backup(
        app_name, version, app_backup_dir
    )
    if not backup_info:
        return None

    version_info, backup_path = backup_info

    app_config = _load_and_check_app_config(app_name, config_manager)
    if not app_config:
        return None

    path_info = _determine_app_path_and_rename(
        app_name, app_config, destination_dir
    )
    if not path_info:
        return None

    app_rename, destination_path = path_info

    state = cast("dict[str, Any]", app_config.get("state", {}))
    current_version = cast("str", state.get("version", "unknown"))
    if current_version != version:
        _backup_current_version(
            destination_path,
            app_name,
            current_version,
            config_manager,
            global_config,
        )

    try:
        appimage_name = f"{app_rename}.AppImage"
        _perform_atomic_restore(
            backup_path, destination_path, destination_dir, appimage_name
        )

        _update_config_after_restore(
            app_name,
            version,
            version_info,
            app_config,
            config_manager,
        )

    except OSError:
        logger.exception("Failed to restore %s v%s", app_name, version)
        raise
    else:
        backup_base_dir = Path(global_config["directory"]["backup"])
        app_backup_dir = backup_base_dir / app_name

        from my_unicorn.core.backup.service import BackupService

        backup_service = BackupService(
            config_manager=config_manager,
            global_config=global_config,
        )
        backup_service._cleanup_old_backups_for_app(app_backup_dir)  # noqa: SLF001

        logger.info(
            "Restored %s v%s to %s", app_name, version, destination_path
        )
        logger.info("Updated app configuration with restored version")
        return destination_path
