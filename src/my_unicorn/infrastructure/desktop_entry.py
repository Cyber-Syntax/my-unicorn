"""Desktop entry management for AppImage applications.

This module handles creating and removing .desktop files for installed
AppImage applications following the freedesktop.org desktop entry specification.

Design Philosophy:
- Desktop files are created ONCE during initial installation
- Desktop files are NEVER modified during updates (thanks to clean naming)
- Since AppImages use clean names (e.g., siyuan.appimage), paths never change
- Updates only replace the AppImage file, desktop entry remains valid
- This ensures stable desktop integration without constant file rewrites
"""

import os
import shutil
from pathlib import Path
from typing import Any

from my_unicorn.logger import get_logger
from my_unicorn.utils.utils import create_desktop_entry_name, sanitize_filename

from ..config import ConfigManager
from ..domain.constants import (
    DESKTOP_BROWSER_CATEGORIES,
    DESKTOP_BROWSER_EXEC_PARAM,
    DESKTOP_BROWSER_KEYWORDS,
    DESKTOP_BROWSER_MIME_TYPES,
    DESKTOP_BROWSER_NAMES,
    DESKTOP_DEFAULT_CATEGORIES,
    DESKTOP_FILE_TYPE,
    DESKTOP_FILE_VERSION,
    DESKTOP_ICON_EXTENSIONS,
    DESKTOP_SECTION_HEADER,
    DESKTOP_SYSTEM_APPLICATION_DIRS,
    DESKTOP_USER_APPLICATIONS_SUBPATH,
)

logger = get_logger(__name__)


