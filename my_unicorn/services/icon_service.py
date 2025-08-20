"""Shared icon acquisition service to eliminate code duplication."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from my_unicorn.download import DownloadService, IconAsset
from my_unicorn.icon import IconManager

logger = logging.getLogger(__name__)


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

    def __init__(self, download_service: DownloadService) -> None:
        """Initialize icon service.

        Args:
            download_service: Service for downloading icons from GitHub

        """
        self.download_service = download_service

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
        if "extraction" in current_config:
            return current_config["extraction"]

        # Check catalog config if available
        if catalog_entry and catalog_entry.get("icon", {}).get("extraction") is not None:
            return catalog_entry.get("icon", {}).get("extraction", True)

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
        icon_extension = "png"  # Default extension

        if icon_url:
            # Try to detect extension from URL
            url_ext = Path(icon_url).suffix.lower()
            if url_ext in [".svg", ".png", ".ico"]:
                icon_extension = url_ext.lstrip(".")

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
            icon_manager = IconManager(self.download_service, enable_extraction=True)
            extracted_icon = await icon_manager.extract_icon_only(
                appimage_path=appimage_path,
                dest_path=dest_path,
                app_name=app_name,
            )
            if extracted_icon:
                logger.info("✅ Icon extracted from AppImage for %s", app_name)
                return extracted_icon
        except Exception as e:
            logger.info("⚠️  AppImage extraction failed for %s: %s", app_name, e)

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
        except Exception as e:
            logger.warning("⚠️  GitHub icon download failed for %s: %s", app_name, e)

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
        updated_config = base_config.copy()
        updated_config["source"] = icon_source
        updated_config["name"] = icon_filename

        # Set installed and path info
        if icon_path is not None:
            updated_config["installed"] = True
            updated_config["path"] = str(icon_path)
        else:
            updated_config["installed"] = False
            updated_config["path"] = None

        # Set extraction flag and URL based on what happened
        if icon_source == "extraction":
            updated_config["extraction"] = True
            updated_config["url"] = icon_url if preserve_url_on_extraction else ""
        elif icon_source == "github":
            updated_config["extraction"] = False
            updated_config["url"] = icon_url
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
    ) -> IconResult:
        """Acquire icon using extraction with GitHub fallback.

        Args:
            icon_config: Icon configuration
            app_name: Application name
            icon_dir: Directory where icons should be saved
            appimage_path: Path to AppImage for extraction
            current_config: Current icon configuration (optional)
            catalog_entry: Catalog entry for preference detection (optional)

        Returns:
            IconResult with acquired icon path and updated config

        """
        current_config = current_config or {}

        # Determine extraction preference if not explicitly provided
        extraction_enabled = icon_config.extraction_enabled
        if catalog_entry:
            extraction_enabled = self._determine_extraction_preference(
                current_config, catalog_entry
            )

        logger.debug(f"🎨 Icon extraction for {app_name}: enabled={extraction_enabled}")

        dest_path = icon_dir / icon_config.icon_filename
        icon_source = "none"
        result_icon_path = None

        # Try extraction first if enabled
        if extraction_enabled:
            result_icon_path = await self._attempt_extraction(
                appimage_path, dest_path, app_name
            )
            if result_icon_path:
                icon_source = "extraction"

        # Fallback to GitHub download if extraction failed/disabled or no icon found
        if not result_icon_path and icon_config.icon_url:
            icon_asset = IconAsset(
                icon_filename=icon_config.icon_filename,
                icon_url=icon_config.icon_url,
            )
            result_icon_path = await self._attempt_github_download(
                icon_asset, dest_path, app_name
            )
            if result_icon_path:
                icon_source = "github"

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

        # Log results
        if result_icon_path:
            logger.debug(
                f"🎨 Icon acquisition completed for {app_name}: "
                f"source={icon_source}, extraction={updated_config['extraction']}"
            )
        else:
            logger.warning(f"⚠️  No icon acquired for {app_name}")

        return IconResult(
            icon_path=result_icon_path,
            source=icon_source,
            config=updated_config,
        )
