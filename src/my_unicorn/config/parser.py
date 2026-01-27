"""INI parser utilities for my-unicorn configuration.

This module provides helper classes for parsing INI configuration files
with support for inline comments and user-friendly documentation.
"""

import configparser
from datetime import UTC, datetime
from typing import Any

from my_unicorn.constants import (
    GLOBAL_CONFIG_VERSION,
    ISO_DATETIME_FORMAT,
    KEY_CONFIG_VERSION,
    SECTION_DEFAULT,
    SECTION_DIRECTORY,
    SECTION_NETWORK,
)


def _strip_inline_comment(value: str) -> str:
    """Strip inline comments from configuration values.

    Args:
        value: Configuration value that may contain inline comment

    Returns:
        Value with inline comment removed (anything after '  #')
    """
    if "  #" in value:
        return value.split("  #")[0].strip()
    return value


class CommentAwareConfigParser(configparser.ConfigParser):
    """ConfigParser that strips inline comments when reading values."""

    def get(  # type: ignore[override]
        self,
        section: str,
        option: str,
        **kwargs: Any,  # noqa: ANN401
    ) -> str:
        """Get a configuration value with inline comments stripped."""
        value = super().get(section, option, **kwargs)
        return _strip_inline_comment(value)


class ConfigCommentManager:
    """Manages configuration file comments for user-friendly documentation."""

    @staticmethod
    def get_file_header() -> str:
        """Generate file header comment with description and timestamp.

        Returns:
            Header comment string for the configuration file
        """
        timestamp = datetime.now(tz=UTC).strftime(ISO_DATETIME_FORMAT)
        return f"""# My-Unicorn AppImage Installer Configuration
# This file contains settings for the my-unicorn AppImage installer.
# You can modify these values to customize the behavior of the application.
#
# Last updated: {timestamp}
# Configuration version: {GLOBAL_CONFIG_VERSION}

"""

    @staticmethod
    def get_section_comments() -> dict[str, str]:
        """Get comments for each configuration section.

        Returns:
            Dictionary mapping section names to their comment strings
        """
        return {
            SECTION_DEFAULT: """# ========================================
# MAIN CONFIGURATION
# ========================================
# These settings control the overall behavior of my-unicorn.
#
# config_version: Version of configuration format (DO NOT EDIT)
# max_concurrent_downloads: Max simultaneous downloads (1-10)
# max_backup: Number of backup copies to keep when updating apps (0-5)
# log_level: Detail level for log files (DEBUG, INFO, WARNING, ERROR)
# console_log_level: Console output detail level (DEBUG, INFO, etc.)

""",
            SECTION_NETWORK: """
# ========================================
# NETWORK CONFIGURATION
# ========================================
# Settings for downloading AppImages and accessing repositories.
#
# retry_attempts: Number of times to retry failed downloads (1-10)
# timeout_seconds: Seconds to wait before timing out requests (5-60)

""",
            SECTION_DIRECTORY: """
# ========================================
# DIRECTORY PATHS
# ========================================
# Customize where my-unicorn stores files and directories.
# Use absolute paths or paths starting with ~ for home directory.
#
# download: Temporary download location for AppImages
# storage: Where installed AppImages are stored
# backup: Backup location for old AppImage versions
# icon: Directory for application icons
# settings: Configuration and settings directory
# logs: Log files location
# cache: Temporary cache directory
# tmp: Temporary files directory

""",
        }

    @staticmethod
    def get_key_comments() -> dict[str, dict[str, str]]:
        """Get inline comments for specific configuration keys.

        Returns:
            Nested dictionary mapping section -> key -> comment
        """
        return {
            SECTION_DEFAULT: {
                KEY_CONFIG_VERSION: "# DO NOT MODIFY - Config format version",
            },
            SECTION_NETWORK: {},
            SECTION_DIRECTORY: {},
        }
