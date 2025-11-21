"""Download service for handling AppImage and icon downloads.

This module provides a service for downloading AppImage files and associated
icons with progress tracking via the project's `ProgressDisplay` service.
"""

import asyncio
import contextlib
from pathlib import Path
from urllib.parse import urlparse

import aiohttp

from my_unicorn.auth import GitHubAuthManager
from my_unicorn.config import config_manager
from my_unicorn.github_client import Asset
from my_unicorn.logger import get_logger
from my_unicorn.progress import (
    ProgressDisplay,
    ProgressType,
    get_progress_service,
)
from my_unicorn.types import DownloadIconAsset

logger = get_logger(__name__)

# Download constants
CHUNK_SIZE = 8192
PROGRESS_MB_THRESHOLD = 0.5
CONTENT_PREVIEW_MAX = 200


class DownloadService:
    """Service for downloading AppImage files and associated assets."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        progress_service: ProgressDisplay | None = None,
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
        """Download a file from URL to destination with retry logic.

        Args:
            url: URL to download from
            dest: Destination path
            show_progress: Whether to show progress bar
            progress_type: Type of progress operation for categorization

        Raises:
            aiohttp.ClientError: If download fails after all retry attempts

        """
        # Load network configuration
        network_cfg = config_manager.load_global_config()["network"]
        retry_attempts = int(network_cfg.get("retry_attempts", 3))
        timeout_seconds = int(network_cfg.get("timeout_seconds", 10))

        # Derive timeouts from configured base seconds.
        # Keep previous defaults via multipliers.
        timeout = aiohttp.ClientTimeout(
            total=timeout_seconds * 60,
            sock_read=timeout_seconds * 3,
            sock_connect=timeout_seconds,
        )

        # Retry loop wraps entire download operation
        for attempt in range(1, retry_attempts + 1):
            try:
                # Attempt complete download (connection + all chunks)
                await self._attempt_download(
                    url, dest, show_progress, progress_type, timeout
                )

                # Success - break out of retry loop
                logger.debug("✅ Download completed: %s", dest)
                break

            except (aiohttp.ClientError, TimeoutError) as e:
                logger.warning(
                    "Attempt %s/%s failed for %s: %s",
                    attempt,
                    retry_attempts,
                    dest.name,
                    e,
                )

                # Clean up partial download if it exists
                if dest.exists():
                    logger.debug("🗑️  Removing partial download: %s", dest)
                    try:
                        dest.unlink()
                    except Exception as cleanup_error:
                        logger.warning(
                            "Failed to remove partial file: %s",
                            cleanup_error,
                        )

                if attempt == retry_attempts:
                    logger.error(
                        "❌ Download failed after %s attempts: %s - %s",
                        retry_attempts,
                        dest.name,
                        e,
                    )
                    raise

                # Exponential backoff before retrying
                backoff = 2**attempt
                logger.info("⏳ Retrying in %s seconds...", backoff)
                await asyncio.sleep(backoff)

            except Exception as e:
                # Non-retryable errors (cleanup and raise immediately)
                logger.error("❌ Download failed: %s - %s", dest.name, e)
                if dest.exists():
                    logger.debug("🗑️  Removing partial download: %s", dest)
                    with contextlib.suppress(Exception):
                        dest.unlink()
                raise

    async def _attempt_download(
        self,
        url: str,
        dest: Path,
        show_progress: bool,
        progress_type: ProgressType,
        timeout: aiohttp.ClientTimeout,
    ) -> None:
        """Perform a single download attempt without retry logic.

        Args:
            url: URL to download from
            dest: Destination path
            show_progress: Whether to show progress bar
            progress_type: Type of progress operation
            timeout: Timeout configuration

        Raises:
            aiohttp.ClientError: If HTTP request fails
            TimeoutError: If download times out
            Exception: For other download failures

        """
        headers: dict[str, str] = GitHubAuthManager.apply_auth({})

        async with self.session.get(
            url, headers=headers, timeout=timeout
        ) as response:
            _maybe = response.raise_for_status()
            if asyncio.iscoroutine(_maybe):
                await _maybe
            total = int(response.headers.get("Content-Length", 0))

            dest.parent.mkdir(parents=True, exist_ok=True)

            logger.debug("📥 Downloading %s", dest.name)
            logger.debug("   URL: %s", url)
            logger.debug(
                "   Size: %s bytes" if total > 0 else "   Size: Unknown",
                f"{total:,}" if total > 0 else "",
            )

            if (
                show_progress
                and total > 0
                and self.progress_service.is_active()
            ):
                await self._download_with_progress(
                    response,
                    dest,
                    total,
                    progress_type,
                )
            else:
                await self._download_without_progress(response, dest)

    async def _download_without_progress(
        self,
        response: aiohttp.ClientResponse,
        dest: Path,
    ) -> None:
        """Download file without progress tracking.

        Args:
            response: HTTP response to read from
            dest: Destination path for the file

        Raises:
            aiohttp.ClientError: If download fails
            TimeoutError: If download times out

        """
        with open(dest, "wb") as f:
            async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                if chunk:
                    f.write(chunk)

    async def _download_with_progress(
        self,
        response: aiohttp.ClientResponse,
        dest: Path,
        total: int,
        progress_type: ProgressType,
    ) -> None:
        """Download file with progress tracking via `ProgressDisplay`.

        Args:
            response: HTTP response to read from
            dest: Destination path for the file
            total: Total file size in bytes
            progress_type: Type of progress operation

        Raises:
            aiohttp.ClientError: If download fails
            TimeoutError: If download times out

        """
        # Create progress task with total in bytes
        task_id = await self.progress_service.add_task(
            name=dest.name,
            progress_type=progress_type,
            total=total,  # Keep in bytes for accurate calculations
        )

        success = False
        downloaded_bytes = 0

        try:
            chunk_count = 0
            last_progress_update = 0.0

            with open(dest, "wb") as f:
                async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        chunk_count += 1

                        # Update progress in bytes (throttle updates to every
                        # PROGRESS_MB_THRESHOLD MB or every 100 chunks)
                        mb_threshold_bytes = (
                            PROGRESS_MB_THRESHOLD * 1024 * 1024
                        )
                        if (
                            downloaded_bytes - last_progress_update
                            >= mb_threshold_bytes
                        ) or (chunk_count % 100 == 0):
                            await self.progress_service.update_task(
                                task_id,
                                completed=downloaded_bytes,
                            )
                            last_progress_update = downloaded_bytes

            # Always ensure final progress update with actual downloaded size
            # This handles cases where Content-Length differs from actual size
            # (e.g. due to compression)
            await self.progress_service.update_task(
                task_id, total=downloaded_bytes, completed=downloaded_bytes
            )
            success = True

        finally:
            # Mark task as finished
            description = None
            if not success:
                description = "download failed"
            await self.progress_service.finish_task(
                task_id,
                success=success,
                description=description,
            )
            # Give time for display to update
            await asyncio.sleep(0.1)

    async def download_appimage(
        self, asset: Asset, dest: Path, show_progress: bool = True
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
            asset.browser_download_url,
            dest,
            show_progress=show_progress,
            progress_type=ProgressType.DOWNLOAD,
        )
        return dest

    async def download_icon(self, icon: DownloadIconAsset, dest: Path) -> Path:
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

            logger.info(
                "✅ Icon downloaded: %s (%s bytes)", dest, f"{file_size:,}"
            )
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

        # Load network configuration
        network_cfg = config_manager.load_global_config()["network"]
        retry_attempts = int(network_cfg.get("retry_attempts", 3))
        timeout_seconds = int(network_cfg.get("timeout_seconds", 10))

        timeout = aiohttp.ClientTimeout(
            total=timeout_seconds * 60,
            sock_read=timeout_seconds * 3,
            sock_connect=timeout_seconds,
        )

        for attempt in range(1, retry_attempts + 1):
            try:
                async with self.session.get(
                    checksum_url, headers=headers, timeout=timeout
                ) as response:
                    _maybe = response.raise_for_status()
                    if asyncio.iscoroutine(_maybe):
                        await _maybe
                    content = await response.text()

                    logger.debug("📄 Checksum file downloaded successfully")
                    logger.debug("   Status: %s", response.status)
                    logger.debug(
                        "   Content length: %d characters", len(content)
                    )
                    logger.debug(
                        "   Content preview: %s%s",
                        content[:CONTENT_PREVIEW_MAX],
                        "..." if len(content) > CONTENT_PREVIEW_MAX else "",
                    )

                    return content
            except (aiohttp.ClientError, TimeoutError) as e:
                logger.warning(
                    "Attempt %s/%s failed downloading checksum %s: %s",
                    attempt,
                    retry_attempts,
                    checksum_url,
                    e,
                )
                if attempt == retry_attempts:
                    logger.error("❌ Failed to download checksum file: %s", e)
                    logger.error("   URL: %s", checksum_url)
                    raise
                await asyncio.sleep(2**attempt)
            except Exception as e:
                logger.error("❌ Failed to download checksum file: %s", e)
                logger.error("   URL: %s", checksum_url)
                raise


class DownloadError(Exception):
    """Raised when download fails."""
