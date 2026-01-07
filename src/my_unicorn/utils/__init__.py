"""Utility functions and helpers for my-unicorn.

This package provides common utility functions including:
- File and path operations (sanitize_filename, format_bytes)
- Version string handling (extract_and_validate_version)
- Desktop entry creation (create_desktop_entry_name)
- Checksum file detection (is_checksum_file, is_appimage_file)
- Update display functions (display_update_summary, display_update_error)
- Workflow utilities in submodules (asset_selection, verification,
  appimage_setup, github_ops)
"""

# Import all utility functions from utils.py
# Import update display functions
from my_unicorn.ui.display_update import (
    display_update_details,
    display_update_error,
    display_update_progress,
    display_update_success,
    display_update_summary,
    display_update_warning,
)

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

# NOTE: Workflow utilities (asset_selection, github_ops, verification,
# appimage_setup) are NOT imported here to avoid circular imports.
# Import them directly from their respective modules.

__all__ = [
    "BYTES_PER_UNIT",
    "CHECKSUM_FILE_PATTERNS",
    "SPECIFIC_CHECKSUM_EXTENSIONS",
    "create_desktop_entry_name",
    "display_update_details",
    "display_update_error",
    "display_update_progress",
    "display_update_success",
    "display_update_summary",
    "display_update_warning",
    "extract_and_validate_version",
    "extract_version_from_package_string",
    "format_bytes",
    "get_checksum_file_format_type",
    "is_appimage_file",
    "is_checksum_file",
    "sanitize_filename",
    "sanitize_version_string",
    "validate_version_string",
]
