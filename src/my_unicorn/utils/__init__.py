"""Utility functions and helpers for my-unicorn.

This package provides common utility functions including:
- Asset validation (is_appimage_file, is_checksum_file, get_checksum_file_format_type)
- Progress utilities (human_mib, human_speed_bps, format_eta)
- Update display functions (display_update_summary, display_update_error)

Note: Functions have been reorganized following DRY principles:
- Asset validation -> utils/asset_validation.py (shared across layers)
- Verification formatting (format_bytes) -> domain/verification/formatting.py
- Version extraction -> infrastructure/github/version_utils.py
- Desktop entry utils (sanitize_filename, create_desktop_entry_name) -> infrastructure/desktop_entry.py
"""

# Import asset validation utilities (truly shared across multiple layers)
from my_unicorn.utils.asset_validation import (
    CHECKSUM_FILE_PATTERNS,
    SPECIFIC_CHECKSUM_EXTENSIONS,
    get_checksum_file_format_type,
    is_appimage_file,
    is_checksum_file,
)

__all__ = [
    "CHECKSUM_FILE_PATTERNS",
    "SPECIFIC_CHECKSUM_EXTENSIONS",
    "get_checksum_file_format_type",
    "is_appimage_file",
    "is_checksum_file",
]
