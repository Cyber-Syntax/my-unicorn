import logging
import os
import shutil
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class FileHandler:
    """Handles file operations for AppImage management with atomic operations."""

    appimage_download_folder_path: str  # Default: ~/Documents/appimages/
    appimage_download_backup_folder_path: str  # ~/Documents/appimages/backup/
    config_file: str
    config_folder: str
    config_file_name: str
    repo: str
    version: str
    sha_name: str
    appimage_name: str
    batch_mode: bool
    keep_backup: bool

    # Derived properties
    @property
    def old_appimage_path(self) -> str:
        return os.path.join(self.appimage_download_folder_path, f"{self.repo}.AppImage")

    @property
    def backup_path(self) -> str:
        return os.path.join(
            self.appimage_download_backup_folder_path, f"{self.repo}.AppImage"
        )

    @property
    def target_path(self) -> str:
        return os.path.join(self.appimage_download_folder_path, f"{self.repo}.AppImage")

    @property
    def config_path(self) -> str:
        return os.path.join(self.config_folder, f"{self.repo}.json")

    def ask_user_confirmation(self, message: str) -> bool:
        """Handle confirmations respecting batch mode settings."""
        if self.batch_mode:
            logger.info("Batch mode: Auto-confirming '%s'", message)
            return True
        return input(f"{message} (y/n): ").strip().lower() == "y"

    def _safe_remove(self, path: str) -> None:
        """Safely remove a file with error handling."""
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info("Removed file: %s", path)
        except OSError as e:
            logger.error("Failed to remove %s: %s", path, e)
            if self.batch_mode:
                raise

    def make_executable(self, file_path: Optional[str] = None) -> None:
        """Make a file executable with proper error handling."""
        target = file_path or self.appimage_name
        try:
            if not os.path.exists(target):
                raise FileNotFoundError(f"File not found: {target}")

            current_mode = os.stat(target).st_mode
            if not (current_mode & os.X_OK):
                os.chmod(target, current_mode | 0o111)
                logger.info("Made executable: %s", target)
        except Exception as e:
            logger.error("Failed to make %s executable: %s", target, e)
            if self.batch_mode:
                raise

    def _ensure_directory(self, path: str) -> bool:
        """Create directory if needed with user confirmation."""
        if os.path.exists(path):
            return True

        if self.batch_mode or self.ask_user_confirmation(
            f"Create missing directory {path}?"
        ):
            os.makedirs(path, exist_ok=True)
            return True

        logger.warning("Directory creation cancelled: %s", path)
        return False

    def backup_old_appimage(self) -> None:
        """Create backup of existing AppImage with atomic operations."""
        if not os.path.exists(self.old_appimage_path):
            logger.info("No existing AppImage to backup")
            return

        if not self._ensure_directory(self.appimage_download_backup_folder_path):
            return

        try:
            # Use copy2 to preserve metadata
            shutil.copy2(self.old_appimage_path, self.backup_path)
            logger.info(
                "Created backup: %s → %s", self.old_appimage_path, self.backup_path
            )
        except IOError as e:
            logger.error("Backup failed: %s", e)
            if self.batch_mode:
                raise

    def _safe_move(self, src: str, dst: str) -> None:
        """Atomic file move with error handling."""
        try:
            shutil.move(src, dst)
            logger.info("Moved file: %s → %s", src, dst)
        except shutil.Error as e:
            logger.error("Move failed: %s", e)
            if self.batch_mode:
                raise

    # TODO: Need to find better way to rename
    # example standart-notes repo name is "app"...
    def rename_and_move_appimage(self) -> Tuple[bool, str]:
        """Rename the AppImage for Unix-based .desktop compatibility and move it to the download folder."""
        expected_name = f"{self.repo}.AppImage"
        try:
            # Rename the file if its basename doesn't match the expected name.
            if os.path.basename(self.appimage_name) != expected_name:
                self._safe_move(self.appimage_name, expected_name)
                logger.info("Renamed AppImage to %s", expected_name)
                self.appimage_name = expected_name
            else:
                logger.info("AppImage is already named %s", expected_name)

            # Ensure the target directory exists.
            os.makedirs(self.appimage_download_folder_path, exist_ok=True)
            target_path = os.path.join(
                self.appimage_download_folder_path, expected_name
            )

            # Move the file to the target directory.
            self._safe_move(self.appimage_name, target_path)
            logger.info("Moved AppImage to %s", self.appimage_download_folder_path)
            self.appimage_name = target_path

            return True, ""
        except Exception as e:
            logger.error("Rename and move failed: %s", e)
            return False, str(e)

    def handle_appimage_operations(self) -> bool:
        """Orchestrate complete file operations with a single global confirmation prompt.

        A summary of the changes is displayed first. In interactive mode,
        the user is prompted once to confirm all operations before proceeding.
        """
        # Build a summary of all planned operations.
        summary_lines = []
        if self.keep_backup:
            summary_lines.append(
                f"Backup old AppImage from {self.old_appimage_path} to {self.backup_path}"
            )
        summary_lines.append(f"Make AppImage executable: {self.appimage_name}")
        summary_lines.append(f"Rename and move AppImage to: {self.target_path}")
        summary_lines.append(f"Update configuration file at: {self.config_path}")
        if self.sha_name != "no_sha_file":
            summary_lines.append(f"Remove SHA file: {self.sha_name}")

        summary_message = "\n".join(summary_lines)
        print("----- Summary of Operations -----")
        print(summary_message)
        print("---------------------------------")

        # Ask a single confirmation prompt before starting operations.
        if not self.batch_mode and not self.ask_user_confirmation(
            "Proceed with these operations?"
        ):
            print("Operation cancelled by user.")
            return False

        # List of operations to perform.
        operations = [
            (self.backup_old_appimage, "Backup old AppImage"),
            (self.make_executable, "Make AppImage executable"),
            (self.rename_and_move_appimage, "Rename and move AppImage"),
            (
                lambda: self._safe_remove(self.sha_name)
                if self.sha_name != "no_sha_file"
                else None,
                "Cleanup SHA file",
            ),
        ]

        # Execute each operation with error handling.
        for operation, description in operations:
            try:
                logger.info("Starting: %s", description)
                if callable(operation):
                    result = operation()
                    # If an operation returns a tuple, check the success flag.
                    if isinstance(result, tuple) and not result[0]:
                        raise RuntimeError(result[1])
            except Exception as e:
                logger.error("Operation failed: %s - %s", description, e)
                if not self.batch_mode:
                    # In interactive mode, ask whether to continue if an operation fails.
                    if not self.ask_user_confirmation(
                        "Operation failed. Continue despite failure?"
                    ):
                        return False
        return True
