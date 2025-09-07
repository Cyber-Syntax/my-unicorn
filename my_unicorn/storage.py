"""Storage service for handling file system operations.

This module provides a service for file operations such as making files executable,
renaming, moving, creating backups, and other storage-related tasks.
"""

import os
from pathlib import Path

from my_unicorn.logger import get_logger

logger = get_logger(__name__)


# TODO: Rename the class as FileOps or AppimageFileOps to represent much meaningful for python.
class StorageService:
    """Service for handling file system operations."""

    def __init__(self, install_dir: Path) -> None:
        """Initialize storage service with install directory.

        Args:
            install_dir: Directory for installations

        """
        self.install_dir = install_dir

    def make_executable(self, path: Path) -> None:
        """Make file executable.

        Args:
            path: Path to file to make executable

        """
        logger.debug("🔧 Making executable: %s", path.name)
        os.chmod(path, 0o755)
        logger.debug("✅ File permissions updated")

    def move_file(self, source: Path, destination: Path) -> Path:
        """Move file from source to destination.

        Args:
            source: Source file path
            destination: Destination file path

        Returns:
            Final destination path

        """
        if source == destination:
            return destination

        # Create destination directory if it doesn't exist
        destination.parent.mkdir(parents=True, exist_ok=True)

        # If target exists, remove it
        if destination.exists():
            logger.debug("🗑️  Removing existing file: %s", destination)
            destination.unlink()

        # Move file
        logger.debug("📦 Moving file: %s → %s", source, destination)
        source.rename(destination)
        return destination

    def move_to_install_dir(self, source: Path, filename: str | None = None) -> Path:
        """Move file from source to install directory.

        Args:
            source: Source file path
            filename: Optional new filename (uses source name if not provided)

        Returns:
            Final installation path

        """
        target_name = filename or source.name
        destination = self.install_dir / target_name
        return self.move_file(source, destination)

    def rename_file(self, current_path: Path, new_name: str) -> Path:
        """Rename a file to a new name.

        Args:
            current_path: Current file path
            new_name: New filename

        Returns:
            New path after rename

        """
        new_path = current_path.parent / new_name

        logger.debug("🏷️  Renaming file: %s → %s", current_path.name, new_name)

        if current_path.exists():
            # Remove target if it exists (for updates)
            if new_path.exists() and new_path != current_path:
                logger.debug("🗑️  Removing existing file: %s", new_path)
                new_path.unlink()

            current_path.rename(new_path)
            logger.debug("✅ Renamed to: %s", new_path)

        return new_path

    def rename_appimage(self, current_path: Path, new_name: str) -> Path:
        """Rename an AppImage file with proper extension handling.

        Args:
            current_path: Current AppImage path
            new_name: New name for the AppImage (extension will be added if missing)

        Returns:
            New path after rename

        """
        # Ensure proper AppImage extension
        if not new_name.lower().endswith(".appimage"):
            new_name = new_name + ".AppImage"

        return self.rename_file(current_path, new_name)

    def get_clean_appimage_name(self, rename: str) -> str:
        """Generate clean AppImage name from rename field.

        Args:
            rename: Rename value from catalog config

        Returns:
            Clean AppImage base name (without extension)

        """
        clean_name = rename.strip()
        # Remove any existing extensions to avoid double extensions
        if clean_name.lower().endswith((".appimage", ".AppImage")):
            clean_name = clean_name[:-9]  # Remove .AppImage or .appimage
        return clean_name
