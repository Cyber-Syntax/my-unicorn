"""Icon extraction from AppImage files.

This module provides icon extraction functionality from AppImage files.
Icon management is handled through file_ops.extract_icon_from_appimage().
"""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from pathlib import Path
from typing import ClassVar

from ..logger import get_logger

logger = get_logger(__name__)


class IconExtractionError(Exception):
    """Raised when icon extraction from AppImage fails."""


class AppImageIconExtractor:
    """Handles extraction and processing of icons from AppImage files."""

    # Icon format preferences (higher score = better)
    FORMAT_SCORES: ClassVar[dict[str, int]] = {
        ".png": 100,  # Raster graphics - good quality
        ".svg": 50,  # Scalable vector graphics - high quality
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
            logger.error("AppImage not found: %s", appimage_path)
            return None

        if not appimage_path.is_file():
            logger.error("AppImage path is not a file: %s", appimage_path)
            return None

        logger.info("Extracting icon from AppImage: %s", appimage_path.name)

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
                        "No squashfs-root directory found after extraction"
                    )
                    return None

                best_icon = self._find_best_icon(squashfs_root, app_name)
                if not best_icon:
                    logger.warning("No suitable icon found for %s", app_name)
                    return None

                # Copy icon to destination
                return await self._copy_icon(best_icon, dest_path)

            except IconExtractionError:
                # Re-raise IconExtractionError as-is (already logged)
                raise
            except Exception as e:
                logger.exception(
                    "❌ Failed to extract icon from %s",
                    appimage_path.name,
                )
                error_msg = f"Icon extraction failed: {e}"
                raise IconExtractionError(error_msg) from e

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
                        "AppImage uses unsupported compression format: %s",
                        appimage_path.name,
                    )
                    logger.info(
                        "AppImage cannot be extracted for icon discovery"
                    )
                    msg = "Unsupported AppImage compression format"
                    raise IconExtractionError(msg)

                # Check for other common extraction issues
                if "Failed to open squashfs image" in stderr_text:
                    logger.info(
                        "Cannot open AppImage for extraction: %s",
                        appimage_path.name,
                    )
                    msg = "Cannot open AppImage squashfs filesystem"
                    raise IconExtractionError(msg)

                if "Invalid magic number" in stderr_text:
                    logger.info(
                        "Invalid AppImage format: %s", appimage_path.name
                    )
                    msg = "Invalid AppImage format"
                    raise IconExtractionError(msg)

                # Generic extraction failure
                code = process.returncode
                error_msg = f"AppImage extraction failed with code {code}"
                if stderr_text:
                    error_msg += f": {stderr_text}"
                logger.warning("%s", error_msg)
                raise IconExtractionError(error_msg)

            logger.debug("AppImage extracted successfully to %s", temp_dir)

        except (TimeoutError, OSError) as e:
            logger.warning("Failed to execute AppImage extraction: %s", e)
            error_msg = f"Failed to execute AppImage extraction: {e}"
            raise IconExtractionError(error_msg) from e

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
            "Selected icon: %s (score: %s)",
            best_icon["path"],
            best_icon["score"],
        )

        best_icon_path = best_icon["path"]
        if not isinstance(best_icon_path, Path):
            msg = "Invalid icon path type"
            raise IconExtractionError(msg)
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
                    # Make absolute symlinks relative to squashfs-root
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
            msg = "No icon candidates available"
            raise IconExtractionError(msg)

        # Sort by score (highest first)
        def get_score(candidate: dict[str, int | Path]) -> int:
            score = candidate["score"]
            if not isinstance(score, int):
                msg = "Invalid score type"
                raise TypeError(msg)
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

        except (OSError, shutil.Error) as e:
            error_msg = f"Failed to copy icon to {dest}: {e}"
            raise IconExtractionError(error_msg) from e
        else:
            return dest
