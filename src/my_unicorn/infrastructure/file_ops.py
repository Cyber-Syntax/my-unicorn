"""File operations for handling file system tasks.

This module provides utilities for file operations such as making files
executable, renaming, moving, creating backups, icon extraction, and other
storage-related tasks.
"""

from pathlib import Path

from my_unicorn.infrastructure.icon import AppImageIconExtractor, IconExtractionError
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


class FileOperations:
    """File system operations utility."""

    def __init__(self, install_dir: Path) -> None:
        """Initialize file operations with install directory.

        Args:
            install_dir: Directory for installations

        """
        self.install_dir = install_dir

    def make_executable(self, path: Path) -> None:
        """Make file executable.

        Args:
            path: Path to file to make executable

        """
        logger.debug("Making executable: %s", path.name)
        path.chmod(0o755)
        logger.debug("File permissions updated: %s", path.name)

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
            logger.debug("Removing existing file: %s", destination)
            destination.unlink()

        # Move file
        logger.debug("Moving file: %s -> %s", source.name, destination.name)
        source.rename(destination)
        return destination

    def move_to_install_dir(
        self, source: Path, filename: str | None = None
    ) -> Path:
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

        logger.debug("Renaming file: %s -> %s", current_path.name, new_name)

        if current_path.exists():
            # Remove target if it exists (for updates)
            if new_path.exists() and new_path != current_path:
                logger.debug("Removing existing file: %s", new_path)
                new_path.unlink()

            current_path.rename(new_path)
            logger.debug("Renamed successfully: %s", new_path.name)

        return new_path

    def rename_appimage(self, current_path: Path, new_name: str) -> Path:
        """Rename an AppImage file with proper extension handling.

        Args:
            current_path: Current AppImage path
            new_name: New name for the AppImage (extension added if missing)

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
        return clean_name.removesuffix(".AppImage").removesuffix(".appimage")


async def extract_icon_from_appimage(
    appimage_path: Path,
    icon_dir: Path,
    app_name: str,
    icon_filename: str | None = None,
) -> Path | None:
    """Extract icon from AppImage file.

    This is a simple file operation that extracts an icon from an AppImage
    and saves it to the configured icon directory. Should be called after
    AppImage installation but before desktop entry creation.

    Args:
        appimage_path: Path to the installed AppImage
        icon_dir: Directory where icons should be saved
        app_name: Application name for icon matching
        icon_filename: Icon filename or None (defaults to app_name.png)

    Returns:
        Path to extracted icon or None if extraction failed

    """
    if not appimage_path.exists():
        logger.warning(
            "AppImage not found for icon extraction: %s", appimage_path
        )
        return None

    # Generate icon filename if not provided
    if not icon_filename:
        icon_filename = f"{app_name}.png"

    dest_path = icon_dir / icon_filename

    # Ensure icon directory exists
    icon_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Extracting icon from AppImage: %s", appimage_path.name)

    try:
        # Use AppImageIconExtractor to perform extraction
        extractor = AppImageIconExtractor()
        extracted_icon = await extractor.extract_icon(
            appimage_path=appimage_path,
            dest_path=dest_path,
            app_name=app_name,
        )

        if extracted_icon:
            logger.info(
                "✅ Icon extracted successfully: %s", extracted_icon.name
            )
            return extracted_icon

    except IconExtractionError as e:
        error_msg = str(e)
        # Check if this is a recoverable error (unsupported compression, etc.)
        extractor = AppImageIconExtractor()
        if extractor.is_recoverable_error(error_msg):
            logger.info(
                "️  Cannot extract icon from %s: %s", app_name, error_msg
            )
        else:
            logger.warning("Icon extraction failed for %s: %s", app_name, e)
        return None

    except (OSError, PermissionError) as e:
        logger.warning(
            "️  File operation error during icon extraction for %s: %s",
            app_name,
            e,
        )
        return None
    else:
        logger.info("No icon found in AppImage for %s", app_name)
        return None
