"""my-unicorn: A modern AppImage package manager and installer.

This package provides tools for downloading, installing, updating, and managing
AppImage applications from GitHub releases with features like:

- Concurrent downloads and updates
- GitHub authentication and rate limiting
- Verification and checksums
- Desktop entry management
- Icon downloads
- Backup and restore functionality
- Configuration management
"""

__version__ = "2.0.0"
__author__ = "my-unicorn team"
__description__ = "Modern AppImage package manager and installer"

# Core exports
from .auth import GitHubAuthManager, auth_manager
from .config import ConfigManager, config_manager
from .github_client import GitHubReleaseFetcher, GitHubAsset, GitHubReleaseDetails
from .install import Installer, IconAsset
from .logger import get_logger, logger
from .update import UpdateManager, UpdateInfo
from .utils import (
    get_system_architecture,
    is_valid_github_repo,
    sanitize_filename,
    format_bytes,
)
from .verify import Verifier, VerificationConfig

__all__ = [
    # Main classes
    "ConfigManager",
    "GitHubAuthManager",
    "GitHubReleaseFetcher",
    "Installer",
    "UpdateManager",
    "Verifier",
    # Global instances
    "config_manager",
    "auth_manager",
    "logger",
    # Type definitions
    "GitHubAsset",
    "GitHubReleaseDetails",
    "IconAsset",
    "UpdateInfo",
    "VerificationConfig",
    # Utility functions
    "get_logger",
    "get_system_architecture",
    "is_valid_github_repo",
    "sanitize_filename",
    "format_bytes",
    # Version info
    "__version__",
    "__author__",
    "__description__",
]
