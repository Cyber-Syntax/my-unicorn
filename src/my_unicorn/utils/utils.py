"""Utility functions for my-unicorn AppImage installer.

This module provides common utility functions used across the application.

Functions have been reorganized into specific modules following the DRY principle:
- Asset validation utilities moved to utils.asset_validation (shared across layers)
- Verification formatting moved to domain.verification.formatting (domain layer)
- Version extraction moved to infrastructure.github.version_utils (GitHub layer)
- Desktop entry utilities moved to infrastructure.desktop_entry (desktop integration)

For backward compatibility and shared utilities, use:
    from my_unicorn.utils.asset_validation import (
        is_appimage_file,
        is_checksum_file,
        get_checksum_file_format_type,
        CHECKSUM_FILE_PATTERNS,
        SPECIFIC_CHECKSUM_EXTENSIONS,
    )
"""

# Re-export asset validation utilities for backward compatibility
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
