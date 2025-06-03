import asyncio
import fcntl
import logging
import os
import tempfile
import threading # Added for cancel_event
import time
from typing import Dict, Optional, Set

import requests

from .api import GitHubAPI
from .global_config import GlobalConfigManager
from .progress_manager import BasicMultiAppProgress


# Custom exception for download cancellation
class DownloadCancelledError(Exception):
    """Custom exception for when a download is cancelled."""
    pass


class DownloadManager:
    """Manages the download of AppImages from GitHub releases.

    Attributes:
        github_api: The GitHub API object containing release information
        _logger: Logger for this class
        is_async_mode: Whether the download is happening in an async context
        app_index: Index of the app in a multi-app update (1-based)
        total_apps: Total number of apps being updated
        cancel_event: Optional threading.Event to signal download cancellation.

    """

    # Class variables for shared progress tracking
    _global_progress: Optional[BasicMultiAppProgress] = None
    _active_tasks: Set[int] = set()
    _lock = asyncio.Lock() if hasattr(asyncio, "Lock") else None

    # Use GlobalConfigManager for configuration
    _global_config: Optional[GlobalConfigManager] = None
    
    # Class-level file locks to prevent concurrent access to same files
    _file_locks: Dict[str, threading.Lock] = {}
    _locks_lock = threading.Lock()  # Protects the _file_locks dictionary
    
    # Class-level progress task sharing for same files
    _progress_tasks: Dict[str, int] = {}  # Maps file paths to task IDs
    _progress_locks: Dict[str, threading.Lock] = {}  # Locks for progress task access

    def __init__(
        self,
        github_api: "GitHubAPI",
        app_index: int = 0,
        total_apps: int = 0,
        cancel_event: Optional[threading.Event] = None,
    ) -> None:
        """Initialize the download manager with GitHub API instance.

        Args:
            github_api: GitHub API instance containing release information
            app_index: Index of the app in a multi-app update (1-based)
            total_apps: Total number of apps being updated
            cancel_event: Optional threading.Event to signal download cancellation.

        """
        self.github_api = github_api
        self._logger = logging.getLogger(__name__)
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

    def download(self) -> tuple[str, bool]:
        """Download the AppImage from the GitHub release or return existing file.

        Returns:
            tuple: (file_path, was_existing_file) where was_existing_file is True if 
                   file already existed, False if newly downloaded

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

        downloads_dir = self.get_downloads_dir()
        existing_file_path = os.path.join(downloads_dir, appimage_name)
        
        # Get or create a lock for this specific file
        file_lock = self._get_file_lock(existing_file_path)
        
        # Use class-level locking to prevent concurrent operations on same file
        with file_lock:
            # Check if file exists
            if os.path.exists(existing_file_path):
                # Verify the existing file is complete
                if self._verify_existing_file(existing_file_path):
                    self._logger.info(f"File already exists and verified: {appimage_name}")
                    print(f"Found existing file: {appimage_name}")
                    return existing_file_path, True
                else:
                    # Remove corrupted/incomplete file
                    self._logger.info(f"Removing corrupted existing file: {appimage_name}")
                    try:
                        os.remove(existing_file_path)
                    except OSError as e:
                        self._logger.warning(f"Could not remove corrupted file {existing_file_path}: {e}")

            # Download the file atomically
            try:
                return self._download_with_atomic_write(appimage_url, appimage_name, existing_file_path)
            except Exception as e:
                error_msg = f"Error downloading {appimage_name}: {e!s}"
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
                if self.cancel_event and self.cancel_event.is_set():
                    self._logger.info(f"Download of {os.path.basename(file_path)} cancelled by user.")
                    # response.close() # Ensure connection is closed
                    # f.close() # Ensure file is closed before attempting to remove
                    # No, file is closed by with statement exit.
                    # We need to ensure the file is closed before removing.
                    # The 'with open' handles closing on break/return/exception.
                    raise DownloadCancelledError(f"Download of {os.path.basename(file_path)} cancelled.")

                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)

                    # Always update progress if we have a task_id
                    if task_id is not None and progress is not None:
                        # Important: Use direct method call for testability
                        progress.update(task_id, completed=downloaded_size)

        # Make the AppImage executable only if download wasn't cancelled
        # (If cancelled, this part is skipped due to exception)
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
            self._cleanup_progress_task() # Ensure progress task is cleaned up
            raise RuntimeError(error_msg)

        except DownloadCancelledError: # Catch our custom error
            self._logger.info(f"Download of {filename} was cancelled. Cleaning up partial file.")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self._logger.info(f"Successfully removed partial download: {file_path}")
                except OSError as e_remove:
                    self._logger.error(f"Error removing partial download {file_path}: {e_remove}")
            self._cleanup_progress_task() # Ensure progress task is cleaned up
            raise # Re-raise for the caller to handle

        except Exception: # General exceptions
            self._cleanup_progress_task() # Ensure progress task is cleaned up
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
        if self.github_api.skip_verification or not self.github_api.sha_name:
            logging.info("Skipping verification as requested (verification disabled or no hash provided)")
            return True

        from src.verify import VerificationManager # Import once at the top of the relevant scope

        # Handle "extracted_checksum" (which now implies hash might be directly available)
        # or other standard SHA file scenarios.
        # VerificationManager will internally decide whether to use direct_expected_hash
        # or fall back to legacy "extracted_checksum" logic, or parse a SHA file.

        direct_hash_to_pass: Optional[str] = None
        sha_name_to_pass: Optional[str] = self.github_api.sha_name
        sha_url_to_pass: Optional[str] = self.github_api.sha_url

        if self.github_api.sha_name == "extracted_checksum":
            logging.info(f"Processing 'extracted_checksum' for {self.github_api.appimage_name}.")
            # SHAManager should have set extracted_hash_from_body if it successfully parsed one.
            # It also sets hash_type to "sha256".
            direct_hash_to_pass = self.github_api.extracted_hash_from_body
            if direct_hash_to_pass:
                logging.info("Direct hash found for 'extracted_checksum', will pass to VerificationManager.")
                # sha_url is not needed if direct_hash is used by VerificationManager's "extracted_checksum" path
                sha_url_to_pass = None
            else:
                # If no direct hash, VerificationManager's "extracted_checksum" will use its legacy path
                logging.info("No direct hash for 'extracted_checksum', VerificationManager will use legacy path.")

        # For all other cases (actual SHA file names), direct_hash_to_pass remains None.
        # VerificationManager will download and parse the sha_name file.

        logging.info(
            f"Instantiating VerificationManager for {self.github_api.appimage_name} with: "
            f"sha_name='{sha_name_to_pass}', hash_type='{self.github_api.hash_type}', "
            f"direct_hash_provided={direct_hash_to_pass is not None}"
        )

        verifier = VerificationManager(
            sha_name=sha_name_to_pass,
            sha_url=sha_url_to_pass,
            appimage_name=self.github_api.appimage_name,
            appimage_path=downloaded_file,
            hash_type=self.github_api.hash_type if self.github_api.hash_type is not None else "sha256",
            direct_expected_hash=direct_hash_to_pass,
            asset_digest=self.github_api.asset_digest,
        )
        return verifier.verify_appimage(cleanup_on_failure=True)

    @classmethod
    def _get_file_lock(cls, file_path: str) -> threading.Lock:
        """Get or create a lock for a specific file path.
        
        Args:
            file_path: The file path to get a lock for
            
        Returns:
            A threading.Lock for the specified file
        """
        with cls._locks_lock:
            if file_path not in cls._file_locks:
                cls._file_locks[file_path] = threading.Lock()
            return cls._file_locks[file_path]
    
    @classmethod
    def _get_or_create_progress_task(cls, file_path: str, filename: str, total_size: int, prefix: str, progress_manager) -> tuple[int, bool]:
        """Get existing progress task for file or create a new one.
        
        Args:
            file_path: Full path to the file
            filename: Display name for the file
            total_size: Total file size
            prefix: Progress display prefix
            progress_manager: Progress manager instance
            
        Returns:
            Tuple of (task_id, is_owner) where is_owner indicates if this thread should update progress
        """
        with cls._locks_lock:
            # Get or create progress lock for this file
            if file_path not in cls._progress_locks:
                cls._progress_locks[file_path] = threading.Lock()
            progress_lock = cls._progress_locks[file_path]
        
        with progress_lock:
            # Check if we already have a progress task for this file
            if file_path in cls._progress_tasks:
                return cls._progress_tasks[file_path], False  # Not the owner
            
            # Create new progress task
            task_id = progress_manager.add_task(
                f"Downloading {filename}",
                total=total_size,
                prefix=prefix,
            )
            
            cls._progress_tasks[file_path] = task_id
            return task_id, True  # This thread is the owner
    
    @classmethod
    def _update_progress_task(cls, file_path: str, progress_manager, **kwargs) -> None:
        """Update progress for a file if task exists.
        
        Args:
            file_path: Full path to the file
            progress_manager: Progress manager instance
            **kwargs: Progress update arguments
        """
        with cls._locks_lock:
            if file_path not in cls._progress_locks:
                return
            progress_lock = cls._progress_locks[file_path]
        
        with progress_lock:
            if file_path in cls._progress_tasks:
                task_id = cls._progress_tasks[file_path]
                progress_manager.update(task_id, **kwargs)
    
    @classmethod
    def _cleanup_progress_task(cls, file_path: str, progress_manager) -> None:
        """Clean up progress task when file download is complete.
        
        Args:
            file_path: Full path to the file
            progress_manager: Progress manager instance
        """
        with cls._locks_lock:
            if file_path not in cls._progress_locks:
                return
            progress_lock = cls._progress_locks[file_path]
        
        with progress_lock:
            # Remove from shared progress tasks
            if file_path in cls._progress_tasks:
                task_id = cls._progress_tasks[file_path]
                del cls._progress_tasks[file_path]
                
                # Remove the task from progress manager
                try:
                    progress_manager.remove_task(task_id)
                except Exception:
                    pass
        
        # Clean up the progress lock if no longer needed
        with cls._locks_lock:
            if file_path in cls._progress_locks:
                del cls._progress_locks[file_path]

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
                self._logger.warning(f"File {file_path} is too small ({file_size} bytes)")
                return False
                
            # Try to get expected file size from server if possible
            try:
                expected_size = self._get_expected_file_size()
                if expected_size > 0 and abs(file_size - expected_size) > 1024:  # Allow 1KB tolerance
                    self._logger.warning(f"File size mismatch: expected {expected_size}, got {file_size}")
                    return False
            except Exception:
                # If we can't get expected size, just check basic validity
                pass
                
            return True
            
        except Exception as e:
            self._logger.error(f"Error verifying existing file {file_path}: {e}")
            return False
    
    def _get_expected_file_size(self) -> int:
        """Get the expected file size from the server.
        
        Returns:
            Expected file size in bytes, or 0 if unknown
        """
        try:
            headers = {"User-Agent": "AppImage-Updater/1.0"}
            response = requests.head(
                self.github_api.appimage_url, 
                allow_redirects=True, 
                timeout=10, 
                headers=headers
            )
            response.raise_for_status()
            
            content_length = response.headers.get("Content-Length")
            if content_length:
                return int(content_length)
                
        except Exception as e:
            self._logger.debug(f"Could not get expected file size: {e}")
            
        return 0
    
    def _download_with_atomic_write(self, url: str, filename: str, final_path: str) -> tuple[str, bool]:
        """Download file atomically using a temporary file.
        
        Args:
            url: URL to download from
            filename: Name of the file being downloaded
            final_path: Final path where the file should be placed
            
        Returns:
            Tuple of (file_path, was_existing_file)
        """
        downloads_dir = os.path.dirname(final_path)
        
        # Create temporary file in the same directory
        with tempfile.NamedTemporaryFile(
            dir=downloads_dir,
            prefix=f".{filename}.",
            suffix=".tmp",
            delete=False
        ) as temp_file:
            temp_path = temp_file.name
            
        try:
            # Set up request headers
            headers = {"User-Agent": "AppImage-Updater/1.0", "Accept": "application/octet-stream"}
            
            # Create a progress prefix if this is part of a multi-app update
            prefix = f"[{self.app_index}/{self.total_apps}] " if self.total_apps > 0 else ""
            
            # Download to temporary file with shared progress tracking
            self._download_with_progress_to_file(url, temp_path, filename, headers, prefix, final_path)
            
            # Make the AppImage executable
            os.chmod(temp_path, os.stat(temp_path).st_mode | 0o111)
            
            # Atomically move the completed file to its final location
            os.rename(temp_path, final_path)
            
            self._logger.info(f"Successfully downloaded {filename} to {final_path}")
            return final_path, False
            
        except Exception as e:
            # Clean up temporary file on error
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            raise e
    
    def _download_with_progress_to_file(self, url: str, file_path: str, filename: str, headers: dict, prefix: str, final_path: str) -> None:
        """Download a file with progress tracking to a specific path.
        
        Args:
            url: URL to download from
            file_path: Path where to save the file
            filename: Display name for progress
            headers: HTTP headers
            prefix: Progress display prefix
            final_path: Final destination path (for progress tracking)
        """
        try:
            response = requests.get(url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()
            
            total_size = int(response.headers.get("Content-Length", 0))
            progress = self.get_or_create_progress()
            
            # Use shared progress task for this file
            task_id, is_progress_owner = self._get_or_create_progress_task(final_path, filename, total_size, prefix, progress)
            downloaded = 0
            
            try:
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Only update progress if this thread is the owner
                            if is_progress_owner and progress and task_id is not None:
                                progress.update(task_id, completed=downloaded)
                                
                            # Check for cancellation
                            if self.cancel_event and self.cancel_event.is_set():
                                raise DownloadCancelledError("Download cancelled by user")
                                
            finally:
                # Only clean up progress task if this thread owns it and download is complete
                if is_progress_owner and task_id is not None and progress and downloaded == total_size:
                    self._cleanup_progress_task(final_path, progress)
                
            # Only display completion stats if this thread owns the progress
            if is_progress_owner:
                self._display_completion_stats(filename, downloaded, time.time(), prefix)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error downloading {filename}: {e!s}"
            self._logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    def _wait_for_download_completion(self, file_path: str, filename: str, timeout: int = 300) -> tuple[str, bool]:
        """Wait for another process to complete downloading the file.
        
        Args:
            file_path: Path to the file being downloaded
            filename: Name of the file for logging
            timeout: Maximum time to wait in seconds
            
        Returns:
            Tuple of (file_path, was_existing_file) 
        """
        start_time = time.time()
        check_interval = 2  # Check every 2 seconds
        
        while time.time() - start_time < timeout:
            time.sleep(check_interval)
            
            if os.path.exists(file_path):
                # File exists, verify it's complete
                if self._verify_existing_file(file_path):
                    self._logger.info(f"Download of {filename} completed by another process")
                    return file_path, True
                    
            # Check if lock file still exists (indicating download is still in progress)
            lock_file_path = file_path + ".lock"
            if not os.path.exists(lock_file_path):
                # Lock file is gone but main file doesn't exist - download failed
                break
                
        # Timeout or download failed
        error_msg = f"Timeout waiting for {filename} to be downloaded by another process"
        self._logger.error(error_msg)
        raise RuntimeError(error_msg)
