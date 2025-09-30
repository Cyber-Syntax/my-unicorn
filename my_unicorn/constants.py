"""Centralized constants module for my-unicorn application.

This module serves as the single source of truth for all shared constants
across the my-unicorn codebase. Constants are organized by logical categories
and use typing.Final annotations to ensure immutability.

Usage:
    from my_unicorn.constants import CONFIG_VERSION
    from my_unicorn.constants import CONFIG_DIR_NAME
"""

from typing import Final

# =============================================================================
# Configuration Constants
# =============================================================================

# Configuration version - single source of truth for config versioning
CONFIG_VERSION: Final[str] = "1.0.2"

# Configuration directory and file names
CONFIG_DIR_NAME: Final[str] = ".config"
APPS_DIR_NAME: Final[str] = "applications"
CONFIG_FILE_NAME: Final[str] = "settings.conf"

# Configuration defaults
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
DEFAULT_BACKUP_COUNT: Final[int] = 5
