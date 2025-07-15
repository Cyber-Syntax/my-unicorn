"""Download manager for AppImages from GitHub releases.

This module provides the DownloadManager class that handles downloading AppImages
from GitHub releases with progress tracking, file verification, and concurrent
download support.
"""

import asyncio
import logging
import os
import tempfile
import threading  # Added for cancel_event
import time
from typing import ClassVar

import requests

from .api import GitHubAPI
from .global_config import GlobalConfigManager
from .progress import AppImageProgressMeter

logger = logging.getLogger(__name__)


# Custom exception for download cancellation
class DownloadCancelledError(Exception):
    """Custom exception for when a download is cancelled."""


class DownloadManager:
    """Manages the download of AppImages from GitHub releases.

    Attributes:
        github_api: The GitHub API object containing release information
        logger: Logger for this class
        is_async_mode: Whether the download is happening in an async context
        app_index: Index of the app in a multi-app update (1-based)
        total_apps: Total number of apps being updated
        cancel_event: Optional threading.Event to signal download cancellation.

    """

    # Class variables for shared progress tracking
    _global_progress: ClassVar[AppImageProgressMeter | None] = None
    _active_downloads: ClassVar[set[str]] = set()
    _active_tasks: ClassVar[set[str]] = set()  # Changed to str for download IDs

    # Use GlobalConfigManager for configuration
    _global_config: ClassVar[GlobalConfigManager | None] = None

    # Class-level file locks to prevent concurrent access to same files
    _file_locks: ClassVar[dict[str, threading.Lock]] = {}
    _locks_lock = threading.Lock()  # Protects the _file_locks dictionary

    def __init__(
        self,
        github_api: "GitHubAPI",
        app_index: int = 0,
        total_apps: int = 0,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Initialize the download manager with GitHub API instance.

        Args:
            github_api: GitHub API instance containing release information
            app_index: Index of the app in a multi-app update (1-based)
            total_apps: Total number of apps being updated
            cancel_event: Optional threading.Event to signal download cancellation.

        """
        self.github_api = github_api
        self.app_index = app_index
        self.total_apps = total_apps
        self.cancel_event = cancel_event

        # Initialize global config if not already set
        if DownloadManager._global_config is None:
            DownloadManager._global_config = GlobalConfigManager()
            DownloadManager._global_config.load_config()

        # Detect if we're in an async context
        self.is_async_mode = self._detect_async_mode()

        # Store task ID for this download instance
        self._progress_task_id: str | None = None

    def _detect_async_mode(self) -> bool:
        """Detect if we're running in an async context.

        Returns:
            bool: True if running in an async context

        """
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    @classmethod
    def get_downloads_dir(cls) -> str:
        """Get the path to the downloads directory, ensuring it exists.

        Returns:
            str: Path to the downloads directory

        """
        # Initialize global config if not already set
        if cls._global_config is None:
            cls._global_config = GlobalConfigManager()
            cls._global_config.load_config()

        # Use the app_download_path from GlobalConfigManager
        downloads_dir = cls._global_config.expanded_app_download_path
        os.makedirs(downloads_dir, exist_ok=True)
        return downloads_dir

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            str: Formatted size string (e.g., '10.5 MB')

        """
        if size_bytes <= 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(size_bytes)

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return (
            f"{size:.1f} {units[unit_index]}"
            if unit_index > 0
            else f"{int(size)} {units[unit_index]}"
        )

    @classmethod
    def get_or_create_progress(cls, total_downloads: int = 0) -> AppImageProgressMeter:
        """Get or create a shared progress instance for all downloads.

        Args:
            total_downloads: Expected number of downloads (for initialization)

        Returns:
            AppImageProgressMeter: The shared progress instance

        """
        if cls._global_progress is None:
            cls._global_progress = AppImageProgressMeter()
            cls._active_downloads = set()

        # Always start the progress display if total_downloads is provided
        if total_downloads > 0 and not cls._global_progress.active:
            cls._global_progress.start(total_downloads)

        return cls._global_progress

    @classmethod
    def stop_progress(cls) -> None:
        """Stop and clear the shared progress instance."""
        if cls._global_progress is not None:
            try:
                cls._global_progress.stop()
            except Exception as e:
                logger.error("Error stopping progress display: %s", e)
            finally:
                cls._global_progress = None
                cls._active_tasks.clear()
                cls._active_downloads.clear()

    def download(self) -> tuple[str, bool]:
        """Download the AppImage from the GitHub release or return existing file.

        Returns:
            tuple: (file_path, was_existing_file) where was_existing_file is True if
                   file already existed, False if newly downloaded

        Raises:
            ValueError: If AppImage URL or name is not available
            RuntimeError: For network errors, file system errors, or other unexpected issues

        """
        app_download_url = self.github_api.app_download_url
        appimage_name = self.github_api.appimage_name

        if not app_download_url or not appimage_name:
            logger.error("AppImage URL or name is not available. Cannot download.")
            raise ValueError("AppImage URL or name is not available. Cannot download.")

        downloads_dir = self.get_downloads_dir()
        existing_file_path = os.path.join(downloads_dir, appimage_name)

        # Get or create a lock for this specific file
        file_lock = self.get_file_lock(existing_file_path)

        # Use class-level locking to prevent concurrent operations on same file
        with file_lock:
            # Check if file exists
            if os.path.exists(existing_file_path):
                # Verify the existing file is complete
                if self._verify_existing_file(existing_file_path):
                    logger.info("File already exists and verified: %s", appimage_name)
                    print(f"Found existing file: {appimage_name}")
                    return existing_file_path, True
                else:
                    # Remove corrupted/incomplete file
                    logger.info("Removing corrupted existing file: %s", appimage_name)
                    try:
                        os.remove(existing_file_path)
                    except OSError as e:
                        logger.warning(
                            "Could not remove corrupted file %s: %s", existing_file_path, e
                        )

            # Download the file with progress tracking
            try:
                return self._download_with_progress_tracking(
                    app_download_url, appimage_name, existing_file_path
                )
            except Exception as e:
                logger.error("Error downloading %s: %s", appimage_name, e)
                raise RuntimeError("Error downloading %s: %s" % (appimage_name, e)) from e

    def _get_file_size(self, url: str, headers: dict[str, str]) -> int:
        """Get the file size by making a HEAD request.

        Args:
            url: URL to check
            headers: HTTP headers for the request

        Returns:
            int: File size in bytes

        Raises:
            requests.exceptions.RequestException: For network errors

        """
        logger.info("Fetching headers for %s", url)
        response = requests.head(url, allow_redirects=True, timeout=10, headers=headers)
        response.raise_for_status()
        return int(response.headers.get("content-length", 0))

    def _setup_progress_task(self, filename: str, total_size: int, prefix: str) -> str | None:
        """Set up a progress tracking task.

        Args:
            filename: Name of the file being downloaded
            total_size: Total size in bytes
            prefix: Prefix for the progress message

        Returns:
            Optional[str]: ID of the progress task, or None if setup failed

        """
        progress = self.get_or_create_progress()

        try:
            # Create a unique download ID
            download_id = f"download_{abs(hash(filename))}"

            # Add download to progress manager
            progress.add_download(download_id, filename, total_size, prefix)

            # Track this download
            self._progress_task_id = download_id
            DownloadManager._active_tasks.add(download_id)
            return download_id

        except Exception as e:
            logger.error("Error creating progress task: %s", e)
            # Fallback to console output without progress bar
            print(f"{prefix}Downloading {filename}...")
            return None

    def _cleanup_progress_task(self) -> None:
        """Clean up progress tracking task, ignoring any errors."""
        if not hasattr(self, "_progress_task_id") or self._progress_task_id is None:
            return

        # Get the progress instance directly to ensure we use the same one
        progress = self.get_or_create_progress()

        if self._progress_task_id in DownloadManager._active_tasks:
            DownloadManager._active_tasks.remove(self._progress_task_id)

        # Complete the download task in the progress manager
        progress.complete_download(self._progress_task_id, success=True)

        self._progress_task_id = None

    def _perform_download(
        self,
        url: str,
        file_path: str,
        headers: dict[str, str],
        task_id: str | None,
        total_size: int,
    ) -> float:
        """Perform the actual file download with progress updates.

        Args:
            url: URL to download from
            file_path: Path to save the file to
            headers: HTTP headers for the request
            task_id: Progress task ID
            total_size: Total file size in bytes

        Returns:
            float: Download time in seconds

        Raises:
            requests.exceptions.RequestException: For network errors

        """
        start_time = time.time()
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()

        # Download with progress tracking
        downloaded_size = 0
        chunk_size = 1024 * 1024  # 1MB per chunk
        progress = self.get_or_create_progress()  # Use instance method to get progress

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "wb") as f:
            # Process each chunk from the response
            for chunk in response.iter_content(chunk_size=chunk_size):
                if self.cancel_event and self.cancel_event.is_set():
                    logger.info(
                        "Download of %s cancelled by user.", os.path.basename(file_path)
                    )
                    # response.close() # Ensure connection is closed
                    # f.close() # Ensure file is closed before attempting to remove
                    # No, file is closed by with statement exit.
                    # We need to ensure the file is closed before removing.
                    # The 'with open' handles closing on break/return/exception.
                    raise DownloadCancelledError(
                        f"Download of {os.path.basename(file_path)} cancelled."
                    )

                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)

                    # Always update progress if we have a task_id
                    if task_id is not None:
                        # Update progress using the progress manager's API
                        progress.update_progress(task_id, downloaded_size)

        # Make the AppImage executable only if download wasn't cancelled
        # (If cancelled, this part is skipped due to exception)
        os.chmod(file_path, os.stat(file_path).st_mode | 0o111)

        # Final update to mark task as completed
        if task_id is not None:
            progress.update_progress(task_id, total_size)

        return time.time() - start_time

    def _display_completion_stats(
        self, filename: str, total_size: int, download_time: float, prefix: str
    ) -> None:
        """Calculate and display download completion statistics.

        Args:
            filename: Name of the downloaded file
            total_size: Size in bytes
            download_time: Time taken to download in seconds
            prefix: Message prefix

        """
        speed_mbps = (total_size / (1024 * 1024)) / download_time if download_time > 0 else 0

        print(
            f"{prefix}✓ Downloaded {filename} "
            f"({self._format_size(total_size)}, {speed_mbps:.1f} MB/s)"
        )

    def verify_download(self, downloaded_file: str) -> bool:
        """Verify the downloaded file using checksums.

        This method uses the appropriate checksum verification strategy based on
        the application's configuration, including special handling for apps
        that store checksums in GitHub release descriptions.

        Args:
            downloaded_file: Path to the downloaded file to verify

        Returns:
            bool: True if verification passed or skipped, False otherwise

        """
        logger.info("Verifying download integrity...")

        # Skip verification if hash verification is disabled
        if self.github_api.skip_verification or not self.github_api.checksum_file_name:
            logger.info(
                "Skipping verification as requested (verification disabled or no hash provided)"
            )
            return True

        from my_unicorn.verify import (
            VerificationManager,  # Import once at the top of the relevant scope
        )

        # Handle "extracted_checksum" (which now implies hash might be directly available)
        # or other standard SHA file scenarios.
        # VerificationManager will internally decide whether to use direct_expected_hash
        # or fall back to legacy "extracted_checksum" logic, or parse a SHA file.

        direct_hash_to_pass: str | None = None
        checksum_file_name_to_pass: str | None = self.github_api.checksum_file_name
        checksum_file_download_url_to_pass: str | None = (
            self.github_api.checksum_file_download_url
        )

        if self.github_api.checksum_file_name == "extracted_checksum":
            logger.info(
                "Processing 'extracted_checksum' for %s.", self.github_api.appimage_name
            )
            # SHAManager should have set extracted_hash_from_body if it successfully parsed one.
            # It also sets checksum_hash_type to "sha256".
            direct_hash_to_pass = self.github_api.extracted_hash_from_body
            if direct_hash_to_pass:
                logger.info(
                    "Direct hash found for 'extracted_checksum', will pass to VerificationManager."
                )
                # checksum_file_download_url is not needed if direct_hash is used by VerificationManager's "extracted_checksum" path
                checksum_file_download_url_to_pass = None
            else:
                # If no direct hash, VerificationManager's "extracted_checksum" will use its legacy path
                logger.info(
                    "No direct hash for 'extracted_checksum', VerificationManager will use legacy path."
                )

        # For all other cases (actual SHA file names), direct_hash_to_pass remains None.
        # VerificationManager will download and parse the checksum_file_name file.

        logger.info(
            "Instantiating VerificationManager for %s with: "
            "checksum_file_name='%s', checksum_hash_type='%s', "
            "direct_hash_provided=%s",
            self.github_api.appimage_name,
            checksum_file_name_to_pass,
            self.github_api.checksum_hash_type,
            direct_hash_to_pass is not None,
        )

        verifier = VerificationManager(
            checksum_file_name=checksum_file_name_to_pass,
            checksum_file_download_url=checksum_file_download_url_to_pass,
            appimage_name=self.github_api.appimage_name,
            appimage_path=downloaded_file,
            checksum_hash_type=self.github_api.checksum_hash_type
            if self.github_api.checksum_hash_type is not None
            else "sha256",
            direct_expected_hash=direct_hash_to_pass,
            asset_digest=self.github_api.asset_digest,
        )
        return verifier.verify_appimage(cleanup_on_failure=True)

    @classmethod
    def get_file_lock(cls, file_path: str) -> threading.Lock:
        """Get or create a file-specific lock to prevent concurrent downloads.

        Args:
            file_path: Path to the file

        Returns:
            A threading.Lock for the specified file

        """
        with cls._locks_lock:
            if file_path not in cls._file_locks:
                cls._file_locks[file_path] = threading.Lock()
            return cls._file_locks[file_path]

    def _verify_existing_file(self, file_path: str) -> bool:
        """Verify that an existing file is complete and valid.

        Args:
            file_path: Path to the file to verify

        Returns:
            True if the file appears to be complete, False otherwise

        """
        try:
            # Check if file exists and has reasonable size
            if not os.path.exists(file_path):
                return False

            stat_info = os.stat(file_path)
            file_size = stat_info.st_size

            # File should be at least 1KB for an AppImage (allow smaller files for testing)
            if file_size < 1024:
                logger.warning("File %s is too small (%s bytes)", file_path, file_size)
                return False

            # Try to get expected file size from server if possible
            try:
                expected_size = self._get_expected_file_size()
                if (
                    expected_size > 0 and abs(file_size - expected_size) > 1024
                ):  # Allow 1KB tolerance
                    logger.warning(
                        "File size mismatch: expected %s, got %s", expected_size, file_size
                    )
                    return False
            except Exception:
                # If we can't get expected size, just check basic validity
                pass

            return True

        except Exception as e:
            logger.error("Error verifying existing file %s: %s", file_path, e)
            return False

    def _get_expected_file_size(self) -> int:
        """Get the expected file size from the server.

        Returns:
            Expected file size in bytes, or 0 if unknown

        """
        try:
            headers = {"User-Agent": "AppImage-Updater/1.0"}
            response = requests.head(
                self.github_api.app_download_url,
                allow_redirects=True,
                timeout=10,
                headers=headers,
            )
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")
            if content_length:
                return int(content_length)

        except Exception as e:
            logger.debug("Could not get expected file size: %s", e)

        return 0

    def _download_with_progress_tracking(
        self, url: str, filename: str, final_path: str
    ) -> tuple[str, bool]:
        """Download file with progress tracking using the new progress manager.

        Args:
            url: URL to download from
            filename: Name of the file being downloaded
            final_path: Final path where the file should be placed

        Returns:
            tuple of (file_path, was_existing_file)

        """
        downloads_dir = os.path.dirname(final_path)

        # Create temporary file in the same directory
        with tempfile.NamedTemporaryFile(
            dir=downloads_dir, prefix=f".{filename}.", suffix=".tmp", delete=False
        ) as temp_file:
            temp_path = temp_file.name

        try:
            # Set up request headers
            headers = {
                "User-Agent": "AppImage-Updater/1.0",
                "Accept": "application/octet-stream",
            }

            # Create a progress prefix if this is part of a multi-app update
            prefix = f"[{self.app_index}/{self.total_apps}] " if self.total_apps > 0 else ""

            # Get progress manager and set up download tracking
            progress = self.get_or_create_progress()
            download_id = self._get_download_id(final_path)

            # Add to active downloads tracking
            with self._locks_lock:
                self._active_downloads.add(download_id)

            # Start the download with progress tracking
            self._download_with_progress(
                url, temp_path, filename, headers, prefix, download_id, progress
            )

            # Make the AppImage executable
            os.chmod(temp_path, os.stat(temp_path).st_mode | 0o111)

            # Atomically move the completed file to its final location
            os.rename(temp_path, final_path)

            logger.info("Successfully downloaded %s to %s", filename, final_path)
            return final_path, False

        except Exception as e:
            # Clean up temporary file on error
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            # Mark download as failed in progress manager
            if "progress" in locals() and "download_id" in locals():
                progress.complete_download(download_id, success=False, error_msg=str(e))
            raise e
        finally:
            # Remove from active downloads tracking
            with self._locks_lock:
                if "download_id" in locals():
                    self._active_downloads.discard(download_id)

    def _download_with_progress(
        self,
        url: str,
        file_path: str,
        filename: str,
        headers: dict,
        prefix: str,
        download_id: str,
        progress: AppImageProgressMeter,
    ) -> None:
        """Download a file with progress tracking.

        Args:
            url: URL to download from
            file_path: Path where to save the file
            filename: Display name for progress
            headers: HTTP headers
            prefix: Progress display prefix
            download_id: Unique download identifier
            progress: Progress manager instance

        """
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()

        total_size = int(response.headers.get("Content-Length", 0))

        # Add download to progress manager
        progress.add_download(download_id, filename, total_size, prefix)

        downloaded = 0

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Update progress
                    progress.update_progress(download_id, downloaded)

                    # Check for cancellation
                    if self.cancel_event and self.cancel_event.is_set():
                        raise DownloadCancelledError("Download cancelled by user")

        # Mark download as completed
        progress.complete_download(download_id, success=True)

    def _wait_for_download_completion(
        self, file_path: str, filename: str, timeout: int = 300
    ) -> tuple[str, bool]:
        """Wait for another process to complete downloading the file.

        Args:
            file_path: Path to the file being downloaded
            filename: Name of the file for logging
            timeout: Maximum time to wait in seconds

        Returns:
            tuple of (file_path, was_existing_file)

        """
        start_time = time.time()
        check_interval = 2  # Check every 2 seconds

        while time.time() - start_time < timeout:
            time.sleep(check_interval)

            if os.path.exists(file_path):
                # File exists, verify it's complete
                if self._verify_existing_file(file_path):
                    logger.info("Download of %s completed by another process", filename)
                    return file_path, True

            # Check if lock file still exists (indicating download is still in progress)
            lock_file_path = file_path + ".lock"
            if not os.path.exists(lock_file_path):
                # Lock file is gone but main file doesn't exist - download failed
                break

        # Timeout or download failed
        logger.error("Timeout waiting for %s to be downloaded by another process", filename)
        raise RuntimeError(
            "Timeout waiting for %s to be downloaded by another process" % filename
        )

    def _get_download_id(self, file_path: str) -> str:
        """Generate a unique download ID from file path.

        Args:
            file_path: Path to the file being downloaded

        Returns:
            Unique identifier for the download

        """
        return f"download_{abs(hash(file_path))}"
