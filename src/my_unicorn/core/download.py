"""Download service for handling AppImage downloads.

This module provides a service for downloading AppImage files and associated
checksum files with progress tracking via the `ProgressReporter` protocol.

The service depends on the abstract `ProgressReporter` protocol rather than
concrete UI implementations, enabling testing without UI dependencies and
supporting alternative progress display backends.

File I/O is performed asynchronously using aiofiles when available, with a
fallback to synchronous I/O in a thread executor for compatibility.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import IO, TypeVar
from urllib.parse import urlparse

import aiohttp

from my_unicorn.config import ConfigManager
from my_unicorn.core.auth import GitHubAuthManager
from my_unicorn.core.github import Asset
from my_unicorn.core.protocols import (
    NullProgressReporter,
    ProgressReporter,
    ProgressType,
)
from my_unicorn.logger import get_logger

T = TypeVar("T")

logger = get_logger(__name__)

try:
    import aiofiles

    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False
    logger.debug(
        "aiofiles not available, using sync I/O fallback in thread executor"
    )

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
        progress_reporter: ProgressReporter | None = None,
        auth_manager: GitHubAuthManager | None = None,
    ) -> None:
        """Initialize download service with HTTP session.

        Args:
            session: aiohttp session for downloads
            progress_reporter: Progress reporter for tracking downloads.
                Uses NullProgressReporter if not provided.
            auth_manager: Optional GitHub authentication manager
                         (creates default if not provided)

        """
        self.session = session
        self.progress_reporter = progress_reporter or NullProgressReporter()
        self.auth_manager = auth_manager or GitHubAuthManager.create_default()

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

            # Show progress for files > 1MB when progress reporter is active
            show_progress = (
                total > MIN_SIZE_FOR_PROGRESS
                and self.progress_reporter.is_active()
            )
            if show_progress:
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

        Uses async file I/O via aiofiles when available, falling back to
        sync I/O in a thread executor for compatibility.

        Args:
            response: HTTP response to read from
            dest: Destination path for the file

        Raises:
            aiohttp.ClientError: If download fails
            TimeoutError: If download times out

        """
        if HAS_AIOFILES:
            async with aiofiles.open(dest, mode="wb") as f:
                async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                    if chunk:
                        await f.write(chunk)
        else:
            await self._download_sync_fallback(response, dest)

    async def _download_with_progress(
        self,
        response: aiohttp.ClientResponse,
        dest: Path,
        total: int,
        progress_type: ProgressType,
    ) -> None:
        """Download file with progress tracking via ProgressReporter.

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
        task_id = await self.progress_reporter.add_task(
            name=dest.name,
            progress_type=progress_type,
            total=total,  # Keep in bytes for accurate calculations
        )

        success = False
        downloaded_bytes = 0

        try:
            chunk_count = 0
            last_progress_update = 0.0

            if HAS_AIOFILES:
                async with aiofiles.open(dest, mode="wb") as f:
                    async for chunk in response.content.iter_chunked(
                        CHUNK_SIZE
                    ):
                        if chunk:
                            await f.write(chunk)
                            downloaded_bytes += len(chunk)
                            chunk_count += 1

                            mb_threshold_bytes = (
                                PROGRESS_MB_THRESHOLD * 1024 * 1024
                            )
                            if (
                                downloaded_bytes - last_progress_update
                                >= mb_threshold_bytes
                            ) or (chunk_count % 100 == 0):
                                await self.progress_reporter.update_task(
                                    task_id,
                                    completed=downloaded_bytes,
                                )
                                last_progress_update = downloaded_bytes
            else:
                downloaded_bytes = (
                    await self._download_sync_fallback_with_progress(
                        response,
                        dest,
                        task_id,
                    )
                )

            # Always ensure final progress update with actual downloaded size
            # This handles cases where Content-Length differs from actual size
            # (e.g. due to compression)
            await self.progress_reporter.update_task(
                task_id, completed=downloaded_bytes
            )
            success = True

        finally:
            # Mark task as finished
            description = None
            if not success:
                description = "download failed"
            await self.progress_reporter.finish_task(
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

    async def _download_sync_fallback(
        self,
        response: aiohttp.ClientResponse,
        dest: Path,
    ) -> None:
        """Fallback download using sync I/O in thread executor.

        Used when aiofiles is not available. Runs blocking file writes
        in a thread executor to avoid blocking the event loop.

        Args:
            response: HTTP response to read from
            dest: Destination path for the file

        """
        loop = asyncio.get_running_loop()

        def write_chunk(f: IO[bytes], chunk: bytes) -> None:
            f.write(chunk)

        with dest.open("wb") as f:
            async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                if chunk:
                    await loop.run_in_executor(None, write_chunk, f, chunk)

    async def _download_sync_fallback_with_progress(
        self,
        response: aiohttp.ClientResponse,
        dest: Path,
        task_id: str,
    ) -> int:
        """Fallback download with progress using sync I/O in thread executor.

        Args:
            response: HTTP response to read from
            dest: Destination path for the file
            task_id: Progress task ID for updates

        Returns:
            Total bytes downloaded

        """
        loop = asyncio.get_running_loop()
        downloaded_bytes = 0
        chunk_count = 0
        last_progress_update = 0.0

        def write_chunk(f: IO[bytes], chunk: bytes) -> None:
            f.write(chunk)

        with dest.open("wb") as f:
            async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                if chunk:
                    await loop.run_in_executor(None, write_chunk, f, chunk)
                    downloaded_bytes += len(chunk)
                    chunk_count += 1

                    mb_threshold_bytes = PROGRESS_MB_THRESHOLD * 1024 * 1024
                    if (
                        downloaded_bytes - last_progress_update
                        >= mb_threshold_bytes
                    ) or (chunk_count % 100 == 0):
                        await self.progress_reporter.update_task(
                            task_id,
                            completed=downloaded_bytes,
                        )
                        last_progress_update = downloaded_bytes

        return downloaded_bytes

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
        config = ConfigManager()
        network_cfg = config.load_global_config()["network"]
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
        headers = self.auth_manager.apply_auth({})

        for attempt in range(1, retry_attempts + 1):
            try:
                async with self.session.get(
                    url, headers=headers, timeout=timeout
                ) as response:
                    response.raise_for_status()
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
