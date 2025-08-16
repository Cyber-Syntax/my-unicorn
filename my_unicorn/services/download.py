"""Download service for handling AppImage and icon downloads.

This module provides a service for downloading AppImage files and associated
icons with progress tracking and basic verification.
"""

from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

import aiohttp
from tqdm.asyncio import tqdm

from ..auth import GitHubAuthManager
from ..github_client import GitHubAsset
from ..logger import get_logger

logger = get_logger(__name__)


class IconAsset(TypedDict):
    """Type definition for icon asset information."""

    icon_filename: str
    icon_url: str


class DownloadService:
    """Service for downloading AppImage files and associated assets."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize download service with HTTP session.

        Args:
            session: aiohttp session for downloads

        """
        self.session = session

    async def download_file(
        self,
        url: str,
        dest: Path,
        show_progress: bool = False,
        success_color: str = "green",
        description_prefix: str = "📥",
    ) -> None:
        """Download a file from URL to destination.

        Args:
            url: URL to download from
            dest: Destination path
            show_progress: Whether to show progress bar
            success_color: Color for successful download progress bar
            description_prefix: Prefix for progress description

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
                    await self._download_with_progress(
                        response, dest, total, success_color, description_prefix
                    )
                else:
                    await self._download_without_progress(response, dest)

                logger.debug(f"✅ Download completed: {dest}")

        except Exception as e:
            logger.error(f"❌ Download failed: {dest.name} - {e}")
            raise

    async def _download_with_progress(
        self,
        response: aiohttp.ClientResponse,
        dest: Path,
        total: int,
        success_color: str,
        description_prefix: str,
    ) -> None:
        """Download file with progress bar."""
        with logger.progress_context():
            # Determine descriptions based on operation type
            if success_color == "blue":
                initial_desc = f"📦 {dest.name}"
                final_desc = f"✅ {dest.name}"
            else:
                initial_desc = f"{description_prefix} {dest.name}"
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

    async def _download_without_progress(
        self, response: aiohttp.ClientResponse, dest: Path
    ) -> None:
        """Download file without progress bar."""
        with open(dest, "wb") as f:
            async for chunk in response.content.iter_chunked(8192):
                if chunk:
                    f.write(chunk)

    async def download_appimage(
        self, asset: GitHubAsset, dest: Path, show_progress: bool = True
    ) -> Path:
        """Download an AppImage file.

        Args:
            asset: GitHub asset containing download information
            dest: Destination path for the AppImage
            show_progress: Whether to show download progress

        Returns:
            Path to downloaded AppImage

        Raises:
            aiohttp.ClientError: If download fails

        """
        await self.download_file(
            asset["browser_download_url"],
            dest,
            show_progress=show_progress,
            success_color="blue",
            description_prefix="📦",
        )
        return dest

    async def download_icon(self, icon: IconAsset, dest: Path) -> Path:
        """Download an icon file.

        Args:
            icon: Icon asset information
            dest: Destination path for the icon

        Returns:
            Path to downloaded icon

        Raises:
            aiohttp.ClientError: If download fails

        """
        # Check if icon already exists
        if dest.exists():
            logger.info(f"✅ Icon already exists: {dest}")
            return dest

        try:
            await self.download_file(
                icon["icon_url"], dest, show_progress=False, description_prefix="🎨"
            )
            logger.info(f"✅ Icon downloaded: {dest}")
            return dest
        except Exception as e:
            logger.error(f"❌ Failed to download icon: {e}")
            raise

    def verify_file_size(self, path: Path, expected_size: int) -> bool:
        """Verify downloaded file size matches expected.

        Args:
            path: Path to verify
            expected_size: Expected file size in bytes

        Returns:
            True if verification passes

        """
        if not path.exists():
            logger.error(f"❌ File not found for verification: {path}")
            return False

        if expected_size <= 0:
            logger.debug("ℹ️  No expected size available, skipping size verification")
            return True

        actual_size = path.stat().st_size
        if actual_size == expected_size:
            logger.debug(f"✅ File size verification passed: {actual_size:,} bytes")
            return True
        else:
            logger.error(
                f"❌ File size mismatch: expected {expected_size:,}, got {actual_size:,}"
            )
            return False

    def get_filename_from_url(self, url: str) -> str:
        """Extract filename from URL.

        Args:
            url: Download URL

        Returns:
            Extracted filename

        """
        return Path(urlparse(url).path).name


class DownloadError(Exception):
    """Raised when download fails."""
