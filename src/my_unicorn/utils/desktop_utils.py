"Utility functions for desktop entry handling."

import re
from pathlib import Path


def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from filename for safe filesystem use.

    Args:
        filename: Filename to sanitize

    Returns:
        Sanitized filename safe for filesystem operations

    """
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "", filename)

    # Remove control characters
    sanitized = "".join(char for char in sanitized if ord(char) >= 32)

    # Limit length
    if len(sanitized) > 255:
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        max_name_len = 255 - len(ext)
        sanitized = name[:max_name_len] + ext

    return sanitized.strip()


def create_desktop_entry_name(app_name: str) -> str:
    """Create desktop entry filename from app name (e.g., 'app.desktop').

    Args:
        app_name: Application name

    Returns:
        Desktop entry filename (e.g., 'myapp.desktop')

    """
    # Normalize to lowercase and clean up the name
    name = app_name.lower().strip()

    # Remove special characters except alphanumeric, hyphens, and underscores
    name = re.sub(r"[^\w-]", "", name)

    # Replace multiple consecutive hyphens/underscores with single hyphen
    name = re.sub(r"[-_]+", "-", name)

    # Remove leading/trailing hyphens
    name = name.strip("-")

    # Ensure we have a valid name
    if not name:
        name = "appimage"

    return f"{name}.desktop"
