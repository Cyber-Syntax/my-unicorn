"""Installation utilities for AppImage files.

This module handles downloading, installing, and managing AppImage files
including progress tracking, icon downloads, and file operations.
"""

import os
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

import aiohttp
from tqdm.asyncio import tqdm

from .auth import GitHubAuthManager
from .github_client import GitHubAsset
from .logger import get_logger

logger = get_logger(__name__)


class IconAsset(TypedDict):
    icon_filename: str
    icon_url: str


class Installer:
    """Handles installation of AppImage files and associated assets."""

    def __init__(
        self,
        asset: GitHubAsset,
        session: aiohttp.ClientSession,
        icon: IconAsset | None = None,
        download_dir: Path | None = None,
        install_dir: Path | None = None,
    ) -> None:
        """Initialize installer with asset and configuration.

        Args:
            asset: GitHub asset to install
            session: aiohttp session for downloads
            icon: Optional icon asset to download
            download_dir: Directory for temporary downloads
            install_dir: Directory for final installation

        """
        self.asset: GitHubAsset = asset
        self.session = session
        self.icon: IconAsset | None = icon
        self.download_dir = download_dir or Path.cwd()
        self.install_dir = install_dir or Path.cwd()

        # Extract filename from URL
        self.filename: str = Path(urlparse(asset["browser_download_url"]).path).name
        self.download_path = self.download_dir / self.filename
        self.install_path = self.install_dir / self.filename

    async def download_file(
        self, url: str, dest: Path, show_progress: bool = False, success_color: str = "green"
    ) -> None:
        """Download a file from URL to destination.

        Args:
            url: URL to download from
            dest: Destination path
            show_progress: Whether to show progress bar
            success_color: Color for successful download progress bar

        Raises:
            aiohttp.ClientError: If download fails

        """
        headers: dict[str, str] = GitHubAuthManager.apply_auth({})

        try:
            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length", 0))

                dest.parent.mkdir(parents=True, exist_ok=True)

                logger.debug(f"📥 Downloading {dest.name}")
                logger.debug(f"   URL: {url}")
                logger.debug(f"   Size: {total:,} bytes" if total > 0 else "   Size: Unknown")

                if show_progress and total > 0:
                    # Use progress context to defer logging during download
                    with logger.progress_context():
                        # Determine initial color and description based on operation type
                        if success_color == "blue":
                            initial_desc = f"📦 {dest.name}"
                            final_desc = f"✅ {dest.name}"
                        else:
                            initial_desc = f"🎨 {dest.name}"
                            final_desc = f"✅ {dest.name}"

                        with (
                            open(dest, "wb") as f,
                            tqdm(
                                total=total,
                                unit="B",
                                unit_scale=True,
                                desc=initial_desc,
                                leave=True,
                                colour=success_color,
                                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
                                ncols=100,
                            ) as pbar,
                        ):
                            try:
                                async for chunk in response.content.iter_chunked(8192):
                                    if chunk:
                                        f.write(chunk)
                                        pbar.update(len(chunk))
                                # Update to success state
                                pbar.colour = "green"
                                pbar.set_description(final_desc)
                                pbar.refresh()
                            except Exception:
                                # Update to failure state
                                pbar.colour = "red"
                                pbar.set_description(f"❌ {dest.name}")
                                pbar.refresh()
                                raise
                else:
                    with open(dest, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if chunk:
                                f.write(chunk)

                logger.debug(f"✅ Download completed: {dest}")

        except Exception as e:
            logger.error(f"❌ Download failed: {dest.name} - {e}", exc_info=True)
            raise

    async def download_appimage(self, show_progress: bool = True) -> Path:
        """Download the AppImage file.

        Args:
            show_progress: Whether to show download progress

        Returns:
            Path to downloaded AppImage

        Raises:
            aiohttp.ClientError: If download fails

        """
        await self.download_file(
            self.asset["browser_download_url"],
            self.download_path,
            show_progress=show_progress,
            success_color="blue",
        )
        return self.download_path

    async def download_icon(self, icon_dir: Path | None = None) -> Path | None:
        """Download icon if available and not already exists.

        Args:
            icon_dir: Directory to save icon (defaults to install_dir)

        Returns:
            Path to icon file or None if no icon

        """
        if not self.icon:
            return None

        icon_dir = icon_dir or self.install_dir
        icon_path = icon_dir / self.icon["icon_filename"]

        # Check if icon already exists
        if icon_path.exists():
            logger.info(f"✅ Icon already exists: {icon_path}")
            return icon_path

        try:
            await self.download_file(self.icon["icon_url"], icon_path, show_progress=False)
            logger.info(f"✅ Icon downloaded: {icon_path}")
            return icon_path
        except Exception as e:
            logger.error(f"❌ Failed to download icon: {e}", exc_info=True)
            return None

    def make_executable(self, path: Path) -> None:
        """Make file executable.

        Args:
            path: Path to file to make executable

        """
        logger.debug(f"🔧 Making executable: {path.name}")
        os.chmod(path, 0o755)
        logger.debug("✅ File permissions updated")

    def move_to_install_dir(self, source: Path) -> Path:
        """Move file from download directory to install directory.

        Args:
            source: Source file path

        Returns:
            Final installation path

        """
        if source == self.install_path:
            return self.install_path

        # Create install directory if it doesn't exist
        self.install_dir.mkdir(parents=True, exist_ok=True)

        # If target exists, remove it
        if self.install_path.exists():
            logger.debug(f"🗑️  Removing existing file: {self.install_path}")
            self.install_path.unlink()

        # Move file
        logger.debug(f"📦 Moving to install directory: {self.install_path}")
        source.rename(self.install_path)
        return self.install_path

    def rename_appimage(self, new_name: str) -> Path:
        """Rename the AppImage file to a clean name without version numbers.

        Args:
            new_name: New name for the AppImage (base name only, extension will be added)

        Returns:
            New path after rename

        """
        # Ensure proper AppImage extension
        if not new_name.lower().endswith(".appimage"):
            new_name = new_name + ".AppImage"

        new_path = self.install_dir / new_name

        logger.debug(f"🏷️  Renaming AppImage: {self.install_path.name} → {new_name}")

        if self.install_path.exists():
            # Remove target if it exists (for updates)
            if new_path.exists() and new_path != self.install_path:
                logger.debug(f"🗑️  Removing existing file: {new_path}")
                new_path.unlink()

            self.install_path.rename(new_path)
            self.install_path = new_path
            self.filename = new_name
            logger.debug(f"✅ Renamed to: {new_path}")

        return new_path

    def get_clean_appimage_name(self, rename: str) -> str:
        """Generate clean AppImage name from rename field.

        Args:
            rename: Rename value from catalog config

        Returns:
            Clean AppImage base name (without extension, rename_appimage will add it)

        """
        clean_name = rename.strip()
        # Remove any existing extensions to avoid double extensions
        if clean_name.lower().endswith((".appimage", ".AppImage")):
            clean_name = clean_name[:-9]  # Remove .AppImage or .appimage
        return clean_name

    async def install(
        self,
        show_progress: bool = True,
        make_executable: bool = True,
        move_to_install: bool = True,
        download_icon: bool = True,
        icon_dir: Path | None = None,
        rename_to: str | None = None,
    ) -> tuple[Path, Path | None]:
        """Install the AppImage and associated assets.

        Args:
            show_progress: Whether to show download progress
            make_executable: Whether to make AppImage executable
            move_to_install: Whether to move to install directory
            download_icon: Whether to download icon
            icon_dir: Directory for icon (defaults to install_dir)
            rename_to: Clean name to rename AppImage to (without version numbers)

        Returns:
            Tuple of (appimage_path, icon_path)

        """
        # Download AppImage
        appimage_path = await self.download_appimage(show_progress=show_progress)

        # Download icon if requested
        icon_path = None
        if download_icon:
            icon_path = await self.download_icon(icon_dir=icon_dir)

        # Make executable
        if make_executable:
            self.make_executable(appimage_path)

        # Move to install directory
        if move_to_install:
            appimage_path = self.move_to_install_dir(appimage_path)

        # Rename to clean name if specified
        if rename_to:
            clean_name = self.get_clean_appimage_name(rename_to)
            appimage_path = self.rename_appimage(clean_name)

        return appimage_path, icon_path

    def get_expected_size(self) -> int:
        """Get expected file size from asset.

        Returns:
            Expected file size in bytes

        """
        return self.asset.get("size", 0)

    def cleanup_download(self) -> None:
        """Clean up downloaded files in download directory."""
        if self.download_path.exists() and self.download_path != self.install_path:
            self.download_path.unlink()

    async def verify_download(self, path: Path) -> bool:
        """Verify downloaded file size matches expected.

        Args:
            path: Path to verify

        Returns:
            True if verification passes

        """
        if not path.exists():
            logger.error(f"❌ File not found for verification: {path}", exc_info=True)
            return False

        expected_size = self.get_expected_size()
        if expected_size > 0:
            actual_size = path.stat().st_size
            if actual_size == expected_size:
                logger.debug(f"✅ File size verification passed: {actual_size:,} bytes")
                return True
            else:
                logger.error(
                    f"❌ File size mismatch: expected {expected_size:,}, got {actual_size:,}",
                    exc_info=True,
                )
                return False

        logger.debug("ℹ️  No expected size available, skipping size verification")
        return True

    def create_backup(self, backup_dir: Path, version: str | None = None) -> Path | None:
        """Create backup of existing AppImage.

        Args:
            backup_dir: Directory to store backup
            version: Version string to include in backup name

        Returns:
            Path to backup file or None if no existing file

        """
        if not self.install_path.exists():
            return None

        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create backup filename
        stem = self.install_path.stem
        suffix = self.install_path.suffix
        version_str = f"-{version}" if version else ""
        backup_name = f"{stem}{version_str}.backup{suffix}"
        backup_path = backup_dir / backup_name

        # Copy file to backup location
        import shutil

        shutil.copy2(self.install_path, backup_path)

        logger.debug(f"💾 Backup created: {backup_path}")
        return backup_path


class InstallationError(Exception):
    """Raised when installation fails."""


class DownloadError(Exception):
    """Raised when download fails."""
