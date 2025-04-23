import logging
import os
import sys
import asyncio
import time
from typing import Optional, List, Dict, Any, Union, Set

import requests
from rich.console import Console
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)

from .api import GitHubAPI
from .global_config import GlobalConfigManager


class MultiAppProgress(Progress):
    """
    Custom Progress class for displaying multiple app downloads simultaneously.

    Each app gets its own progress bar with its own styling and prefix.
    All progress bars are rendered together in a single display.
    """

    def get_renderables(self) -> List[Any]:
        """
        Override to customize the progress bar display for each task.

        Returns:
            List[Any]: A list of renderables for displaying download progress
        """
        renderables = []

        # Safely iterate through tasks that actually exist
        for task in self.tasks:
            if task.visible:
                # Get the custom prefix if provided
                prefix = task.fields.get("prefix", "")

                # Create app-specific columns for this task
                temp_columns = [
                    TextColumn(f"{prefix}[bold cyan]{{task.description}}[/]"),
                    BarColumn(),
                    "[progress.percentage]{task.percentage:>3.0f}%",
                    "•",
                    DownloadColumn(),
                    "•",
                    TransferSpeedColumn(),
                    "•",
                    TimeRemainingColumn(),
                ]

                # Create a table with just this task
                # Note: make_tasks_table in Rich only takes the columns parameter
                # and gets tasks from self.tasks. We need to create a new Progress
                # instance with just this task.
                single_task_progress = Progress(*temp_columns)
                single_task_progress.add_task(
                    task.description, total=task.total, completed=task.completed, **task.fields
                )
                renderables.append(single_task_progress)

        return renderables


