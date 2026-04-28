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

import shutil
import subprocess
from pathlib import Path
from typing import Any

from my_unicorn.config import ConfigManager
from my_unicorn.constants import (
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
from my_unicorn.logger import get_logger
from my_unicorn.utils.desktop_utils import (
    create_desktop_entry_name,
    sanitize_filename,
)

logger = get_logger(__name__)


def is_browser_app(app_name: str) -> bool:
    """Check if an application is a browser based on its name.

    Args:
        app_name: Name of the application.

    Returns:
        True if the app is detected as a browser.

    """
    app_name_lower = app_name.lower()
    return any(browser in app_name_lower for browser in DESKTOP_BROWSER_NAMES)


def should_update_desktop_file(
    existing_content: str, new_content: str
) -> bool:
    """Check if a desktop file should be updated by comparing key fields.

    Args:
        existing_content: Current desktop file content.
        new_content: New desktop file content that would be written.

    Returns:
        True if the desktop file should be updated.

    """

    def parse_desktop_fields(content: str) -> dict[str, str]:
        """Parse key fields from desktop file content."""
        fields: dict[str, str] = {}
        for line in content.split("\n"):
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                fields[key.strip()] = value.strip()
        return fields

    existing_fields = parse_desktop_fields(existing_content)
    new_fields = parse_desktop_fields(new_content)

    # Key fields that should trigger an update if changed
    important_fields = [
        "Exec",
        "Icon",
        "Name",
        "Comment",
        "Categories",
        "MimeType",
        "Keywords",
        "StartupNotify",
        "NoDisplay",
        "Terminal",
    ]

    for field in important_fields:
        if existing_fields.get(field) != new_fields.get(field):
            logger.debug("Desktop file field changed: %s", field)
            logger.debug("  Old: %s", existing_fields.get(field))
            logger.debug("  New: %s", new_fields.get(field))
            return True

    return False


def validate_desktop_file(desktop_file: Path) -> list[str]:
    """Validate desktop file format and content.

    Args:
        desktop_file: Path to desktop file to validate.

    Returns:
        List of validation errors (empty if valid).

    """
    errors: list[str] = []

    if not desktop_file.exists():
        errors.append("Desktop file does not exist")
        return errors

    try:
        with desktop_file.open(encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")

        # Check for required header
        if not lines or lines[0] != "[Desktop Entry]":
            errors.append("Missing or invalid [Desktop Entry] header")

        # Check for required fields
        required_fields = ["Name", "Exec", "Type"]
        found_fields: set[str] = set()

        for line in lines:
            if "=" in line:
                key = line.split("=", 1)[0].strip()
                found_fields.add(key)

        for field in required_fields:
            if field not in found_fields:
                errors.append(f"Missing required field: {field}")

        # Check if the AppImage file referenced in Exec actually exists
        for line in lines:
            if line.startswith("Exec="):
                # Strip any trailing arguments (e.g. %u)
                exec_value = line.split("=", 1)[1].strip()
                exec_path = exec_value.split()[0]
                if not Path(exec_path).exists():
                    errors.append(f"AppImage file does not exist: {exec_path}")

    except OSError as e:
        errors.append(f"Failed to read desktop file: {e}")

    return errors


class DesktopEntry:
    """Manages .desktop entry files for AppImage applications."""

    def __init__(
        self,
        app_name: str,
        appimage_path: Path,
        icon_path: Path | None = None,
        config_manager: ConfigManager | None = None,
    ) -> None:
        """Initialize desktop entry manager.

        Args:
            app_name: Name of the application.
            appimage_path: Path to the AppImage file (should use a clean name
                without a version suffix).
            icon_path: Optional path to icon file.
            config_manager: Configuration manager for directory paths.

        """
        self.app_name = app_name.lower()  # Normalize to lowercase
        self.appimage_path = appimage_path
        self.icon_path = icon_path
        self.desktop_filename = create_desktop_entry_name(self.app_name)
        self.config_manager = config_manager or ConfigManager()
        self.global_config = self.config_manager.load_global_config()

    def get_desktop_dirs(self) -> list[Path]:
        """Return desktop entry directories to check, highest priority first.

        Returns:
            List of desktop directory paths.

        """
        dirs: list[Path] = []

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
        """Find an existing desktop file for this application.

        Returns:
            Path to the existing desktop file, or None if not found.

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
            comment: Application description.
            categories: List of application categories.
            mime_types: List of MIME types the app can handle.
            keywords: List of keywords for searching.
            startup_notify: Whether to show a startup notification.
            no_display: Whether to hide the entry from application menus.
            terminal: Whether the app should run in a terminal.

        Returns:
            Desktop file content as a string.

        """
        is_browser = is_browser_app(self.app_name)

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

        # Build display name
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

        # Exec path — browsers receive a %u URL argument
        exec_path = str(self.appimage_path.resolve())
        if is_browser:
            exec_path += f" {DESKTOP_BROWSER_EXEC_PARAM}"

        # Icon: prefer the provided icon_path, then fall back to the icon dir
        if self.icon_path and self.icon_path.exists():
            icon_value = str(self.icon_path.resolve())
        else:
            icon_dir = self.global_config["directory"]["icon"]
            icon_value = display_name.lower()  # ultimate fallback
            for ext in list(DESKTOP_ICON_EXTENSIONS):
                potential_icon = icon_dir / f"{self.app_name}{ext}"
                if potential_icon.exists():
                    icon_value = str(potential_icon.resolve())
                    break

        # Assemble content
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

        content_lines.append("")  # trailing newline
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
        """Create or update a desktop entry file when content changes.

        Automatically detects whether the existing file differs from what
        would be generated and only writes when there are real changes.

        Args:
            target_dir: Directory to create the desktop file in
                (defaults to ``~/.local/share/applications``).
            comment: Application description.
            categories: List of application categories.
            mime_types: List of MIME types the app can handle.
            keywords: List of keywords for searching.
            **kwargs: Additional desktop entry options passed to
                :meth:`generate_desktop_content`.

        Returns:
            Path to the desktop file (existing, newly created, or updated).

        Raises:
            OSError: If file creation fails.

        """
        if target_dir is None:
            target_dir = Path.home() / ".local" / "share" / "applications"

        target_dir.mkdir(parents=True, exist_ok=True)
        desktop_file_path = target_dir / self.desktop_filename

        new_content = self.generate_desktop_content(
            comment=comment,
            categories=categories,
            mime_types=mime_types,
            keywords=keywords,
            **kwargs,
        )

        needs_update = True
        if desktop_file_path.exists():
            try:
                existing_content = desktop_file_path.read_text(
                    encoding="utf-8"
                )
                needs_update = should_update_desktop_file(
                    existing_content, new_content
                )
                if needs_update:
                    logger.debug(
                        "Desktop file content changed, updating: %s",
                        desktop_file_path,
                    )
                else:
                    logger.debug(
                        "Desktop file unchanged, skipping: %s",
                        desktop_file_path,
                    )
                    return desktop_file_path
            except OSError:
                needs_update = True

        if needs_update:
            try:
                desktop_file_path.write_text(new_content, encoding="utf-8")
                desktop_file_path.chmod(0o755)
                logger.debug(
                    "️Desktop entry written: %s", desktop_file_path.name
                )
            except OSError as e:
                logger.exception(
                    "Failed to write desktop file %s: %s",
                    desktop_file_path,
                    e,
                )
                raise

        return desktop_file_path

    def update_desktop_file(
        self,
        comment: str = "",
        categories: list[str] | None = None,
        mime_types: list[str] | None = None,
        keywords: list[str] | None = None,
        **kwargs: Any,
    ) -> Path | None:
        """Update an existing desktop entry file.

        Args:
            comment: Application description.
            categories: List of application categories.
            mime_types: List of MIME types the app can handle.
            keywords: List of keywords for searching.
            **kwargs: Additional desktop entry options passed to
                :meth:`generate_desktop_content`.

        Returns:
            Path to the updated desktop file, or None if no file was found.

        """
        existing_file = self.find_existing_desktop_file()
        if not existing_file:
            logger.warning(
                "No existing desktop file found for %s", self.app_name
            )
            return None

        try:
            content = self.generate_desktop_content(
                comment=comment,
                categories=categories,
                mime_types=mime_types,
                keywords=keywords,
                **kwargs,
            )
            existing_file.write_text(content, encoding="utf-8")
            logger.debug("Updated desktop file: %s", existing_file)
            return existing_file
        except OSError as e:
            logger.exception(
                "Failed to update desktop file %s: %s",
                existing_file,
                e,
            )
            return None

    def remove_desktop_file(self) -> bool:
        """Remove the desktop entry file.

        Returns:
            True if the file was removed, False if it was not found.

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
            logger.exception(
                "Failed to remove desktop file %s: %s",
                existing_file,
                e,
            )
            return False

    def is_installed(self) -> bool:
        """Return True if a desktop entry file already exists."""
        return self.find_existing_desktop_file() is not None

    def validate(self, desktop_file: Path) -> list[str]:
        """Validate a desktop file's format and content.

        Args:
            desktop_file: Path to the desktop file to validate.

        Returns:
            List of validation errors (empty if valid).

        """
        return validate_desktop_file(desktop_file)

    def refresh_desktop_database(self) -> bool:
        """Refresh the desktop database so new entries become available.

        Returns:
            True if the refresh succeeded.

        """
        try:
            cmd = shutil.which("update-desktop-database")
            if cmd:
                user_dir = Path.home() / ".local" / "share" / "applications"
                subprocess.run(
                    [cmd, str(user_dir)],
                    check=False,
                    capture_output=True,
                )
                logger.debug("Desktop database refreshed")
                return True
        except Exception as e:
            logger.debug("Could not refresh desktop database: %s", e)

        return False

    @staticmethod
    def remove_desktop_entry_for_app(
        app_name: str,
        config_manager: ConfigManager | None = None,
    ) -> bool:
        """Remove the desktop entry for an AppImage application.

        Args:
            app_name: Name of the application.
            config_manager: Configuration manager for directory paths.

        Returns:
            True if the desktop file was removed.

        """
        dummy_path = Path("/dev/null")
        desktop_entry = DesktopEntry(
            app_name,
            dummy_path,
            config_manager=config_manager,
        )
        return desktop_entry.remove_desktop_file()
