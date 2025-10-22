"""Utility functions and helpers for my-unicorn.

This package provides common utility functions including:
- File and path operations (sanitize_filename, format_bytes)
- Version string handling (extract_and_validate_version)
- Desktop entry creation (create_desktop_entry_name)
- Checksum file detection (is_checksum_file, is_appimage_file)
- Update display functions (display_update_summary, display_update_error)
"""

# Import all utility functions from utils.py
from .utils import (
    BYTES_PER_UNIT,
    CHECKSUM_FILE_PATTERNS,
    SPECIFIC_CHECKSUM_EXTENSIONS,
    create_desktop_entry_name,
    extract_and_validate_version,
    extract_version_from_package_string,
    format_bytes,
    get_checksum_file_format_type,
    is_appimage_file,
    is_checksum_file,
    sanitize_filename,
    sanitize_version_string,
    validate_version_string,
)

# Import update display functions
from .update_displays import (
    display_update_details,
    display_update_error,
    display_update_progress,
    display_update_success,
    display_update_summary,
    display_update_warning,
)

__all__ = [
    # Constants
    "BYTES_PER_UNIT",
    "CHECKSUM_FILE_PATTERNS",
    "SPECIFIC_CHECKSUM_EXTENSIONS",
    # File operations
    "sanitize_filename",
    "format_bytes",
    "create_desktop_entry_name",
    # Version handling
    "extract_version_from_package_string",
    "sanitize_version_string",
    "validate_version_string",
    "extract_and_validate_version",
    # Checksum operations
    "is_checksum_file",
    "is_appimage_file",
    "get_checksum_file_format_type",
    # Update display functions
    "display_update_summary",
    "display_update_details",
    "display_update_progress",
    "display_update_success",
    "display_update_error",
    "display_update_warning",
]