class DownloadManager:
    """
    Manages the download of AppImages from GitHub releases.

    Attributes:
        github_api: The GitHub API object containing release information
        _logger: Logger for this class
        is_async_mode: Whether the download is happening in an async context
        app_index: Index of the app in a multi-app update (1-based)
        total_apps: Total number of apps being updated
    """

    # Class variables for shared progress tracking
    _global_progress: Optional[MultiAppProgress] = None
    _active_tasks: Set[int] = set()
    _lock = (
        asyncio.Lock() if hasattr(asyncio, "Lock") else None
    )  # For thread safety in async contexts

    # Use GlobalConfigManager for configuration
    _global_config: Optional[GlobalConfigManager] = None

    def __init__(self, github_api: "GitHubAPI", app_index: int = 0, total_apps: int = 0) -> None:
        """
        Initialize the download manager with GitHub API instance.

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
        try:
            asyncio.get_running_loop()
            self.is_async_mode = True
        except RuntimeError:
            self.is_async_mode = False

        # Store task ID for this download instance
        self._progress_task_id: Optional[int] = None

    def _format_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format.

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
    def get_or_create_progress(cls) -> MultiAppProgress:
        """
        Get or create a shared progress instance for all downloads.

        Returns:
            MultiAppProgress: The shared progress instance
        """
        # Use the first instance's progress or create a new one
        if cls._global_progress is None:
            cls._global_progress = MultiAppProgress(
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
                logging.error(f"Error stopping progress display: {str(e)}")
            finally:
                cls._global_progress = None
                cls._active_tasks = set()

    def download(self) -> None:
        """
        Download the AppImage from the GitHub release.

        Raises:
            ValueError: If AppImage URL or name is not available
            RuntimeError: For network errors, file system errors, or other unexpected issues
        """
        appimage_url = self.github_api.appimage_url
        appimage_name = self.github_api.appimage_name

        if not appimage_url or not appimage_name:
            error_msg = "AppImage URL or name not available. Cannot download."
            self._logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Set up request with appropriate headers
            headers = {"User-Agent": "AppImage-Updater/1.0", "Accept": "application/octet-stream"}

            # Create a console for output
            console = Console()

            # Create a progress prefix if this is part of a multi-app update
            prefix = f"[{self.app_index}/{self.total_apps}] " if self.total_apps > 0 else ""

            # Download with nested progress tracking
            self._download_with_nested_progress(
                appimage_url, appimage_name, headers, console, prefix
            )

        except IOError as e:
            error_msg = f"File system error while downloading {appimage_name}: {str(e)}"
            self._logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error downloading {appimage_name}: {str(e)}"
            self._logger.error(error_msg)
            raise RuntimeError(error_msg)

    def _download_with_nested_progress(
        self,
        appimage_url: str,
        appimage_name: str,
        headers: Dict[str, str],
        console: Console,
        prefix: str = "",
    ) -> None:
        """
        Download with a nested progress bar display.

        Args:
            appimage_url: URL to download from
            appimage_name: Name of the AppImage file
            headers: HTTP headers for the request
            console: Rich console for output
            prefix: Prefix to add to progress messages (e.g., "[1/2] ")

        Raises:
            Exception: Any error during download
        """
        try:
            # Get file size
            self._logger.info(f"Fetching headers for {appimage_url}")
            response = requests.head(
                appimage_url, allow_redirects=True, timeout=10, headers=headers
            )
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))

            # Create output directory if it doesn't exist
            os.makedirs("downloads", exist_ok=True)

            # Prepare the output file path
            file_path = os.path.join("downloads", appimage_name)

            # Get the shared progress instance with thread safety
            progress = self.get_or_create_progress()

            # Add a task for this download with the app's prefix
            try:
                download_task = progress.add_task(
                    f"Downloading {appimage_name}",
                    total=total_size,
                    prefix=prefix,  # Store prefix as a custom field
                )

                # Track this task
                self._progress_task_id = download_task
                DownloadManager._active_tasks.add(download_task)

            except Exception as e:
                self._logger.error(f"Error creating progress task: {str(e)}")
                # Fallback to console output without progress bar
                console.print(f"{prefix}[cyan]Downloading {appimage_name}...[/]")
                download_task = None

            # Start the actual download
            start_time = time.time()
            response = requests.get(appimage_url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()

            # Download with progress tracking
            downloaded_size = 0
            chunk_size = 1024 * 1024  # 1MB per chunk

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if download_task is not None and progress is not None:
                            try:
                                progress.update(download_task, completed=downloaded_size)
                            except Exception as e:
                                # If updating progress fails, log it but continue the download
                                self._logger.debug(f"Error updating progress: {str(e)}")

            # Make the AppImage executable
            os.chmod(file_path, os.stat(file_path).st_mode | 0o111)

            # Clean up progress tracking
            if download_task is not None and progress is not None:
                try:
                    # Mark task as completed
                    progress.update(download_task, completed=total_size)

                    # Remove this task from tracking and the progress display
                    if download_task in DownloadManager._active_tasks:
                        DownloadManager._active_tasks.remove(download_task)

                    progress.remove_task(download_task)
                    self._progress_task_id = None
                except Exception as e:
                    self._logger.debug(f"Error cleaning up progress task: {str(e)}")

            # Calculate download statistics
            download_time = time.time() - start_time
            speed_mbps = (total_size / (1024 * 1024)) / download_time if download_time > 0 else 0

            # Display completion message
            logging.info(
                f"{prefix}[green]✓ Downloaded {appimage_name}[/] "
                f"({self._format_size(total_size)}, {speed_mbps:.1f} MB/s)"
            )
            self._logger.info(f"Successfully downloaded {appimage_name}")

            # If this is the last download and we're in async mode, clean up the progress display
            if self.is_async_mode and self.app_index == self.total_apps:
                # Only stop if no active tasks remain
                if not DownloadManager._active_tasks:
                    self.stop_progress()

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error while downloading {appimage_name}: {str(e)}"
            self._logger.error(error_msg)
            console.print(f"{prefix}[bold red]✗ Download failed:[/] {error_msg}")

            # Clean up the progress task if it exists
            if hasattr(self, "_progress_task_id") and self._progress_task_id is not None:
                try:
                    if self._progress_task_id in DownloadManager._active_tasks:
                        DownloadManager._active_tasks.remove(self._progress_task_id)

                    if DownloadManager._global_progress is not None:
                        DownloadManager._global_progress.remove_task(self._progress_task_id)
                except Exception:
                    pass  # Ignore errors during cleanup

                self._progress_task_id = None

            raise RuntimeError(error_msg)
        except Exception as e:
            # Ensure we clean up the task in case of any other error
            if hasattr(self, "_progress_task_id") and self._progress_task_id is not None:
                try:
                    if self._progress_task_id in DownloadManager._active_tasks:
                        DownloadManager._active_tasks.remove(self._progress_task_id)

                    if DownloadManager._global_progress is not None:
                        DownloadManager._global_progress.remove_task(self._progress_task_id)
                except Exception:
                    pass  # Ignore errors during cleanup

                self._progress_task_id = None

            raise  # Re-raise the original exception
