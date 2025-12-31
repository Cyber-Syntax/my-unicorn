"""Download service for handling AppImage downloads.

This module provides a service for downloading AppImage files and associated
checksum files with progress tracking via the project's `ProgressDisplay` service.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar
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

T = TypeVar("T")

logger = get_logger(__name__)

# Download constants
CHUNK_SIZE = 8192
PROGRESS_MB_THRESHOLD = 0.5
CONTENT_PREVIEW_MAX = 200
MIN_SIZE_FOR_PROGRESS = 1_048_576  # 1MB threshold for showing progress bars


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
        progress_type: ProgressType = ProgressType.DOWNLOAD,
    ) -> None:
        """Download a file from URL to destination with retry logic.

        Args:
            url: URL to download from
            dest: Destination path
            progress_type: Type of progress operation for categorization

        Raises:
            aiohttp.ClientError: If download fails after all retry attempts

        """

        def cleanup() -> None:
            if dest.exists():
                logger.debug("Removing partial download: %s", dest)
                with contextlib.suppress(Exception):
                    dest.unlink()

        async def process(response: aiohttp.ClientResponse) -> None:
            total = int(response.headers.get("Content-Length", 0))
            dest.parent.mkdir(parents=True, exist_ok=True)

            logger.debug("Downloading file: %s", dest.name)
            logger.debug("   URL: %s", url)
            logger.debug(
                "   Size: %s bytes" if total > 0 else "   Size: Unknown",
                f"{total:,}" if total > 0 else "",
            )

            # Show progress for files > 1MB when progress service is active
            if (
                total > MIN_SIZE_FOR_PROGRESS
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

            logger.debug("Download completed: %s", dest)

        await self._make_request_with_retry(
            url, process, dest.name, cleanup_callback=cleanup
        )

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

    async def download_appimage(self, asset: Asset, dest: Path) -> Path:
        """Download an AppImage file.

        Args:
            asset: GitHub asset containing download information
            dest: Destination path for the AppImage

        Returns:
            Path to downloaded AppImage

        Raises:
            aiohttp.ClientError: If download fails

        """
        await self.download_file(
            asset.browser_download_url,
            dest,
            progress_type=ProgressType.DOWNLOAD,
        )
        return dest

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

        async def process(response: aiohttp.ClientResponse) -> str:
            content = await response.text()
            logger.debug("Checksum file downloaded successfully")
            logger.debug("   Status: %s", response.status)
            logger.debug("   Content length: %d characters", len(content))
            logger.debug(
                "   Content preview: %s%s",
                content[:CONTENT_PREVIEW_MAX],
                "..." if len(content) > CONTENT_PREVIEW_MAX else "",
            )
            return content

        return await self._make_request_with_retry(
            checksum_url, process, f"checksum file {checksum_url}"
        )

    def _get_network_config(self) -> tuple[int, aiohttp.ClientTimeout]:
        """Get network configuration (retries and timeout)."""
        network_cfg = config_manager.load_global_config()["network"]
        retry_attempts = int(network_cfg.get("retry_attempts", 3))
        timeout_seconds = int(network_cfg.get("timeout_seconds", 10))

        timeout = aiohttp.ClientTimeout(
            total=timeout_seconds * 60,
            sock_read=timeout_seconds * 3,
            sock_connect=timeout_seconds,
        )
        return retry_attempts, timeout

    async def _make_request_with_retry(
        self,
        url: str,
        process_callback: Callable[[aiohttp.ClientResponse], Awaitable[T]],
        description: str,
        cleanup_callback: Callable[[], None] | None = None,
    ) -> T:
        """Make HTTP request with retry logic."""
        retry_attempts, timeout = self._get_network_config()
        headers = GitHubAuthManager.apply_auth({})

        for attempt in range(1, retry_attempts + 1):
            try:
                async with self.session.get(
                    url, headers=headers, timeout=timeout
                ) as response:
                    _maybe = response.raise_for_status()
                    if asyncio.iscoroutine(_maybe):
                        await _maybe
                    return await process_callback(response)

            except (aiohttp.ClientError, TimeoutError) as e:
                logger.warning(
                    "Attempt %s/%s failed for %s: %s",
                    attempt,
                    retry_attempts,
                    description,
                    e,
                )

                if cleanup_callback:
                    cleanup_callback()

                if attempt == retry_attempts:
                    logger.exception(
                        "❌ %s failed after %s attempts",
                        description,
                        retry_attempts,
                    )
                    msg = f"Failed to download {description}"
                    raise DownloadError(msg) from e

                backoff = 2**attempt
                logger.info("Retrying in %s seconds...", backoff)
                await asyncio.sleep(backoff)
            except Exception as e:
                logger.exception("%s failed", description)
                if cleanup_callback:
                    cleanup_callback()
                msg = f"Failed to download {description}"
                raise DownloadError(msg) from e

        msg = f"Failed to download {description}"
        raise DownloadError(msg)


class DownloadError(Exception):
    """Raised when download fails."""
