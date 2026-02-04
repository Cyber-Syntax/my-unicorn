"""Update workflow utilities for post-download processing."""

from pathlib import Path
from typing import Any

from my_unicorn.config import ConfigManager
from my_unicorn.core.backup import BackupService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.github import Asset, Release
from my_unicorn.core.protocols.progress import ProgressReporter
from my_unicorn.core.verification import VerificationService
from my_unicorn.core.workflows.appimage_setup import (
    create_desktop_entry,
    rename_appimage,
    setup_appimage_icon,
)
from my_unicorn.logger import get_logger
from my_unicorn.utils.appimage_utils import verify_appimage_download
from my_unicorn.utils.config_builders import get_stored_hash, update_app_config

logger = get_logger(__name__)


async def process_post_download(
    app_name: str,
    app_config: dict[str, Any],
    latest_version: str,
    owner: str,
    repo: str,
    catalog_entry: dict[str, Any] | None,
    appimage_asset: Asset,
    release_data: Release,
    icon_dir: Path,
    storage_dir: Path,
    downloaded_path: Path,
    verification_service: VerificationService,
    storage_service: FileOperations,
    config_manager: ConfigManager,
    backup_service: BackupService,
    progress_reporter: ProgressReporter | None = None,
) -> bool:
    """Process post-download operations for update workflow.

    This function handles verification, installation, icon setup,
    configuration updates, and desktop entry creation.

    Args:
        app_name: Name of the app
        app_config: App configuration
        latest_version: Latest version being installed
        owner: GitHub owner
        repo: GitHub repository
        catalog_entry: Catalog entry or None
        appimage_asset: AppImage Asset object
        release_data: Release data
        icon_dir: Icon directory path
        storage_dir: Storage directory path
        downloaded_path: Path to downloaded AppImage
        verification_service: Verification service instance
        storage_service: Storage service instance
        config_manager: Configuration manager instance
        backup_service: Backup service instance
        progress_reporter: Optional ProgressReporter protocol implementation

    Returns:
        True if processing was successful, False otherwise

    Raises:
        Exception: If any step in post-download processing fails

    """
    progress_enabled = (
        progress_reporter is not None and progress_reporter.is_active()
    )

    verification_task_id = None
    installation_task_id = None

    def _raise_no_progress_reporter() -> None:
        msg = "Progress reporter is required when progress is enabled"
        raise ValueError(msg)

    def _raise_progress_required() -> None:
        msg = "Progress service is required"
        raise ValueError(msg)

    try:
        if progress_enabled:
            if progress_reporter is None:
                _raise_no_progress_reporter()
            # Protocol doesn't define create_installation_workflow,
            # check if concrete implementation has it
            if hasattr(progress_reporter, "create_installation_workflow"):
                (
                    verification_task_id,
                    installation_task_id,
                ) = await progress_reporter.create_installation_workflow(
                    app_name, with_verification=True
                )

        # Verify download
        verify_result = await verify_appimage_download(
            file_path=downloaded_path,
            asset=appimage_asset,
            release=release_data,
            app_name=app_name,
            verification_service=verification_service,
            verification_config=app_config.get("verification"),
            catalog_entry=catalog_entry,
            owner=owner,
            repo=repo,
            progress_task_id=verification_task_id,
        )
        verification_results = verify_result

        # Move to install directory and make executable
        storage_service.make_executable(downloaded_path)
        appimage_path = storage_service.move_to_install_dir(downloaded_path)

        # Rename to clean name using catalog configuration
        appimage_path = rename_appimage(
            appimage_path=appimage_path,
            app_name=app_name,
            app_config=app_config,
            catalog_entry=catalog_entry,
            storage_service=storage_service,
        )

        # Handle icon setup
        icon_result = await setup_appimage_icon(
            appimage_path=appimage_path,
            app_name=app_name,
            icon_dir=icon_dir,
            app_config=app_config,
            catalog_entry=catalog_entry,
        )
        icon_path = (
            Path(icon_result["path"]) if icon_result.get("path") else None
        )
        updated_icon_config = {
            "source": icon_result.get("source", "none"),
            "installed": icon_result.get("installed", False),
            "path": icon_result.get("path"),
            "extraction": icon_result.get("extraction", False),
            "name": icon_result.get("name", ""),
        }

        # Update configuration
        update_app_config(
            app_name=app_name,
            latest_version=latest_version,
            appimage_path=appimage_path,
            icon_path=icon_path,
            verify_result=verification_results,
            updated_icon_config=updated_icon_config,
            config_manager=config_manager,
        )

        # Clean up old backups after successful update
        try:
            backup_service.cleanup_old_backups(app_name)
        except Exception as e:
            logger.warning(
                "⚠️  Failed to cleanup old backups for %s: %s",
                app_name,
                e,
            )

        # Create desktop entry
        try:
            create_desktop_entry(
                appimage_path=appimage_path,
                app_name=app_name,
                icon_result={
                    "icon_path": str(icon_path) if icon_path else None,
                    "path": str(icon_path) if icon_path else None,
                },
                config_manager=config_manager,
            )
        except Exception:
            logger.exception("Failed to update desktop entry for %s", app_name)

        # Finish installation task
        if installation_task_id and progress_enabled:
            if progress_reporter is None:
                _raise_progress_required()
            await progress_reporter.finish_task(
                installation_task_id,
                success=True,
                description=f"✅ {app_name}",
            )

        # Store the computed hash
        stored_hash = get_stored_hash(
            verification_results.get("methods", {}), appimage_asset
        )
        if stored_hash:
            logger.debug("Updated stored hash: %s", stored_hash[:16])

        return True

    except Exception:
        # Mark installation as failed if we have a progress task
        if installation_task_id and progress_enabled:
            if progress_reporter is None:
                _raise_progress_required()
            await progress_reporter.finish_task(
                installation_task_id,
                success=False,
                description=f"❌ {app_name} installation failed",
            )
        raise
