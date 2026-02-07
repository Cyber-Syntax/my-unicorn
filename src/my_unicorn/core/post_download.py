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
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
)
from my_unicorn.core.verification import VerificationService
from my_unicorn.logger import get_logger
from my_unicorn.utils.appimage_setup import (
    create_desktop_entry,
    rename_appimage,
    setup_appimage_icon,
)
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

    Attributes:
        app_name: Name of the application being processed.
        downloaded_path: Path to the downloaded AppImage file.
        asset: GitHub asset metadata for the downloaded file.
        release: GitHub release information.
        app_config: Application configuration dictionary (v2 format).
        catalog_entry: Catalog entry if installed from catalog, None otherwise.
        operation_type: Type of operation (INSTALL or UPDATE).
        owner: GitHub repository owner.
        repo: GitHub repository name.
        verify_downloads: Whether to verify downloaded file hash.
        source: Installation source ("catalog" or "url").

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

    Attributes:
        success: Whether all processing steps completed successfully.
        install_path: Final path to the installed AppImage, None on failure.
        verification_result: Hash verification result dict, None if skipped.
        icon_result: Icon extraction result dict, None on failure.
        config_result: Configuration save result dict, None on failure.
        desktop_result: Desktop entry creation result dict, None on failure.
        error: Error message if processing failed, None on success.

    """

    success: bool
    install_path: Path | None
    verification_result: dict[str, Any] | None
    icon_result: dict[str, Any] | None
    config_result: dict[str, Any] | None
    desktop_result: dict[str, Any] | None
    error: str | None = None


class PostDownloadProcessor:
    """Handles post-download workflow for both install and update operations.

    This class consolidates the common post-download steps:
    1. Verification (if enabled) - hash/signature verification
    2. Move and rename AppImage - to final install location
    3. Setup icon - extract from AppImage or use fallback
    4. Create or update configuration - save app state
    5. Create desktop entry - for desktop integration

    Attributes:
        download_service: Service for downloading files (used for hash files).
        storage_service: Service for file storage operations.
        config_manager: Configuration manager for app settings.
        backup_service: Service for backup operations (updates only).
        progress_reporter: Progress reporter for tracking steps.

    Thread Safety:
        - Safe for concurrent access across multiple asyncio tasks
        - Each operation should use a separate context instance
        - Progress tracking is isolated per context

    Example:
        >>> from my_unicorn.core.post_download import (
        ...     PostDownloadProcessor, PostDownloadContext, OperationType
        ... )
        >>>
        >>> processor = PostDownloadProcessor(
        ...     download_service=download_service,
        ...     storage_service=file_ops,
        ...     config_manager=config_manager,
        ...     progress_reporter=progress,
        ... )
        >>> context = PostDownloadContext(
        ...     app_name="firefox",
        ...     downloaded_path=Path("/tmp/firefox.AppImage"),
        ...     asset=asset,
        ...     release=release,
        ...     app_config=app_config,
        ...     catalog_entry=None,
        ...     operation_type=OperationType.INSTALL,
        ...     owner="AcmeInc",
        ...     repo="firefox-appimage",
        ... )
        >>> result = await processor.process(context)
        >>> if result.success:
        ...     print(f"Installed to {result.install_path}")

    """

    def __init__(
        self,
        download_service: DownloadService,
        storage_service: FileOperations,
        config_manager: ConfigManager,
        verification_service: VerificationService | None = None,
        backup_service: BackupService | None = None,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        """Initialize post-download processor.

        Args:
            download_service: Service for downloading files
            storage_service: Service for storage operations
            config_manager: Configuration manager
            verification_service: Optional verification service
            backup_service: Optional backup service (required for updates)
            progress_reporter: Optional progress reporter for tracking

        """
        self.download_service = download_service
        self.storage_service = storage_service
        self.config_manager = config_manager
        self._verification_service = verification_service
        self.backup_service = backup_service
        # Apply null object pattern for progress reporter
        self.progress_reporter = progress_reporter or NullProgressReporter()

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

            # Step 7: Finalize progress (null object handles inactive)
            if installation_task_id:
                await self.progress_reporter.finish_task(
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

            # Mark installation task as failed (null object handles inactive)
            if installation_task_id:
                await self.progress_reporter.finish_task(
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
        if not self.progress_reporter.is_active():
            return None, None

        # Use standalone workflow helper if available
        # This requires the reporter to be a ProgressDisplay instance
        from my_unicorn.core.progress.display import ProgressDisplay
        from my_unicorn.core.progress.display_workflows import (
            create_installation_workflow,
        )

        if isinstance(self.progress_reporter, ProgressDisplay):
            return await create_installation_workflow(
                self.progress_reporter,
                app_name,
                with_verification=with_verification,
            )
        return None, None

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
            progress_reporter = getattr(
                self.download_service, "progress_reporter", None
            )
            self._verification_service = VerificationService(
                self.download_service, progress_reporter
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
        verify_result_for_config = verify_result

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
            verify_result=verify_result_for_config,
            updated_icon_config=updated_icon_config,
            config_manager=self.config_manager,
        )

        # Store the computed hash
        stored_hash = get_stored_hash(
            verify_result_for_config.get("methods", {}), context.asset
        )
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
        except Exception as e:
            logger.warning(
                "Failed to create desktop entry for %s: %s",
                context.app_name,
                e,
            )
            # Desktop entry failures are non-fatal,
            # return error dict instead of raising
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
