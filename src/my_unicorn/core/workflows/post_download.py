"""Post-download processing for install and update workflows.

This module provides unified post-download processing for both install
and update operations, eliminating code duplication while handling
operation-specific differences.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from my_unicorn.config import ConfigManager
from my_unicorn.core.backup import BackupService
from my_unicorn.core.download import DownloadService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.github import Asset, Release
from my_unicorn.core.verification import VerificationService
from my_unicorn.core.workflows.appimage_setup import (
    create_desktop_entry,
    rename_appimage,
    setup_appimage_icon,
)
from my_unicorn.logger import get_logger
from my_unicorn.ui.display import ProgressDisplay
from my_unicorn.utils.appimage_utils import verify_appimage_download
from my_unicorn.utils.config_builders import (
    create_app_config_v2,
    get_stored_hash,
    update_app_config,
)

logger = get_logger(__name__)


class OperationType(Enum):
    """Type of operation being performed."""

    INSTALL = "install"
    UPDATE = "update"


@dataclass
class PostDownloadContext:
    """Context for post-download processing.

    Contains all information needed to process a downloaded AppImage
    for either install or update operations.
    """

    app_name: str
    downloaded_path: Path
    asset: Asset
    release: Release
    app_config: dict[str, Any]
    catalog_entry: dict[str, Any] | None
    operation_type: OperationType
    owner: str
    repo: str
    verify_downloads: bool = True
    source: str = "catalog"  # "catalog" or "url"


@dataclass
class PostDownloadResult:
    """Result of post-download processing.

    Provides structured output with all processing results.
    """

    success: bool
    install_path: Path | None
    verification_result: dict[str, Any] | None
    icon_result: dict[str, Any] | None
    config_result: dict[str, Any] | None
    desktop_result: dict[str, Any] | None
    error: str | None = None


class PostDownloadProcessor:
    """Handles post-download workflow for both install and update.

    This class consolidates the common post-download steps:
    1. Verification (if enabled)
    2. Move and rename AppImage
    3. Setup icon
    4. Create or update configuration
    5. Create desktop entry

    Thread Safety:
        - Safe for concurrent access across multiple asyncio tasks
        - Each operation should use a separate context instance
        - Progress tracking is isolated per context
    """

    def __init__(
        self,
        download_service: DownloadService,
        storage_service: FileOperations,
        config_manager: ConfigManager,
        verification_service: VerificationService | None = None,
        backup_service: BackupService | None = None,
        progress_service: ProgressDisplay | None = None,
    ) -> None:
        """Initialize post-download processor.

        Args:
            download_service: Service for downloading files
            storage_service: Service for storage operations
            config_manager: Configuration manager
            verification_service: Optional verification service
            backup_service: Optional backup service (required for updates)
            progress_service: Optional progress service for tracking

        """
        self.download_service = download_service
        self.storage_service = storage_service
        self.config_manager = config_manager
        self._verification_service = verification_service
        self.backup_service = backup_service
        self.progress_service = progress_service

    async def process(
        self, context: PostDownloadContext
    ) -> PostDownloadResult:
        """Execute post-download workflow.

        Processes a downloaded AppImage through all post-download steps,
        handling differences between install and update operations.

        Args:
            context: Processing context with all required information

        Returns:
            PostDownloadResult with all processing results

        Raises:
            Exception: If any processing step fails

        """
        logger.debug(
            "Post-download processing: app=%s, operation=%s, verify=%s",
            context.app_name,
            context.operation_type.value,
            context.verify_downloads,
        )

        verification_task_id = None
        installation_task_id = None

        try:
            # Setup progress tracking
            (
                verification_task_id,
                installation_task_id,
            ) = await self._setup_progress_tracking(
                context.app_name, context.verify_downloads
            )

            # Step 1: Verify download
            verify_result = await self._verify_download(
                context, verification_task_id
            )

            # Step 2: Install and rename
            install_path = await self._install_and_rename(context)

            # Step 3: Setup icon
            icon_result = await self._setup_icon(context, install_path)

            # Step 4: Create or update config (operation-specific)
            config_result = await self._create_or_update_config(
                context, install_path, verify_result, icon_result
            )

            # Step 5: Create desktop entry
            desktop_result = await self._create_desktop_entry(
                context, install_path, icon_result
            )

            # Step 6: Cleanup (update-specific)
            if context.operation_type == OperationType.UPDATE:
                await self._cleanup_after_update(context.app_name)

            # Step 7: Finalize progress
            if installation_task_id and self.progress_service:
                await self.progress_service.finish_task(
                    installation_task_id,
                    success=True,
                    description=f"✅ {context.app_name}",
                )

            logger.info(
                "Successfully %s %s",
                "installed"
                if context.operation_type == OperationType.INSTALL
                else "updated",
                context.app_name,
            )

            return PostDownloadResult(
                success=True,
                install_path=install_path,
                verification_result=verify_result,
                icon_result=icon_result,
                config_result=config_result,
                desktop_result=desktop_result,
            )

        except Exception as error:
            logger.exception(
                "Post-download processing failed for %s",
                context.app_name,
            )

            # Mark installation task as failed
            if installation_task_id and self.progress_service:
                await self.progress_service.finish_task(
                    installation_task_id,
                    success=False,
                    description=f"❌ {context.app_name} failed",
                )

            return PostDownloadResult(
                success=False,
                install_path=None,
                verification_result=None,
                icon_result=None,
                config_result=None,
                desktop_result=None,
                error=str(error),
            )

    async def _setup_progress_tracking(
        self, app_name: str, with_verification: bool
    ) -> tuple[str | None, str | None]:
        """Setup progress tracking tasks.

        Args:
            app_name: Name of the app
            with_verification: Whether verification is enabled

        Returns:
            Tuple of (verification_task_id, installation_task_id)

        """
        if not self.progress_service or not self.progress_service.is_active():
            return None, None

        return await self.progress_service.create_installation_workflow(
            app_name, with_verification=with_verification
        )

    async def _verify_download(
        self, context: PostDownloadContext, verification_task_id: str | None
    ) -> dict[str, Any] | None:
        """Verify downloaded AppImage.

        Args:
            context: Processing context
            verification_task_id: Progress task ID for verification

        Returns:
            Verification result or None if verification disabled

        """
        if not context.verify_downloads:
            return None

        # Lazy initialization of verification service
        if self._verification_service is None:
            self._verification_service = VerificationService(
                self.download_service.session
            )

        return await verify_appimage_download(
            file_path=context.downloaded_path,
            asset=context.asset,
            release=context.release,
            app_name=context.app_name,
            verification_service=self._verification_service,
            verification_config=context.app_config.get("verification"),
            catalog_entry=context.catalog_entry,
            owner=context.owner,
            repo=context.repo,
            progress_task_id=verification_task_id,
        )

    async def _install_and_rename(self, context: PostDownloadContext) -> Path:
        """Move AppImage to install directory and rename.

        Args:
            context: Processing context

        Returns:
            Path to installed AppImage

        """
        # Make executable and move to install directory
        self.storage_service.make_executable(context.downloaded_path)
        appimage_path = self.storage_service.move_to_install_dir(
            context.downloaded_path
        )

        # Rename to clean name using catalog configuration
        appimage_path = rename_appimage(
            appimage_path=appimage_path,
            app_name=context.app_name,
            app_config=context.app_config,
            catalog_entry=context.catalog_entry,
            storage_service=self.storage_service,
        )

        logger.debug("Installed to path: %s", appimage_path)
        return appimage_path

    async def _setup_icon(
        self, context: PostDownloadContext, install_path: Path
    ) -> dict[str, Any]:
        """Extract and setup icon for the AppImage.

        Args:
            context: Processing context
            install_path: Path where AppImage is installed

        Returns:
            Icon setup result dictionary

        """
        logger.info("Extracting icon for %s", context.app_name)
        global_config = self.config_manager.load_global_config()
        icon_dir = Path(global_config["directory"]["icon"])

        return await setup_appimage_icon(
            appimage_path=install_path,
            app_name=context.app_name,
            icon_dir=icon_dir,
            app_config=context.app_config,
            catalog_entry=context.catalog_entry,
        )

    async def _create_or_update_config(
        self,
        context: PostDownloadContext,
        install_path: Path,
        verify_result: dict[str, Any] | None,
        icon_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Create or update app configuration based on operation type.

        Args:
            context: Processing context
            install_path: Path where AppImage is installed
            verify_result: Verification result or None
            icon_result: Icon setup result

        Returns:
            Configuration result dictionary

        """
        logger.info("Creating/updating config for %s", context.app_name)

        if context.operation_type == OperationType.INSTALL:
            return create_app_config_v2(
                app_name=context.app_name,
                app_path=install_path,
                app_config=context.app_config,
                release=context.release,
                verify_result=verify_result,
                icon_result=icon_result,
                source=context.source,
                config_manager=self.config_manager,
            )

        # UPDATE operation
        verification_results = (
            verify_result.get("methods", {}) if verify_result else {}
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

        update_app_config(
            app_name=context.app_name,
            latest_version=context.release.version,
            appimage_path=install_path,
            icon_path=icon_path,
            verification_results=verification_results,
            updated_icon_config=updated_icon_config,
            config_manager=self.config_manager,
        )

        # Store the computed hash
        stored_hash = get_stored_hash(verification_results, context.asset)
        if stored_hash:
            logger.debug("Updated stored hash: %s", stored_hash[:16])

        return {"success": True, "operation": "update"}

    async def _create_desktop_entry(
        self,
        context: PostDownloadContext,
        install_path: Path,
        icon_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Create or update desktop entry.

        Args:
            context: Processing context
            install_path: Path where AppImage is installed
            icon_result: Icon setup result

        Returns:
            Desktop entry creation result

        """
        logger.info("Creating desktop entry for %s", context.app_name)

        try:
            return create_desktop_entry(
                appimage_path=install_path,
                app_name=context.app_name,
                icon_result=icon_result,
                config_manager=self.config_manager,
            )
        except Exception:
            logger.exception(
                "Failed to create desktop entry for %s", context.app_name
            )
            return {"success": False, "error": "Desktop entry creation failed"}

    async def _cleanup_after_update(self, app_name: str) -> None:
        """Cleanup old backups after successful update.

        Args:
            app_name: Name of the app

        """
        if not self.backup_service:
            logger.debug("No backup service configured, skipping cleanup")
            return

        try:
            self.backup_service.cleanup_old_backups(app_name)
        except Exception as e:
            logger.warning(
                "⚠️  Failed to cleanup old backups for %s: %s",
                app_name,
                e,
            )
