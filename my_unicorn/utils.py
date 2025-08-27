"""Utility functions for my-unicorn AppImage installer.

This module provides common utility functions used across the application
including path operations, string manipulation, and validation helpers.
"""

import platform
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# TODO: Some of these functions are not used in the codebase,
# so determine which ones are necessary and remove the rest.


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem

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


# TODO: We probably not need to use this because most of the appimages
# we might keep arm64 for macos support for future
# windows and linux would be amd64
def get_system_architecture() -> str:
    """Get system architecture string.

    Returns:
        Architecture string (x86_64, aarch64, etc.)

    """
    machine = platform.machine().lower()

    # Normalize architecture names
    arch_mapping = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "arm64": "aarch64",
        "armv7l": "armhf",
    }

    return arch_mapping.get(machine, machine)


def format_bytes(size: int) -> str:
    """Format byte size in human readable format.

    Args:
        size: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB")

    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def is_valid_github_repo(repo: str) -> bool:
    """Check if string is a valid GitHub repository format.

    Args:
        repo: Repository string to validate

    Returns:
        True if valid GitHub repo format

    """
    # Check owner/repo format
    if "/" in repo and not repo.startswith("http"):
        parts = repo.split("/")
        if len(parts) == 2 and all(part.strip() for part in parts):
            # Basic validation for GitHub username/repo rules
            for part in parts:
                if not re.match(r"^[a-zA-Z0-9._-]+$", part):
                    return False
            return True

    # Check full GitHub URL
    if repo.startswith("http"):
        try:
            parsed = urlparse(repo)
            if parsed.hostname == "github.com":
                path_parts = parsed.path.strip("/").split("/")
                if len(path_parts) >= 2:
                    return all(part.strip() for part in path_parts[:2])
        except Exception:
            pass

    return False


def expand_template(template: str, variables: dict[str, Any]) -> str:
    """Expand template string with variables.

    Args:
        template: Template string with {variable} placeholders
        variables: Dictionary of variables to substitute

    Returns:
        Expanded template string

    """
    try:
        return template.format(**variables)
    except (KeyError, ValueError):
        return template


def extract_version_from_package_string(package_string: str) -> str | None:
    """Extract version from package identifier string.

    Handles formats like:
    - "@standardnotes/desktop@3.198.1" -> "3.198.1"
    - "package@1.2.3" -> "1.2.3"
    - "v1.2.3" -> "1.2.3"
    - "1.2.3" -> "1.2.3"

    Args:
        package_string: Package string that may contain version

    Returns:
        Extracted version string or None if not found

    """
    if not package_string:
        return None

    # Handle package@version format
    if "@" in package_string:
        # Split by @ and take the last part (version)
        parts = package_string.split("@")
        if len(parts) >= 2:
            version_part = parts[-1]
            # Clean up the version part
            version_part = version_part.strip()
            if version_part:
                return sanitize_version_string(version_part)

    # Handle direct version strings
    return sanitize_version_string(package_string)


def sanitize_version_string(version: str) -> str:
    """Sanitize version string by removing invalid characters and prefixes.

    Args:
        version: Raw version string

    Returns:
        Sanitized version string

    """
    if not version:
        return ""

    # Remove common prefixes
    version = version.lstrip("v")

    # Remove any remaining @ symbols that might be present
    version = version.replace("@", "")

    # Remove quotes and other problematic characters for JSON
    version = version.strip("\"'")

    # Remove any trailing/leading whitespace
    version = version.strip()

    return version


def validate_version_string(version: str) -> bool:
    """Validate version string format.

    Args:
        version: Version string to validate (should be pre-sanitized)

    Returns:
        True if valid version format

    """
    if not version:
        return False

    # The version should already be sanitized, but ensure no prefixes
    version = version.lstrip("v")

    # Check semantic version pattern (major.minor.patch with optional pre-release)
    pattern = r"^\d+(\.\d+)*(-[a-zA-Z0-9.-]+)?$"
    return bool(re.match(pattern, version))


def extract_and_validate_version(package_string: str) -> str | None:
    """Extract and validate version from package string.

    Combines extraction, sanitization, and validation in one function.

    Args:
        package_string: Package string that may contain version

    Returns:
        Valid version string or None if extraction/validation fails

    """
    extracted_version = extract_version_from_package_string(package_string)
    if extracted_version and validate_version_string(extracted_version):
        return extracted_version
    return None


def create_desktop_entry_name(app_name: str) -> str:
    """Create desktop entry name from app name.

    Args:
        app_name: Application name (will be normalized to lowercase)

    Returns:
        Desktop entry filename (e.g., "siyuan.desktop", "qownnotes.desktop")

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


def is_appimage_file(filename: str) -> bool:
    """Check if filename is an AppImage.

    Args:
        filename: Filename to check

    Returns:
        True if filename ends with .AppImage

    """
    return filename.lower().endswith(".appimage")


