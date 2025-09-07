"""Download service for handling AppImage and icon downloads.

This module provides a service for downloading AppImage files and associated
icons with progress tracking using the Rich library.
"""

import asyncio
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

import aiohttp

from my_unicorn.auth import GitHubAuthManager
from my_unicorn.github_client import GitHubAsset
from my_unicorn.logger import get_logger
from my_unicorn.services.progress import ProgressService, ProgressType, get_progress_service

logger = get_logger(__name__)


class IconAsset(TypedDict):
    """Type definition for icon asset information."""

    icon_filename: str
    icon_url: str


class DownloadService:
    """Service for downloading AppImage files and associated assets."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        progress_service: ProgressService | None = None,
    ) -> None:
        """Initialize download service with HTTP session.

        Args:
            session: aiohttp session for downloads
            progress_service: Optional progress service for tracking downloads

        """
        self.session = session
        self.progress_service = progress_service or get_progress_service()

    async def download_file(
        self,
        url: str,
        dest: Path,
        show_progress: bool = False,
        progress_type: ProgressType = ProgressType.DOWNLOAD,
    ) -> None:
        """Download a file from URL to destination.

        Args:
            url: URL to download from
            dest: Destination path
            show_progress: Whether to show progress bar
            progress_type: Type of progress operation for categorization

        Raises:
            aiohttp.ClientError: If download fails

        """
        headers: dict[str, str] = GitHubAuthManager.apply_auth({})

        # Set timeout for downloads (30 seconds per chunk, 10 minutes total)
        timeout = aiohttp.ClientTimeout(total=600, sock_read=30)

        try:
            async with self.session.get(url, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length", 0))

                dest.parent.mkdir(parents=True, exist_ok=True)

                logger.debug("📥 Downloading %s", dest.name)
                logger.debug("   URL: %s", url)
                logger.debug(
                    "   Size: %s bytes" if total > 0 else "   Size: Unknown",
                    f"{total:,}" if total > 0 else "",
                )

                if show_progress and total > 0 and self.progress_service.is_active():
                    await self._download_with_progress(
                        response,
                        dest,
                        total,
                        progress_type,
                    )
                else:
                    # Download without progress bar
                    with open(dest, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if chunk:
                                f.write(chunk)

                logger.debug("✅ Download completed: %s", dest)

        except Exception as e:
            logger.error("❌ Download failed: %s - %s", dest.name, e)
            raise

    async def _download_with_progress(
        self,
        response: aiohttp.ClientResponse,
        dest: Path,
        total: int,
        progress_type: ProgressType,
    ) -> None:
        """Download file with Rich progress tracking.

        Args:
            response: HTTP response to read from
            dest: Destination path for the file
            total: Total file size in bytes
            progress_type: Type of progress operation

        """
        # Convert bytes to MB for display
        total_mb = total / (1024 * 1024)

        # Create progress task
        task_id = await self.progress_service.add_task(
            name=dest.name,
            progress_type=progress_type,
            total=total_mb,
        )

        success = False
        try:
            downloaded_bytes = 0

            chunk_count = 0
            last_progress_update = 0.0

            with open(dest, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        chunk_count += 1

                        # Update progress in MB (throttle updates to every 0.5 MB or every 100 chunks)
                        downloaded_mb = downloaded_bytes / (1024 * 1024)
                        if (downloaded_mb - last_progress_update >= 0.5) or (
                            chunk_count % 100 == 0
                        ):
                            await self.progress_service.update_task(
                                task_id,
                                completed=downloaded_mb,
                            )
                            last_progress_update = downloaded_mb

            # Always ensure final progress update with actual downloaded size
            final_mb = downloaded_bytes / (1024 * 1024)

            # Update the task total and completion to match actual download size
            # This handles cases where Content-Length differs from actual size due to compression, etc.
            await self.progress_service.update_task_total(
                task_id, new_total=final_mb, completed=final_mb
            )
            success = True

        except TimeoutError:
            logger.error("❌ Download timed out: %s", dest.name)
            raise Exception(f"Download timed out: {dest.name}")
        except aiohttp.ClientError as e:
            logger.error("❌ Network error during download: %s - %s", dest.name, e)
            raise Exception(f"Network error: {e}")
        except Exception as e:
            logger.error("❌ Download failed during progress tracking: %s", e)
            raise
        finally:
            # Mark task as finished with the actual final total for accurate percentage display
            final_mb = downloaded_bytes / (1024 * 1024) if success else 0.0
            await self.progress_service.finish_task(
                task_id,
                success=success,
                final_total=final_mb if success else None,
            )
            # Give Rich time to properly update the display and prevent race conditions
            await asyncio.sleep(0.2)

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
            progress_type=ProgressType.DOWNLOAD,
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
            logger.info("✅ Icon already exists: %s", dest)
            return dest

        try:
            await self.download_file(
                icon["icon_url"],
                dest,
                show_progress=False,  # Icons are usually small
                progress_type=ProgressType.DOWNLOAD,
            )

            # Verify the file was actually created and has content
            if not dest.exists():
                raise Exception(f"Downloaded file does not exist: {dest}")

            file_size = dest.stat().st_size
            if file_size == 0:
                raise Exception(f"Downloaded file is empty: {dest}")

            logger.info("✅ Icon downloaded: %s (%s bytes)", dest, f"{file_size:,}")
            return dest
        except Exception as e:
            logger.error("❌ Failed to download icon: %s", e)
            raise
   
    def get_filename_from_url(self, url: str) -> str:
        """Extract filename from URL.

        Args:
            url: Download URL

        Returns:
            Extracted filename

        """
        return Path(urlparse(url).path).name

    async def download_checksum_file(self, checksum_url: str) -> str:
        """Download checksum file content.

        Args:
            checksum_url: URL to the checksum file

        Returns:
            Content of the checksum file

        Raises:
            aiohttp.ClientError: If download fails

        """
        headers = GitHubAuthManager.apply_auth({})

        try:
            async with self.session.get(checksum_url, headers=headers) as response:
                response.raise_for_status()
                content = await response.text()

                logger.debug("📄 Checksum file downloaded successfully")
                logger.debug("   Status: %s", response.status)
                logger.debug("   Content length: %d characters", len(content))
                logger.debug(
                    "   Content preview: %s%s",
                    content[:200],
                    "..." if len(content) > 200 else "",
                )

                return content

        except Exception as e:
            logger.error("❌ Failed to download checksum file: %s", e)
            logger.error("   URL: %s", checksum_url)
            raise


class DownloadError(Exception):
    """Raised when download fails."""
