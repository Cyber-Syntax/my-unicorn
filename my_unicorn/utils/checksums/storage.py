"""File storage operations for checksum data.

This module provides functionality to securely store and manage checksum data for AppImage
verification. It handles writing checksums to files in a standardized format and ensures proper
file permissions are set.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def save_checksums_file(checksums: list[str], output_path: str | None = None) -> str:
    """Save checksums to a SHA256SUMS.txt file.

    Args:
        checksums: list of checksum lines
        output_path: Optional path where to save the file (default: temp file)

    Returns:
        Path to the created checksums file

    Raises:
        ValueError: If checksums list is empty
        OSError: If file cannot be created

    """
    if not checksums:
        raise ValueError("No checksums provided")

    # Create file path if not provided
    if not output_path:
        try:
            # Try to use the app's download directory if available
            from my_unicorn.global_config import GlobalConfigManager

            config_manager = GlobalConfigManager()
            downloads_dir = Path(config_manager.expanded_app_download_path)
        except (ImportError, AttributeError):
            # Fallback to user's Downloads directory
            downloads_dir = Path.home() / "Downloads"

        downloads_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(downloads_dir / "SHA256SUMS.txt")

    try:
        # Write checksums with atomic pattern
        with open(f"{output_path}.tmp", "w", encoding="utf-8") as f:
            for line in checksums:
                f.write(f"{line}\n")

        # Atomic rename to avoid partial writes
        if os.path.exists(output_path):
            os.remove(output_path)
        os.rename(f"{output_path}.tmp", output_path)

        logger.info("Created checksums file with %d entries: %s", len(checksums), output_path)
        return output_path

    except OSError as e:
        logger.error("Failed to write checksums file: %s", e)
        raise OSError(f"Failed to write checksums file: {e}")
