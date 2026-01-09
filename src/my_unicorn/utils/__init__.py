"""Utility functions and helpers for my-unicorn.

This package provides common utility functions including:
- File and path operations (sanitize_filename, format_bytes)
- Version string handling (extract_and_validate_version)
- Desktop entry creation (create_desktop_entry_name)
- Checksum file detection (is_checksum_file, is_appimage_file)
- Progress utilities (human_mib, human_speed_bps, format_eta)
- Update display functions (display_update_summary, display_update_error)

Note: Workflow-specific utilities have been moved to their appropriate layers:
- Asset selection -> workflows/shared.py
- Verification -> workflows/shared.py
- GitHub operations -> infrastructure/github/operations.py
- Progress helpers -> ui/progress.py
"""

# Import update display functions
from my_unicorn.ui.display_update import (
    display_update_details,
    display_update_error,
    display_update_progress,
    display_update_success,
    display_update_summary,
    display_update_warning,
)

# Import generic utility functions
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
