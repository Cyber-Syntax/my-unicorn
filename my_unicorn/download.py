"""Download manager for AppImages from GitHub releases.

This module provides the DownloadManager class that handles downloading AppImages
from GitHub releases with progress tracking, file verification, and concurrent
download support.
"""

import logging
import os
import tempfile
import threading  # Added for cancel_event
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

        # Store task ID for this download instance
        self._progress_task_id: str | None = None

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

    def _get_download_id(self, file_path: str) -> str:
        """Generate a unique download ID from file path.

        Args:
            file_path: Path to the file being downloaded

        Returns:
            Unique identifier for the download

        """
        return f"download_{abs(hash(file_path))}"