def extract_version_from_filename(filename: str) -> str | None:
    """Extract version from AppImage filename.

    Args:
        filename: AppImage filename

    Returns:
        Extracted version or None if not found

    """
    # Common version patterns in filenames
    patterns = [
        r"v?(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?)",  # v1.2.3 or 1.2.3
        r"(\d+\.\d+(?:\.\d+)?)",  # 1.2 or 1.2.3
    ]

    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            version = match.group(1)
            # Strip .AppImage/.appimage if present at end of version
            if version.lower().endswith(".appimage"):
                version = version[:-9]
            return version

    return None


def safe_path_join(base: Path, *parts: str) -> Path:
    """Safely join path parts, preventing directory traversal.

    Args:
        base: Base path
        parts: Path parts to join

    Returns:
        Safely joined path

    Raises:
        ValueError: If path traversal is detected

    """
    result = base

    for part in parts:
        if ".." in part or part.startswith("/"):
            raise ValueError(f"Unsafe path component: {part}")
        result = result / part

    # Ensure result is within base directory
    try:
        result.resolve().relative_to(base.resolve())
    except ValueError:
        raise ValueError("Path traversal detected")

    return result


def parse_content_disposition(header: str) -> str | None:
    """Parse filename from Content-Disposition header.

    Args:
        header: Content-Disposition header value

    Returns:
        Extracted filename or None

    """
    if not header:
        return None

    # Look for filename parameter
    match = re.search(r"filename\*?=([^;]+)", header)
    if match:
        filename = match.group(1).strip("\"'")
        # Handle RFC 5987 encoding
        if filename.startswith("UTF-8''"):
            filename = filename[7:]
        return filename

    return None


def is_safe_filename(filename: str) -> bool:
    """Check if filename is safe for filesystem operations.

    Args:
        filename: Filename to check

    Returns:
        True if filename is safe

    """
    if not filename or filename in (".", ".."):
        return False

    # Check for invalid characters
    invalid_chars = '<>:"/\\|?*'
    if any(char in filename for char in invalid_chars):
        return False

    # Check for control characters
    if any(ord(char) < 32 for char in filename):
        return False

    return True


def check_icon_exists(icon_name: str, icon_dir: Path) -> bool:
    """Check if icon file already exists.

    Args:
        icon_name: Name of the icon file
        icon_dir: Directory where icons are stored

    Returns:
        True if icon file exists

    """
    if not icon_name or not icon_dir:
        return False

    icon_path = icon_dir / icon_name
    return icon_path.exists() and icon_path.is_file()


def get_icon_path(icon_name: str, icon_dir: Path) -> Path:
    """Get the full path to an icon file.

    Args:
        icon_name: Name of the icon file
        icon_dir: Directory where icons are stored

    Returns:
        Full path to the icon file

    """
    return icon_dir / icon_name


# API Progress Tracking Helpers


def simplify_endpoint_for_display(endpoint: str) -> str:
    """Simplify API endpoint URL for progress display.

    Args:
        endpoint: Full API endpoint URL

    Returns:
        Simplified endpoint name for display

    """
    if not endpoint:
        return "api"

    # Extract meaningful part from URL
    if "://" in endpoint:
        # Full URL - extract path
        try:
            from urllib.parse import urlparse

            parsed = urlparse(endpoint)
            path = parsed.path.strip("/")
            if path:
                # Get the last meaningful part
                parts = path.split("/")
                meaningful_parts = [p for p in parts if p and not p.isdigit()]
                if meaningful_parts:
                    return meaningful_parts[-1]
        except Exception:
            pass

    # Handle path-only endpoints
    if "/" in endpoint:
        parts = endpoint.strip("/").split("/")
        # Remove query parameters
        last_part = parts[-1].split("?")[0] if parts else "api"
        return last_part if last_part else "api"

    # Remove query parameters from simple strings
    return endpoint.split("?")[0] if "?" in endpoint else endpoint


def calculate_api_batch_size(total_requests: int, target_updates: int = 20) -> int:
    """Calculate optimal batch size for API progress updates.

    Args:
        total_requests: Total number of API requests to make
        target_updates: Target number of progress updates (default: 20)

    Returns:
        Optimal batch size for progress updates

    """
    if total_requests <= target_updates:
        return 1

    batch_size = total_requests // target_updates
    return max(1, batch_size)


def format_api_progress_description(endpoint: str, completed: int, total: int) -> str:
    """Format API progress description with consistent styling.

    Args:
        endpoint: API endpoint being fetched
        completed: Number of completed requests
        total: Total number of requests

    Returns:
        Formatted progress description

    """
    simplified_name = simplify_endpoint_for_display(endpoint)
    return f"🌐 Fetching {simplified_name}... ({completed}/{total})"
