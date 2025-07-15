"""GitHub Release Checksums Parsing Utilities."""

import logging

# Import core utility functionality
from my_unicorn.utils.checksums.parser import parse_checksums_from_description
from my_unicorn.utils.checksums.storage import save_checksums_file

logger = logging.getLogger(__name__)

# Export public API (only pure utilities, no verification functions)
__all__ = [
    # Core parsing and extraction utilities (pure functions)
    "parse_checksums_from_description",
    "save_checksums_file",
]