class DesktopEntry:
    """Manages .desktop entry files for AppImage applications."""

    def __init__(
        self,
        app_name: str,
        appimage_path: Path,
        icon_path: Path | None = None,
        config_manager: ConfigManager | None = None,
    ):
        """Initialize desktop entry manager.

        Args:
            app_name: Name of the application
            appimage_path: Path to the AppImage file (should be clean name without version)
            icon_path: Optional path to icon file
            config_manager: Configuration manager for directory paths

        """
        self.app_name = app_name.lower()  # Normalize to lowercase
        self.appimage_path = appimage_path
        self.icon_path = icon_path
        self.desktop_filename = create_desktop_entry_name(self.app_name)
        self.config_manager = config_manager or ConfigManager()
        self.global_config = self.config_manager.load_global_config()

    def get_desktop_dirs(self) -> list[Path]:
        """Get list of desktop entry directories to check.

        Returns:
            List of desktop directory paths in order of preference

        """
        dirs = []

        # User-specific directory (highest priority)
        user_dir = Path.home().joinpath(*DESKTOP_USER_APPLICATIONS_SUBPATH)
        dirs.append(user_dir)

        # System directories (lower priority)
        for dirpath in DESKTOP_SYSTEM_APPLICATION_DIRS:
            dir_path = Path(dirpath)
            if dir_path.exists():
                dirs.append(dir_path)

        return dirs

    def find_existing_desktop_file(self) -> Path | None:
        """Find existing desktop file for this application.

        Returns:
            Path to existing desktop file or None if not found

        """
        for desktop_dir in self.get_desktop_dirs():
            desktop_file = desktop_dir / self.desktop_filename
            if desktop_file.exists():
                return desktop_file

        return None

    def generate_desktop_content(
        self,
        comment: str = "",
        categories: list[str] | None = None,
        mime_types: list[str] | None = None,
        keywords: list[str] | None = None,
        startup_notify: bool = True,
        no_display: bool = False,
        terminal: bool = False,
    ) -> str:
        """Generate desktop entry file content.

        Args:
            comment: Application description
            categories: List of application categories
            mime_types: List of MIME types the app can handle
            keywords: List of keywords for searching
            startup_notify: Whether to show startup notification
            no_display: Whether to hide from application menus
            terminal: Whether app should run in terminal

        Returns:
            Desktop file content as string

        """
        # Auto-detect browser applications and set appropriate defaults
        is_browser = self._is_browser_app()

        if categories is None:
            categories = (
                list(DESKTOP_BROWSER_CATEGORIES)
                if is_browser
                else list(DESKTOP_DEFAULT_CATEGORIES)
            )

        if mime_types is None:
            mime_types = list(DESKTOP_BROWSER_MIME_TYPES) if is_browser else []

        if keywords is None:
            keywords = list(DESKTOP_BROWSER_KEYWORDS) if is_browser else []

        # Sanitize values and use proper paths
        # For browsers, keep the original name format; for others, format as title
        if is_browser:
            display_name = self.app_name
        else:
            display_name = (
                sanitize_filename(self.app_name)
                .replace("-", " ")
                .replace("_", " ")
                .title()
            )
        comment = comment or f"{display_name} AppImage Application"

        # Use absolute paths for Exec and Icon
        # Add %u parameter for browsers to handle URLs
        exec_path = str(self.appimage_path.resolve())
        if is_browser:
            exec_path += f" {DESKTOP_BROWSER_EXEC_PARAM}"

        # Determine icon path - prefer provided icon_path, fallback to configured icon directory
        if self.icon_path and self.icon_path.exists():
            icon_value = str(self.icon_path.resolve())
        else:
            # Try to find icon in configured icon directory
            icon_dir = self.global_config["directory"]["icon"]
            potential_icon_extensions = list(DESKTOP_ICON_EXTENSIONS)
            icon_value = display_name.lower()  # fallback to name

            for ext in potential_icon_extensions:
                potential_icon = icon_dir / f"{self.app_name}{ext}"
                if potential_icon.exists():
                    icon_value = str(potential_icon.resolve())
                    break

        # Build desktop file content
        content_lines = [
            DESKTOP_SECTION_HEADER,
            f"Version={DESKTOP_FILE_VERSION}",
            f"Name={display_name}",
            f"Comment={comment}",
            f"Exec={exec_path}",
            f"Icon={icon_value}",
            f"Type={DESKTOP_FILE_TYPE}",
            f"Categories={';'.join(categories)};",
        ]

        if mime_types:
            content_lines.append(f"MimeType={';'.join(mime_types)};")

        if keywords:
            content_lines.append(f"Keywords={';'.join(keywords)};")

        if startup_notify:
            content_lines.append("StartupNotify=true")

        if no_display:
            content_lines.append("NoDisplay=true")

        if terminal:
            content_lines.append("Terminal=true")

        # Add newline at end
        content_lines.append("")

        return "\n".join(content_lines)

    def create_desktop_file(
        self,
        target_dir: Path | None = None,
        comment: str = "",
        categories: list[str] | None = None,
        mime_types: list[str] | None = None,
        keywords: list[str] | None = None,
        **kwargs: Any,
    ) -> Path:
        """Create or update desktop entry file when content changes.

        This method automatically detects when desktop files need updating by comparing
        the existing content with what would be generated. Updates only when there are
        actual changes to important fields like icon paths, exec paths, MIME types, etc.

        Args:
            target_dir: Directory to create desktop file in (defaults to user dir)
            comment: Application description
            categories: List of application categories
            mime_types: List of MIME types the app can handle
            keywords: List of keywords for searching
            **kwargs: Additional desktop entry options

        Returns:
            Path to desktop file (existing, newly created, or updated)

        Raises:
            OSError: If file creation fails

        """
        if target_dir is None:
            target_dir = Path.home() / ".local" / "share" / "applications"

        # Ensure target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        desktop_file_path = target_dir / self.desktop_filename

        # Generate new content
        new_content = self.generate_desktop_content(
            comment=comment,
            categories=categories,
            mime_types=mime_types,
            keywords=keywords,
            **kwargs,
        )

        # Check if file exists and if update is needed
        needs_update = True
        if desktop_file_path.exists():
            try:
                with open(desktop_file_path, encoding="utf-8") as f:
                    existing_content = f.read()

                # Compare key fields that matter for functionality
                needs_update = self._should_update_desktop_file(
                    existing_content, new_content
                )

                if needs_update:
                    logger.debug(
                        f"Desktop file content changed, updating: {desktop_file_path}"
                    )
                else:
                    logger.debug(
                        "Desktop file unchanged, skipping: %s",
                        desktop_file_path,
                    )
                    return desktop_file_path
            except OSError:
                # If we can't read the existing file, create a new one
                needs_update = True

        # Only write file if update is needed
        if needs_update:
            try:
                with open(desktop_file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                # Make file executable
                os.chmod(desktop_file_path, 0o755)

                if desktop_file_path.exists():
                    logger.info(
                        "🖥️  Updated desktop entry: %s", desktop_file_path.name
                    )
                else:
                    logger.info(
                        "🖥️  Created desktop entry: %s", desktop_file_path.name
                    )
                return desktop_file_path

            except OSError as e:
                logger.error(
                    f"Failed to write desktop file {desktop_file_path}: {e}",
                    exc_info=True,
                )
                raise
        else:
            # File exists and is up to date, just return the path
            return desktop_file_path

    def update_desktop_file(
        self,
        comment: str = "",
        categories: list[str] | None = None,
        mime_types: list[str] | None = None,
        keywords: list[str] | None = None,
        **kwargs: Any,
    ) -> Path | None:
        """Update existing desktop entry file.

        Args:
            comment: Application description
            categories: List of application categories
            mime_types: List of MIME types the app can handle
            keywords: List of keywords for searching
            **kwargs: Additional desktop entry options

        Returns:
            Path to updated desktop file or None if not found

        """
        existing_file = self.find_existing_desktop_file()
        if not existing_file:
            logger.warning(
                "No existing desktop file found for %s", self.app_name
            )
            return None

        # Update by recreating the file
        try:
            content = self.generate_desktop_content(
                comment=comment,
                categories=categories,
                mime_types=mime_types,
                keywords=keywords,
                **kwargs,
            )

            with open(existing_file, "w", encoding="utf-8") as f:
                f.write(content)

            logger.debug("Updated desktop file: %s", existing_file)
            return existing_file

        except OSError as e:
            logger.error(
                "Failed to update desktop file %s: %s",
                existing_file,
                e,
                exc_info=True,
            )
            return None

    def remove_desktop_file(self) -> bool:
        """Remove desktop entry file.

        Returns:
            True if file was removed, False if not found

        """
        existing_file = self.find_existing_desktop_file()
        if not existing_file:
            logger.debug("No desktop file found for %s", self.app_name)
            return False

        try:
            existing_file.unlink()
            logger.debug("Removed desktop file: %s", existing_file)
            return True
        except OSError as e:
            logger.error(
                "Failed to remove desktop file %s: %s",
                existing_file,
                e,
                exc_info=True,
            )
            return False

    def _is_browser_app(self) -> bool:
        """Check if this application is a browser based on its name.

        Returns:
            True if the app is detected as a browser

        """
        app_name_lower = self.app_name.lower()
        return any(
            browser in app_name_lower for browser in DESKTOP_BROWSER_NAMES
        )

    def _get_browser_mime_types(self) -> list[str]:
        """Get standard browser MIME types for web browsers.

        Returns:
            List of MIME types that browsers should handle

        """
        return [
            "text/html",
            "text/xml",
            "application/xhtml+xml",
            "application/xml",
            "application/rss+xml",
            "application/rdf+xml",
            "image/gif",
            "image/jpeg",
            "image/png",
            "x-scheme-handler/http",
            "x-scheme-handler/https",
            "x-scheme-handler/ftp",
            "x-scheme-handler/chrome",
            "video/webm",
            "application/x-xpinstall",
        ]

    def _should_update_desktop_file(
        self, existing_content: str, new_content: str
    ) -> bool:
        """Check if desktop file should be updated by comparing key fields.

        Args:
            existing_content: Current desktop file content
            new_content: New desktop file content that would be written

        Returns:
            True if desktop file should be updated

        """

        def parse_desktop_fields(content: str) -> dict[str, str]:
            """Parse key fields from desktop file content."""
            fields = {}
            for line in content.split("\n"):
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    fields[key.strip()] = value.strip()
            return fields

        existing_fields = parse_desktop_fields(existing_content)
        new_fields = parse_desktop_fields(new_content)

        # Key fields that should trigger an update if changed
        important_fields = [
            "Exec",  # AppImage path or parameters
            "Icon",  # Icon path
            "Name",  # Display name
            "Comment",  # Description
            "Categories",  # Application categories
            "MimeType",  # MIME type associations
            "Keywords",  # Search keywords
        ]

        for field in important_fields:
            if existing_fields.get(field) != new_fields.get(field):
                logger.debug("Desktop file field changed: %s", field)
                logger.debug("  Old: %s", existing_fields.get(field))
                logger.debug("  New: %s", new_fields.get(field))
                return True

        return False

    def is_installed(self) -> bool:
        """Check if desktop entry is installed.

        Returns:
            True if desktop file exists

        """
        return self.find_existing_desktop_file() is not None

    def validate_desktop_file(self, desktop_file: Path) -> list[str]:
        """Validate desktop file format and content.

        Args:
            desktop_file: Path to desktop file to validate

        Returns:
            List of validation errors (empty if valid)

        """
        errors = []

        if not desktop_file.exists():
            errors.append("Desktop file does not exist")
            return errors

        try:
            with open(desktop_file, encoding="utf-8") as f:
                content = f.read()

            lines = content.split("\n")

            # Check for required header
            if not lines or lines[0] != "[Desktop Entry]":
                errors.append("Missing or invalid [Desktop Entry] header")

            # Check for required fields
            required_fields = ["Name", "Exec", "Type"]
            found_fields = set()

            for line in lines:
                if "=" in line:
                    key = line.split("=", 1)[0].strip()
                    found_fields.add(key)

            for field in required_fields:
                if field not in found_fields:
                    errors.append(f"Missing required field: {field}")

            # Check if AppImage file exists
            for line in lines:
                if line.startswith("Exec="):
                    exec_path = line.split("=", 1)[1].strip()
                    if not Path(exec_path).exists():
                        errors.append(
                            f"AppImage file does not exist: {exec_path}"
                        )

        except OSError as e:
            errors.append(f"Failed to read desktop file: {e}")

        return errors

    def refresh_desktop_database(self) -> bool:
        """Refresh desktop database to make new entries available.

        Returns:
            True if refresh was successful

        """
        try:
            # Try to run update-desktop-database
            result = shutil.which("update-desktop-database")
            if result:
                import subprocess

                user_dir = Path.home() / ".local" / "share" / "applications"
                subprocess.run(
                    ["update-desktop-database", str(user_dir)],
                    check=False,
                    capture_output=True,
                )
                logger.debug("Desktop database refreshed")
                return True
        except Exception as e:
            logger.debug("Could not refresh desktop database: %s", e)

        return False


def create_desktop_entry_for_app(
    app_name: str,
    appimage_path: Path,
    icon_path: Path | None = None,
    comment: str = "",
    categories: list[str] | None = None,
    config_manager: ConfigManager | None = None,
    **kwargs: Any,
) -> Path:
    """Convenience function to create or update desktop entry for an app.

    This function automatically detects when desktop entries need updating by comparing
    the existing content with what would be generated. Updates only when there are
    actual changes to important fields like icon paths, exec paths, MIME types, etc.

    Args:
        app_name: Name of the application (will be normalized to lowercase)
        appimage_path: Path to the AppImage file (should use clean name without version)
        icon_path: Optional path to icon file
        comment: Application description
        categories: List of application categories
        config_manager: Configuration manager for directory paths
        **kwargs: Additional desktop entry options

    Returns:
        Path to desktop file (existing, newly created, or updated)

    """
    desktop_entry = DesktopEntry(
        app_name, appimage_path, icon_path, config_manager
    )
    return desktop_entry.create_desktop_file(
        comment=comment, categories=categories, **kwargs
    )


def remove_desktop_entry_for_app(
    app_name: str, config_manager: ConfigManager | None = None
) -> bool:
    """Convenience function to remove desktop entry for an app.

    Args:
        app_name: Name of the application
        config_manager: Configuration manager for directory paths

    Returns:
        True if desktop file was removed

    """
    # Create a dummy DesktopEntry to use the removal logic
    dummy_path = Path("/dev/null")
    desktop_entry = DesktopEntry(
        app_name, dummy_path, config_manager=config_manager
    )
    return desktop_entry.remove_desktop_file()
