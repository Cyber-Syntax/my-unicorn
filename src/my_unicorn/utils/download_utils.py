"""Utility functions for download-related operations."""

from pathlib import Path
from urllib.parse import urlparse


def extract_filename_from_url(url: str) -> str:
    """Extract filename from a URL.

    Args:
        url: URL to extract filename from

    Returns:
        Filename extracted from URL path

    Example:
        >>> extract_filename_from_url("https://example.com/app.AppImage")
        'app.AppImage'

    Notes:
        - Handles query parameters (ignored)
        - Handles fragments (ignored)
        - Returns last path component
    """
    parsed = urlparse(url)
    return Path(parsed.path).name
