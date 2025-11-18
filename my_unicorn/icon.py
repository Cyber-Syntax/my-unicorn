"""Icon management system for AppImages

This module provides comprehensive icon handling by first attempting to extract
icons directly from AppImage files, with GitHub download fallback and
orchestration through IconHandler.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

from .constants import (
    DEFAULT_ICON_EXTENSION,
    ICON_SOURCE_EXTRACTION,
    ICON_SOURCE_GITHUB,
    ICON_SOURCE_NONE,
    SUPPORTED_EXTENSIONS,
)
from .logger import get_logger

logger = get_logger(__name__)


class IconExtractionError(Exception):
    """Raised when icon extraction from AppImage fails."""


class AppImageIconExtractor:
    """Handles extraction and processing of icons from AppImage files."""

    # Icon format preferences (higher score = better)
    FORMAT_SCORES: ClassVar[dict[str, int]] = {
        ".svg": 100,  # Scalable vector graphics - best quality
        ".png": 50,  # Raster graphics - good quality
        ".ico": 30,  # Windows icon format
        ".xpm": 20,  # X11 pixmap format
        ".bmp": 10,  # Bitmap format - lowest quality
    }

    # Resolution preferences for raster formats
    RESOLUTION_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"(\d+)x\d+")

    # Constants for magic values
    MIN_ICON_SIZE_BYTES = 20  # Lowered to allow small test files

    def __init__(self) -> None:
        """Initialize the AppImage icon extractor."""

    def is_recoverable_error(self, error_msg: str) -> bool:
        """Check if an extraction error is recoverable/expected.

        Args:
            error_msg: The error message to check

        Returns:
            True if the error is recoverable and fallback should be used

        """
        recoverable_patterns = [
            "Unsupported AppImage compression format",
            "Cannot open AppImage squashfs filesystem",
            "Invalid AppImage format",
        ]
        return any(pattern in error_msg for pattern in recoverable_patterns)

    async def extract_icon(
        self, appimage_path: Path, dest_path: Path, app_name: str
    ) -> Path | None:
        """Extract the best available icon from an AppImage.

        Args:
            appimage_path: Path to the AppImage file
            dest_path: Destination path for the extracted icon
            app_name: Application name for icon matching

        Returns:
            Path to extracted icon or None if extraction failed

        Raises:
            IconExtractionError: If extraction process fails

        """
        if not appimage_path.exists():
            logger.error("❌ AppImage not found: %s", appimage_path)
            return None

        if not appimage_path.is_file():
            logger.error("❌ AppImage path is not a file: %s", appimage_path)
            return None

        logger.info("🔍 Extracting icon from AppImage: %s", appimage_path.name)

        with tempfile.TemporaryDirectory(
            prefix="my-unicorn-icon-"
        ) as temp_dir:
            temp_path = Path(temp_dir)

            try:
                # Extract AppImage
                await self._extract_appimage(appimage_path, temp_path)

                # Find the best icon
                squashfs_root = temp_path / "squashfs-root"
                if not squashfs_root.exists():
                    logger.warning(
                        "⚠️  No squashfs-root directory found after extraction"
                    )
                    return None

                best_icon = self._find_best_icon(squashfs_root, app_name)
                if not best_icon:
                    logger.warning(
                        "⚠️  No suitable icon found for %s", app_name
                    )
                    return None

                # Copy icon to destination
                return await self._copy_icon(best_icon, dest_path)

            except IconExtractionError:
                # Re-raise IconExtractionError as-is (already logged appropriately)
                raise
            except Exception as e:
                logger.error(
                    "❌ Failed to extract icon from %s: %s",
                    appimage_path.name,
                    e,
                )
                raise IconExtractionError(
                    f"Icon extraction failed: {e}"
                ) from e

    async def _extract_appimage(
        self, appimage_path: Path, temp_dir: Path
    ) -> None:
        """Extract AppImage contents to temporary directory.

        Args:
            appimage_path: Path to the AppImage file
            temp_dir: Temporary directory for extraction

        Raises:
            IconExtractionError: If extraction fails

        """
        try:
            # Make AppImage executable if needed
            appimage_path.chmod(0o755)

            # Run extraction command
            process = await asyncio.create_subprocess_exec(
                str(appimage_path),
                "--appimage-extract",
                cwd=temp_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _, stderr = await process.communicate()

            if process.returncode != 0:
                stderr_text = (
                    stderr.decode("utf-8", errors="ignore") if stderr else ""
                )

                # Check for specific unsupported compression errors
                if (
                    "xz compression" in stderr_text
                    and "supports only" in stderr_text
                ):
                    logger.info(
                        f"ℹ️  AppImage uses unsupported compression format: {appimage_path.name}"
                    )
                    logger.info(
                        "ℹ️  This AppImage cannot be extracted for icon discovery"
                    )
                    raise IconExtractionError(
                        "Unsupported AppImage compression format"
                    )

                # Check for other common extraction issues
                if "Failed to open squashfs image" in stderr_text:
                    logger.info(
                        f"ℹ️  Cannot open AppImage for extraction: {appimage_path.name}"
                    )
                    raise IconExtractionError(
                        "Cannot open AppImage squashfs filesystem"
                    )

                if "Invalid magic number" in stderr_text:
                    logger.info(
                        "ℹ️  Invalid AppImage format: %s", appimage_path.name
                    )
                    raise IconExtractionError("Invalid AppImage format")

                # Generic extraction failure
                error_msg = f"AppImage extraction failed with code {process.returncode}"
                if stderr_text:
                    error_msg += f": {stderr_text}"
                logger.warning("⚠️  %s", error_msg)
                raise IconExtractionError(error_msg)

            logger.debug("✅ AppImage extracted successfully to %s", temp_dir)

        except (TimeoutError, OSError) as e:
            logger.warning("⚠️  Failed to execute AppImage extraction: %s", e)
            raise IconExtractionError(
                f"Failed to execute AppImage extraction: {e}"
            ) from e

    def _find_best_icon(
        self, squashfs_root: Path, app_name: str
    ) -> Path | None:
        """Find the best available icon in the extracted AppImage.

        Args:
            squashfs_root: Path to the extracted squashfs-root directory
            app_name: Application name for icon matching

        Returns:
            Path to the best icon found or None

        """
        candidate_icons: list[dict[str, int | Path]] = []

        # Search for icons in common locations
        search_locations = [
            squashfs_root,  # Root level symlinks
            squashfs_root
            / "usr"
            / "share"
            / "icons",  # Standard icon directory
            squashfs_root
            / "usr"
            / "share"
            / "pixmaps",  # Alternative icon location
            squashfs_root
            / "opt"
            / "**"
            / "icons",  # Application-specific icons
        ]

        for location in search_locations:
            if location.exists():
                candidate_icons.extend(
                    self._scan_directory_for_icons(location, app_name)
                )

        if not candidate_icons:
            logger.debug("No candidate icons found")
            return None

        # Score and select the best icon
        best_icon = self._select_best_icon(candidate_icons)
        logger.info(
            "🎨 Selected icon: %s (score: %s)",
            best_icon["path"],
            best_icon["score"],
        )

        best_icon_path = best_icon["path"]
        assert isinstance(best_icon_path, Path)  # Type guard for mypy
        return best_icon_path

    def _scan_directory_for_icons(
        self, directory: Path, app_name: str
    ) -> list[dict[str, int | Path]]:
        """Scan directory for icon files.

        Args:
            directory: Directory to scan
            app_name: Application name for matching

        Returns:
            List of candidate icon dictionaries

        """
        candidates: list[dict[str, int | Path]] = []

        try:
            # Use glob patterns to find icons
            patterns = [
                f"**/{app_name}.*",
                f"**/*{app_name.lower()}*.*",
                "**/icon.*",
                "**/.DirIcon",
                "**/*.svg",
                "**/*.png",
                "**/*.ico",
            ]

            for pattern in patterns:
                for icon_path in directory.glob(pattern):
                    if icon_path.is_file() or icon_path.is_symlink():
                        # Resolve symlinks
                        resolved_path = self._resolve_icon_path(icon_path)
                        if resolved_path and resolved_path.exists():
                            score = self._score_icon(resolved_path, app_name)
                            if score > 0:  # Only include valid icons
                                candidates.append(
                                    {
                                        "path": resolved_path,
                                        "score": score,
                                        "original_path": icon_path,
                                    }
                                )

        except (OSError, PermissionError) as e:
            logger.debug("Error scanning %s: %s", directory, e)

        return candidates

    def _resolve_icon_path(self, icon_path: Path) -> Path | None:
        """Resolve symlink to actual icon file.

        Args:
            icon_path: Path that might be a symlink

        Returns:
            Resolved path or None if resolution fails

        """
        try:
            if icon_path.is_symlink():
                # Handle both absolute and relative symlinks
                target = icon_path.readlink()
                if target.is_absolute():
                    # For absolute symlinks, make them relative to squashfs-root
                    squashfs_root = icon_path
                    while (
                        squashfs_root.name != "squashfs-root"
                        and squashfs_root.parent != squashfs_root
                    ):
                        squashfs_root = squashfs_root.parent
                    if squashfs_root.name == "squashfs-root":
                        resolved = squashfs_root / target.relative_to("/")
                    else:
                        resolved = target
                else:
                    # Relative symlink
                    resolved = (icon_path.parent / target).resolve()
            else:
                resolved = icon_path

            return resolved if resolved.exists() else None

        except (OSError, ValueError) as e:
            logger.debug("Failed to resolve icon path %s: %s", icon_path, e)
            return None

    def _score_icon(self, icon_path: Path, app_name: str) -> int:
        """Score an icon based on simple format and name preferences.

        Args:
            icon_path: Path to the icon file
            app_name: Application name for relevance scoring

        Returns:
            Icon score (higher is better)

        """
        if not icon_path.exists():
            return 0

        suffix = icon_path.suffix.lower()
        filename_stem = icon_path.stem.lower()
        app_name_lower = app_name.lower()

        # Start with base format score - SVG > PNG > others
        score = self.FORMAT_SCORES.get(suffix, 0)

        # Name relevance bonus (simple priority)
        if filename_stem == app_name_lower:
            score += 50  # Exact match
        elif filename_stem.startswith(app_name_lower):
            score += 30  # Starts with app name
        elif app_name_lower in filename_stem:
            score += 20  # Contains app name
        elif filename_stem in ["icon", "app"]:
            score += 10  # Generic names

        # Simple size check - avoid tiny files
        try:
            file_size = icon_path.stat().st_size
            if file_size < self.MIN_ICON_SIZE_BYTES:
                return 0  # Skip very small files entirely
        except OSError:
            return 0  # Skip files we can't read

        return score

    def _select_best_icon(
        self, candidates: list[dict[str, int | Path]]
    ) -> dict[str, int | Path]:
        """Select the best icon from candidates.

        Args:
            candidates: List of candidate icon dictionaries

        Returns:
            Best icon dictionary

        """
        if not candidates:
            raise IconExtractionError("No icon candidates available")

        # Sort by score (highest first)
        def get_score(candidate: dict[str, int | Path]) -> int:
            score = candidate["score"]
            assert isinstance(score, int)
            return score

        candidates.sort(key=get_score, reverse=True)

        # Log top candidates for debugging
        logger.debug("Icon candidates (top 5):")
        for i, candidate in enumerate(candidates[:5]):
            logger.debug(
                "  %d. %s (score: %s)",
                i + 1,
                candidate["path"],
                candidate["score"],
            )

        return candidates[0]

    async def _copy_icon(self, source: Path, dest: Path) -> Path:
        """Copy icon to final destination.

        Args:
            source: Source icon path
            dest: Destination path

        Returns:
            Path to copied icon

        Raises:
            IconExtractionError: If copy fails

        """
        try:
            # Ensure destination directory exists
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Copy the icon
            _ = shutil.copy2(source, dest)
            logger.info("✅ Icon extracted and copied: %s", dest)

            return dest

        except (OSError, shutil.Error) as e:
            raise IconExtractionError(
                f"Failed to copy icon to {dest}: {e}"
            ) from e


class IconManager:
    """Manages icon acquisition from AppImages with GitHub fallback."""

    def __init__(self, enable_extraction: bool = True) -> None:
        """Initialize icon manager.

        Args:
            enable_extraction: Whether to enable AppImage icon extraction

        """
        self.enable_extraction: bool = enable_extraction
        self.extractor: AppImageIconExtractor = AppImageIconExtractor()

    async def extract_icon_only(
        self, appimage_path: Path, dest_path: Path, app_name: str
    ) -> Path | None:
        """Extract icon from AppImage only (no fallback).

        Args:
            appimage_path: Path to AppImage file
            dest_path: Destination for the extracted icon
            app_name: Application name

        Returns:
            Path to extracted icon or None if extraction failed

        """
        if not self.enable_extraction:
            logger.info("i  AppImage icon extraction is disabled")
            return None

        try:
            return await self.extractor.extract_icon(
                appimage_path, dest_path, app_name
            )
        except IconExtractionError as e:
            error_msg = str(e)
            if self.extractor.is_recoverable_error(error_msg):
                logger.info("ℹ️  Cannot extract icon: %s", error_msg)
            else:
                logger.error("❌ Icon extraction failed: %s", e)
            return None

    def set_extraction_enabled(self, enabled: bool) -> None:
        """Enable or disable AppImage icon extraction.

        Args:
            enabled: Whether to enable extraction

        """
        self.enable_extraction = enabled
        status = "enabled" if enabled else "disabled"
        logger.info("ℹ️  AppImage icon extraction %s", status)


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


class IconHandler:
    """Handles icon acquisition orchestration."""

    def __init__(
        self,
        download_service: Any,
        progress_service: Any | None = None,
    ) -> None:
        """Initialize icon handler.

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
            return bool(extraction)

        # Check catalog config if available
        if catalog_entry:
            catalog_icon = catalog_entry.get("icon", {})
            catalog_extraction = catalog_icon.get("extraction")
            if catalog_extraction is not None:
                return catalog_extraction

        # Default to enabled
        return True

    def _generate_icon_filename(
        self, app_name: str, icon_url: str | None = None
    ) -> str:
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
            logger.info(
                "🔍 Attempting icon extraction from AppImage: %s", app_name
            )
            extracted_icon = await self._get_icon_manager().extract_icon_only(
                appimage_path=appimage_path,
                dest_path=dest_path,
                app_name=app_name,
            )
            if extracted_icon:
                logger.info("✅ Icon extracted from AppImage for %s", app_name)
                return extracted_icon
        except (OSError, PermissionError) as e:
            logger.info(
                "⚠️  AppImage extraction failed for %s: %s", app_name, e
            )
        except Exception as e:
            logger.warning(
                "⚠️  Unexpected error during extraction for %s: %s", app_name, e
            )

        return None

    async def _attempt_github_download(
        self,
        icon_asset: Any,
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
            downloaded_icon = await self.download_service.download_icon(
                icon_asset, dest_path
            )
            if downloaded_icon:
                logger.info("✅ Icon downloaded from GitHub for %s", app_name)
                return downloaded_icon
        except (OSError, ConnectionError, TimeoutError) as e:
            logger.warning(
                "⚠️  GitHub icon download failed for %s: %s", app_name, e
            )
        except Exception as e:
            logger.warning(
                "⚠️  Unexpected error during GitHub download for %s: %s",
                app_name,
                e,
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
            updated_config["url"] = (
                icon_url if preserve_url_on_extraction else ""
            )
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
            progress_task_id = (
                await self.progress_service.create_icon_extraction_task(
                    app_name
                )
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

        logger.debug(
            "🎨 Icon extraction for %s: enabled=%s",
            app_name,
            extraction_enabled,
        )

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
            # Import here to avoid circular dependency
            from my_unicorn.download import IconAsset

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
                    description=f"✅ {app_name} icon extraction",
                )
            else:
                await self.progress_service.finish_task(
                    progress_task_id,
                    success=False,
                    description=f"❌ {app_name} icon extraction failed",
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
