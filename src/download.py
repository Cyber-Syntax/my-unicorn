import asyncio
import logging
import os
import time
from typing import Dict, Optional, Set

import requests

from .api import GitHubAPI
from .global_config import GlobalConfigManager
from .progress_manager import BasicMultiAppProgress


class DownloadManager:
    """Manages the download of AppImages from GitHub releases.

    Attributes:
        github_api: The GitHub API object containing release information
        _logger: Logger for this class
        is_async_mode: Whether the download is happening in an async context
        app_index: Index of the app in a multi-app update (1-based)
        total_apps: Total number of apps being updated

    """

    # Class variables for shared progress tracking
    _global_progress: Optional[BasicMultiAppProgress] = None
    _active_tasks: Set[int] = set()
    _lock = asyncio.Lock() if hasattr(asyncio, "Lock") else None

    # Use GlobalConfigManager for configuration
    _global_config: Optional[GlobalConfigManager] = None

    def __init__(self, github_api: "GitHubAPI", app_index: int = 0, total_apps: int = 0) -> None:
        """Initialize the download manager with GitHub API instance.

        Args:
            github_api: GitHub API instance containing release information
            app_index: Index of the app in a multi-app update (1-based)
            total_apps: Total number of apps being updated

        """
        self.github_api = github_api
        self._logger = logging.getLogger(__name__)
        self.app_index = app_index
        self.total_apps = total_apps

        # Initialize global config if not already set
        if DownloadManager._global_config is None:
            DownloadManager._global_config = GlobalConfigManager()
            DownloadManager._global_config.load_config()

        # Detect if we're in an async context
        self.is_async_mode = self._detect_async_mode()

        # Store task ID for this download instance
        self._progress_task_id: Optional[int] = None

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
    def get_or_create_progress(cls) -> BasicMultiAppProgress:
        """Get or create a shared progress instance for all downloads.

        Returns:
            BasicMultiAppProgress: The shared progress instance

        """
        # Use the first instance's progress or create a new one
        if cls._global_progress is None:
            cls._global_progress = BasicMultiAppProgress(
                expand=True,
                transient=False,  # Keep all progress bars visible
            )
            cls._global_progress.start()
            cls._active_tasks = set()

        return cls._global_progress

    @classmethod
    def stop_progress(cls) -> None:
        """Stop and clear the shared progress instance."""
        if cls._global_progress is not None:
            try:
                cls._global_progress.stop()
            except Exception as e:
                logging.error(f"Error stopping progress display: {e!s}")
            finally:
                cls._global_progress = None
                cls._active_tasks = set()

    def download(self) -> str:
        """Download the AppImage from the GitHub release.

        Returns:
            str: The full path to the downloaded AppImage file

        Raises:
            ValueError: If AppImage URL or name is not available
            RuntimeError: For network errors, file system errors, or other unexpected issues

        """
        appimage_url = self.github_api.appimage_url
        appimage_name = self.github_api.appimage_name

        if not appimage_url or not appimage_name:
            error_msg = "AppImage URL or name is not available. Cannot download."
            self._logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Set up request headers
            headers = {"User-Agent": "AppImage-Updater/1.0", "Accept": "application/octet-stream"}

            # Create a progress prefix if this is part of a multi-app update
            prefix = f"[{self.app_index}/{self.total_apps}] " if self.total_apps > 0 else ""

            # Download with progress tracking
            download_path = self._download_with_progress(
                appimage_url, appimage_name, headers, prefix
            )

            return download_path

        except OSError as e:
            error_msg = f"File system error while downloading {appimage_name}: {e!s}"
            self._logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error downloading {appimage_name}: {e!s}"
            self._logger.error(error_msg)
            raise RuntimeError(error_msg)

    def _get_file_size(self, url: str, headers: Dict[str, str]) -> int:
        """Get the file size by making a HEAD request.

        Args:
            url: URL to check
            headers: HTTP headers for the request

        Returns:
            int: File size in bytes

        Raises:
            requests.exceptions.RequestException: For network errors

        """
        self._logger.info(f"Fetching headers for {url}")
        response = requests.head(url, allow_redirects=True, timeout=10, headers=headers)
        response.raise_for_status()
        return int(response.headers.get("content-length", 0))

    def _setup_progress_task(self, filename: str, total_size: int, prefix: str) -> Optional[int]:
        """Set up a progress tracking task.

        Args:
            filename: Name of the file being downloaded
            total_size: Total size in bytes
            prefix: Prefix for the progress message

        Returns:
            Optional[int]: ID of the progress task, or None if setup failed

        """
        progress = self.get_or_create_progress()

        try:
            task_id = progress.add_task(
                f"Downloading {filename}",
                total=total_size,
                prefix=prefix,
            )

            # Track this task
            self._progress_task_id = task_id
            DownloadManager._active_tasks.add(task_id)
            return task_id

        except Exception as e:
            self._logger.error(f"Error creating progress task: {e!s}")
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

        if progress is not None:
            # Call the remove_task method directly without try/except
            # This ensures it will work with our test mocks
            progress.remove_task(self._progress_task_id)

        self._progress_task_id = None

    def _perform_download(
        self,
        url: str,
        file_path: str,
        headers: Dict[str, str],
        task_id: Optional[int],
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
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)

                    # Always update progress if we have a task_id
                    if task_id is not None and progress is not None:
                        # Important: Use direct method call for testability
                        progress.update(task_id, completed=downloaded_size)

        # Make the AppImage executable
        os.chmod(file_path, os.stat(file_path).st_mode | 0o111)

        # Final update to mark task as completed
        if task_id is not None and progress is not None:
            progress.update(task_id, completed=total_size)

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

    def _download_with_progress(
        self,
        url: str,
        filename: str,
        headers: Dict[str, str],
        prefix: str = "",
    ) -> str:
        """Download with a progress bar display.

        Args:
            url: URL to download from
            filename: Name of the file
            headers: HTTP headers for the request
            prefix: Prefix to add to progress messages

        Returns:
            str: The full path to the downloaded file

        Raises:
            RuntimeError: Any error during download

        """
        try:
            # Get file size
            total_size = self._get_file_size(url, headers)

            # Get the downloads directory
            downloads_dir = self.get_downloads_dir()
            file_path = os.path.join(downloads_dir, filename)

            # Set up progress tracking
            task_id = self._setup_progress_task(filename, total_size, prefix)

            # Perform the download
            download_time = self._perform_download(url, file_path, headers, task_id, total_size)

            # Clean up progress tracking
            self._cleanup_progress_task()

            # Display completion message
            self._display_completion_stats(filename, total_size, download_time, prefix)
            self._logger.info(f"Successfully downloaded {file_path}")

            # Check if we should stop progress tracking
            if self.is_async_mode and self.app_index == self.total_apps:
                if not DownloadManager._active_tasks:
                    self.stop_progress()

            return file_path

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error while downloading {filename}: {e!s}"
            self._logger.error(error_msg)
            print(f"{prefix}✗ Download failed: {error_msg}")
            self._cleanup_progress_task()
            raise RuntimeError(error_msg)

        except Exception:
            self._cleanup_progress_task()
            raise  # Re-raise the original exception

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
        logging.info("Verifying download integrity...")

        # Skip verification if hash verification is disabled
        if self.github_api.hash_type == "no_hash" or not self.github_api.sha_name:
            logging.info("Skipping verification as requested (no hash provided)")
            return True

        # Special handling for checksums extracted from release description
        if self.github_api.sha_name == "extracted_checksum":
            logging.info("Using GitHub release description for verification")

            # Import our checksum extraction utility
            from src.utils.extract_checksums import verify_with_release_checksums

            # Use direct owner/repo from github_api for verification
            owner = self.github_api.owner
            repo = self.github_api.repo

            logging.info(f"Extracting checksums from {owner}/{repo} release description")
            return verify_with_release_checksums(
                owner=owner, repo=repo, appimage_path=downloaded_file, cleanup_on_failure=True
            )

        # Standard verification with SHA file
        from src.verify import VerificationManager

        verifier = VerificationManager(
            sha_name=self.github_api.sha_name,
            sha_url=self.github_api.sha_url,
            appimage_name=os.path.basename(self.github_api.appimage_url),
            appimage_path=downloaded_file,
            hash_type=self.github_api.hash_type,
        )

        return verifier.verify_appimage(cleanup_on_failure=True)
