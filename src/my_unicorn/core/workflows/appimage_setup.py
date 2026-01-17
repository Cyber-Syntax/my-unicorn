"""AppImage setup workflow utilities for install and update operations.

This module provides unified setup operations including file renaming,
icon extraction, and desktop entry creation.
"""

from pathlib import Path
from typing import Any

from my_unicorn.core.desktop_entry import DesktopEntry
from my_unicorn.core.file_ops import FileOperations, extract_icon_from_appimage
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


def rename_appimage(
    *,
    appimage_path: Path,
    app_name: str,
    app_config: dict[str, Any],
    catalog_entry: dict[str, Any] | None,
    storage_service: FileOperations,
) -> Path:
    """Rename AppImage file according to configuration.

    Unified rename logic for both install and update operations.
    Handles both catalog and URL-based installations.

    Args:
        appimage_path: Current path to AppImage file
        app_name: Application name
        app_config: App configuration dictionary
        catalog_entry: Catalog entry if available (optional)
        storage_service: File operations service for rename operations

    Returns:
        Path to renamed AppImage

    """
    # Get rename configuration
    # For catalog installs, use catalog entry; for URL installs use app config
    rename_to = app_name  # fallback

    if catalog_entry and catalog_entry.get("appimage", {}).get("rename"):
        rename_to = catalog_entry["appimage"]["rename"]
    elif app_config.get("appimage", {}).get("rename"):
        rename_to = app_config["appimage"]["rename"]

    # Clean base name and perform rename
    clean_name = storage_service.get_clean_appimage_name(rename_to)
    renamed_path = storage_service.rename_appimage(appimage_path, clean_name)

    logger.debug(
        "Renamed AppImage: %s -> %s", appimage_path.name, renamed_path.name
    )

    return renamed_path


async def setup_appimage_icon(
    *,
    appimage_path: Path,
    app_name: str,
    icon_dir: Path,
    app_config: dict[str, Any],
    catalog_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Extract icon from AppImage.

    Unified icon extraction logic for both install and update operations.

    Args:
        appimage_path: Path to AppImage file
        app_name: Application name
        icon_dir: Directory where icons should be saved
        app_config: App configuration dictionary
        catalog_entry: Catalog entry if available (optional)

    Returns:
        Icon extraction result dictionary with keys:
            - success (bool): Whether extraction succeeded
            - source (str): Icon source ("extraction", "none")
            - icon_path (str | None): Path to extracted icon
            - path (str | None): Alternative path key for update compatibility
            - installed (bool): Whether icon was installed
            - extraction (bool): Whether extraction was attempted
            - name (str): Icon filename
            - error (str): Error message if extraction failed

    """
    # Check if icon extraction is enabled
    extraction_enabled = True
    icon_filename = f"{app_name}.png"  # Default

    if catalog_entry and catalog_entry.get("icon"):
        catalog_icon = catalog_entry.get("icon", {})
        if isinstance(catalog_icon, dict):
            extraction_enabled = catalog_icon.get("extraction", True)
            icon_filename = catalog_icon.get("filename", icon_filename)
    elif app_config.get("icon"):
        icon_cfg = app_config.get("icon", {})
        extraction_enabled = icon_cfg.get("extraction", True)
        icon_filename = icon_cfg.get("filename", icon_filename)

    if not extraction_enabled:
        return {
            "success": False,
            "source": "none",
            "icon_path": None,
            "path": None,
            "installed": False,
            "extraction": False,
            "name": icon_filename,
        }

    try:
        # Extract icon using file operations
        icon_path = await extract_icon_from_appimage(
            appimage_path=appimage_path,
            icon_dir=icon_dir,
            app_name=app_name,
            icon_filename=icon_filename,
        )
    except (OSError, PermissionError):
        logger.exception("Icon extraction failed for %s", app_name)
        return {
            "success": False,
            "source": "none",
            "icon_path": None,
            "path": None,
            "installed": False,
            "extraction": True,
            "name": icon_filename,
            "error": "Extraction error",
        }
    else:
        if icon_path:
            # Ensure icon_path is a Path object for .name access
            icon_path_obj = (
                Path(icon_path) if isinstance(icon_path, str) else icon_path
            )
            return {
                "success": True,
                "source": "extraction",
                "icon_path": str(icon_path_obj),
                "path": str(icon_path_obj),
                "installed": True,
                "extraction": True,
                "name": icon_filename,  # Use configured filename
            }

        return {
            "success": False,
            "source": "none",
            "icon_path": None,
            "path": None,
            "installed": False,
            "extraction": True,
            "name": icon_filename,
        }


def create_desktop_entry(
    *,
    appimage_path: Path,
    app_name: str,
    icon_result: dict[str, Any],
    config_manager: Any,  # noqa: ANN401
) -> dict[str, Any]:
    """Create desktop entry for application.

    Unified desktop entry creation logic for install and update.

    Args:
        appimage_path: Path to installed AppImage
        app_name: Application name
        icon_result: Icon extraction result from setup_appimage_icon()
        config_manager: Configuration manager instance

    Returns:
        Desktop entry creation result dictionary with keys:
            - success (bool): Whether creation succeeded
            - desktop_path (str): Path to created desktop file
            - error (str): Error message if creation failed

    """
    try:
        # Get icon path from result
        icon_path = None
        if icon_result.get("icon_path"):
            icon_path = Path(icon_result["icon_path"])
        elif icon_result.get("path"):
            icon_path = Path(icon_result["path"])

        # Create desktop entry
        desktop = DesktopEntry(
            app_name=app_name,
            appimage_path=appimage_path,
            icon_path=icon_path,
            config_manager=config_manager,
        )

        desktop_path = desktop.create_desktop_file()

        return {
            "success": True,
            "desktop_path": str(desktop_path),
        }

    except Exception:
        logger.exception("Failed to create desktop entry for %s", app_name)
        return {
            "success": False,
            "error": "Desktop entry creation failed",
        }
