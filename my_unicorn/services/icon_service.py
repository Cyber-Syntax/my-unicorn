"""Shared icon acquisition service to eliminate code duplication."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from my_unicorn.download import DownloadService, IconAsset
from my_unicorn.icon import IconManager
from my_unicorn.services.progress import ProgressService

logger = logging.getLogger(__name__)

# Constants for performance
DEFAULT_ICON_EXTENSION: Final[str] = "png"
SUPPORTED_EXTENSIONS: Final[frozenset[str]] = frozenset([".svg", ".png", ".ico"])
ICON_SOURCE_EXTRACTION: Final[str] = "extraction"
ICON_SOURCE_GITHUB: Final[str] = "github"
ICON_SOURCE_NONE: Final[str] = "none"


@dataclass(slots=True, frozen=True)
class IconConfig:
    """Icon configuration data."""

    extraction_enabled: bool
    icon_url: str | None
    icon_filename: str
    preserve_url_on_extraction: bool = False


@dataclass(slots=True, frozen=True)
class IconResult:
    """Result of icon acquisition attempt."""

    icon_path: Path | None
    source: str  # "extraction", "github", or "none"
    config: dict[str, Any]


class IconService:
    """Shared service for icon acquisition with extraction and GitHub fallback."""

    def __init__(
        self,
        download_service: DownloadService,
        progress_service: ProgressService | None = None,
    ) -> None:
        """Initialize icon service.

        Args:
            download_service: Service for downloading icons from GitHub
            progress_service: Optional progress service for tracking extraction

        """
        self.download_service = download_service
        self.progress_service = progress_service
        self._icon_manager_cache: IconManager | None = None

    def _get_icon_manager(self) -> IconManager:
        """Get cached icon manager instance."""
        if self._icon_manager_cache is None:
            self._icon_manager_cache = IconManager(enable_extraction=True)
        return self._icon_manager_cache

    @staticmethod
    @lru_cache(maxsize=256)
    def _extract_extension_from_url(icon_url: str) -> str:
        """Extract file extension from URL with caching.

        Args:
            icon_url: URL to extract extension from

        Returns:
            File extension without dot, defaults to 'png'

        """
        try:
            url_ext = Path(icon_url).suffix.lower()
            return (
                url_ext.lstrip(".")
                if url_ext in SUPPORTED_EXTENSIONS
                else DEFAULT_ICON_EXTENSION
            )
        except (ValueError, OSError):
            return DEFAULT_ICON_EXTENSION

    def _determine_extraction_preference(
        self,
        current_config: dict[str, Any],
        catalog_entry: dict[str, Any] | None = None,
    ) -> bool:
        """Determine if icon extraction should be enabled.

        Priority order:
        1. Current app config setting
        2. Catalog config setting
        3. Default (True)

        Args:
            current_config: Current icon configuration
            catalog_entry: Catalog entry configuration

        Returns:
            Whether extraction should be enabled

        """
        # Check current app config first
        extraction = current_config.get("extraction")
        if extraction is not None:
            return extraction

        # Check catalog config if available
        if catalog_entry:
            catalog_icon = catalog_entry.get("icon", {})
            catalog_extraction = catalog_icon.get("extraction")
            if catalog_extraction is not None:
                return catalog_extraction

        # Default to enabled
        return True

    def _generate_icon_filename(self, app_name: str, icon_url: str | None = None) -> str:
        """Generate icon filename based on app name and URL.

        Args:
            app_name: Application name
            icon_url: Icon URL to detect extension from

        Returns:
            Generated filename

        """
        if icon_url:
            icon_extension = self._extract_extension_from_url(icon_url)
        else:
            icon_extension = DEFAULT_ICON_EXTENSION

        return f"{app_name}.{icon_extension}"

    async def _attempt_extraction(
        self,
        appimage_path: Path,
        dest_path: Path,
        app_name: str,
    ) -> Path | None:
        """Attempt icon extraction from AppImage.

        Args:
            appimage_path: Path to AppImage file
            dest_path: Destination path for extracted icon
            app_name: Application name for logging

        Returns:
            Path to extracted icon or None if failed

        """
        try:
            logger.info("🔍 Attempting icon extraction from AppImage: %s", app_name)
            extracted_icon = await self._get_icon_manager().extract_icon_only(
                appimage_path=appimage_path,
                dest_path=dest_path,
                app_name=app_name,
            )
            if extracted_icon:
                logger.info("✅ Icon extracted from AppImage for %s", app_name)
                return extracted_icon
        except (OSError, PermissionError) as e:
            logger.info("⚠️  AppImage extraction failed for %s: %s", app_name, e)
        except Exception as e:
            logger.warning("⚠️  Unexpected error during extraction for %s: %s", app_name, e)

        return None

    async def _attempt_github_download(
        self,
        icon_asset: IconAsset,
        dest_path: Path,
        app_name: str,
    ) -> Path | None:
        """Attempt icon download from GitHub.

        Args:
            icon_asset: Icon asset information
            dest_path: Destination path for downloaded icon
            app_name: Application name for logging

        Returns:
            Path to downloaded icon or None if failed

        """
        try:
            logger.info("📥 Downloading icon from GitHub: %s", app_name)
            downloaded_icon = await self.download_service.download_icon(icon_asset, dest_path)
            if downloaded_icon:
                logger.info("✅ Icon downloaded from GitHub for %s", app_name)
                return downloaded_icon
        except (OSError, ConnectionError, TimeoutError) as e:
            logger.warning("⚠️  GitHub icon download failed for %s: %s", app_name, e)
        except Exception as e:
            logger.warning(
                "⚠️  Unexpected error during GitHub download for %s: %s", app_name, e
            )

        return None

    def _build_updated_config(
        self,
        base_config: dict[str, Any],
        icon_source: str,
        icon_path: Path | None,
        icon_filename: str,
        icon_url: str | None,
        extraction_enabled: bool,
        preserve_url_on_extraction: bool,
    ) -> dict[str, Any]:
        """Build updated icon configuration.

        Args:
            base_config: Base configuration to update
            icon_source: Source of acquired icon
            icon_path: Path to acquired icon
            icon_filename: Icon filename
            icon_url: Icon URL
            extraction_enabled: Whether extraction was enabled
            preserve_url_on_extraction: Whether to preserve URL on extraction

        Returns:
            Updated configuration dictionary

        """
        # Use dict constructor for better performance than copy()
        updated_config = dict(base_config)

        # Batch update common fields
        updated_config.update(
            {
                "source": icon_source,
                "name": icon_filename,
                "installed": icon_path is not None,
                "path": str(icon_path) if icon_path else None,
            }
        )

        # Set extraction and URL based on source
        if icon_source == ICON_SOURCE_EXTRACTION:
            updated_config["extraction"] = True
            updated_config["url"] = icon_url if preserve_url_on_extraction else ""
        elif icon_source == ICON_SOURCE_GITHUB:
            updated_config["extraction"] = False
            updated_config["url"] = icon_url or ""
        else:
            # No icon was acquired - preserve current settings
            updated_config["extraction"] = extraction_enabled
            updated_config["url"] = icon_url or ""

        return updated_config

    async def acquire_icon(
        self,
        icon_config: IconConfig,
        app_name: str,
        icon_dir: Path,
        appimage_path: Path,
        current_config: dict[str, Any] | None = None,
        catalog_entry: dict[str, Any] | None = None,
        progress_task_id: Any | None = None,
    ) -> IconResult:
        """Acquire icon using extraction with GitHub fallback.

        Args:
            icon_config: Icon configuration
            app_name: Application name
            icon_dir: Directory where icons should be saved
            appimage_path: Path to AppImage for extraction
            current_config: Current icon configuration (optional)
            catalog_entry: Catalog entry for preference detection (optional)
            progress_task_id: Optional progress task ID for tracking

        Returns:
            IconResult with acquired icon path and updated config

        """
        # Use empty dict as default to avoid mutable default argument issues
        current_config = current_config or {}

        # Create progress task if progress service is available but no task ID provided
        create_own_task = False
        if (
            self.progress_service
            and progress_task_id is None
            and self.progress_service.is_active()
        ):
            progress_task_id = await self.progress_service.create_icon_extraction_task(
                app_name
            )
            create_own_task = True

        # Update progress - starting icon extraction
        if progress_task_id and self.progress_service:
            await self.progress_service.update_task(
                progress_task_id,
                completed=10.0,
                description=f"🎨 Analyzing {app_name} icon...",
            )

        # Determine extraction preference if not explicitly provided
        extraction_enabled = icon_config.extraction_enabled
        if catalog_entry:
            extraction_enabled = self._determine_extraction_preference(
                current_config, catalog_entry
            )

        logger.debug("🎨 Icon extraction for %s: enabled=%s", app_name, extraction_enabled)

        dest_path = icon_dir / icon_config.icon_filename
        icon_source = ICON_SOURCE_NONE
        result_icon_path = None

        # Try extraction first if enabled
        if extraction_enabled:
            # Update progress - extracting from AppImage
            if progress_task_id and self.progress_service:
                await self.progress_service.update_task(
                    progress_task_id,
                    completed=40.0,
                    description=f"🎨 Extracting icon from {app_name}",
                )

            result_icon_path = await self._attempt_extraction(
                appimage_path, dest_path, app_name
            )
            if result_icon_path:
                icon_source = ICON_SOURCE_EXTRACTION

        # Fallback to GitHub download if extraction failed/disabled or no icon found
        if not result_icon_path and icon_config.icon_url:
            # Update progress - downloading from GitHub
            if progress_task_id and self.progress_service:
                await self.progress_service.update_task(
                    progress_task_id,
                    completed=70.0,
                    description=f"🎨 Downloading icon for {app_name}...",
                )

            icon_asset = IconAsset(
                icon_filename=icon_config.icon_filename,
                icon_url=icon_config.icon_url,
            )
            result_icon_path = await self._attempt_github_download(
                icon_asset, dest_path, app_name
            )
            if result_icon_path:
                icon_source = ICON_SOURCE_GITHUB

        # Update progress - finalizing
        if progress_task_id and self.progress_service:
            await self.progress_service.update_task(
                progress_task_id,
                completed=90.0,
                description=f"🎨 Finalizing icon for {app_name}...",
            )

        # Build updated configuration
        updated_config = self._build_updated_config(
            base_config=current_config,
            icon_source=icon_source,
            icon_path=result_icon_path,
            icon_filename=icon_config.icon_filename,
            icon_url=icon_config.icon_url,
            extraction_enabled=extraction_enabled,
            preserve_url_on_extraction=icon_config.preserve_url_on_extraction,
        )

        # Update progress - completed (only finish task if we created it)
        if progress_task_id and self.progress_service and create_own_task:
            if result_icon_path:
                await self.progress_service.finish_task(
                    progress_task_id,
                    success=True,
                    final_description=f"✅ {app_name} icon extraction",
                )
            else:
                await self.progress_service.finish_task(
                    progress_task_id,
                    success=False,
                    final_description=f"❌ {app_name} icon extraction failed",
                )

        # Log results
        if result_icon_path:
            logger.debug(
                "🎨 Icon acquisition completed for %s: source=%s, extraction=%s",
                app_name,
                icon_source,
                updated_config["extraction"],
            )
        else:
            logger.warning("⚠️  No icon acquired for %s", app_name)

        return IconResult(
            icon_path=result_icon_path,
            source=icon_source,
            config=updated_config,
        )
