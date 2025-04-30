#!/usr/bin/env python3
"""Architecture utilities.

This module provides functions for detecting and managing system architecture
information for AppImage compatibility.

Note: Currently, this application is designed primarily for Linux systems.
Windows support is experimental and not officially supported.
"""

import logging
import platform
from typing import List, Optional

# Configure module logger
logger = logging.getLogger(__name__)

# Supported platform indicator - currently only Linux is officially supported
SUPPORTED_PLATFORMS = ["linux", "darwin"]


def get_arch_keywords(arch_keyword: Optional[str] = None) -> List[str]:
    """Get architecture-specific keywords based on the current platform.

    Args:
        arch_keyword: Optional specific architecture keyword to use instead of detection

    Returns:
        list: List of architecture keywords
    """
    if arch_keyword:
        return [arch_keyword]

    system = platform.system().lower()
    machine = platform.machine().lower()

    # Check if this is a supported platform
    if system not in SUPPORTED_PLATFORMS:
        logger.warning(
            f"Platform '{system}' is not officially supported. Some features may not work correctly."
        )

    # Special case for Windows AMD64 which is reported as 'AMD64' (uppercase)
    # Note: Windows support is experimental and not officially supported
    if system == "windows" and platform.machine() == "AMD64":
        machine = "amd64"

    # Architecture mapping based on system and machine
    arch_map = {
        "linux": {
            "x86_64": ["x86_64", "amd64", "x64", "linux64"],
            "aarch64": ["aarch64", "arm64", "aarch", "arm"],
            "armv7l": ["armv7", "arm32", "armhf"],
            "armv6l": ["armv6", "arm"],
            "i686": ["i686", "x86", "i386", "linux32"],
        },
        "darwin": {
            "x86_64": ["x86_64", "amd64", "x64", "darwin64", "macos"],
            "arm64": ["arm64", "aarch64", "arm", "macos"],
        },
        # Windows mappings kept for future compatibility - not officially supported
        "windows": {
            "amd64": ["x86_64", "amd64", "x64", "win64"],
            "x86": ["x86", "i686", "i386", "win32"],
            "arm64": ["arm64", "aarch64", "arm"],
        },
    }

    # Return default keywords for the current platform or empty list
    default_keywords = arch_map.get(system, {}).get(machine, [])
    if not default_keywords:
        logger.warning(
            f"No architecture keywords found for {system}/{machine}. Using system name as fallback."
        )
        return [system]
    return default_keywords


def get_incompatible_archs(current_arch: str) -> List[str]:
    """Get a list of architecture keywords that are incompatible with the current architecture.

    Args:
        current_arch: Current system architecture

    Returns:
        list: List of incompatible architecture keywords to filter out
    """
    # Define incompatible architectures based on current architecture
    incompatible_map = {
        # On x86_64, filter out ARM and 32-bit architectures
        "x86_64": [
            "arm64",
            "aarch64",
            "armhf",
            "arm32",
            "armv7",
            "armv6",
            "i686",
            "i386",
            "arm-",
            "-arm",
            "win",
            "windows",
            "darwin",
            "mac",
            "osx",
        ],
        # On ARM, filter out x86_64 and other incompatible architectures
        "aarch64": [
            "x86_64",
            "amd64",
            "i686",
            "i386",
            "win",
            "windows",
            "darwin",
            "mac",
            "osx",
        ],
        "arm64": ["x86_64", "amd64", "i686", "i386", "win", "windows", "darwin", "mac", "osx"],
        # On 32-bit x86, filter out 64-bit and ARM
        "i686": [
            "x86_64",
            "amd64",
            "arm64",
            "aarch64",
            "win",
            "windows",
            "darwin",
            "mac",
            "osx",
        ],
        "i386": [
            "x86_64",
            "amd64",
            "arm64",
            "aarch64",
            "win",
            "windows",
            "darwin",
            "mac",
            "osx",
        ],
    }

    # Return incompatible architectures or empty list if not defined
    return incompatible_map.get(current_arch, [])


def extract_arch_from_filename(filename: str) -> str:
    """Extract architecture information from a filename.

    Args:
        filename: The filename to analyze

    Returns:
        str: Architecture identifier or empty string if not found
    """
    if not filename:
        return ""

    filename_lower = filename.lower()

    # Check for common architecture patterns in the filename
    arch_patterns = {
        "x86_64": ["x86_64", "x86-64", "amd64", "x64"],
        "arm64": ["arm64", "aarch64"],
        "armv7": ["armv7", "armhf", "arm32"],
        "arm": ["arm"],
        "i386": ["i386", "i686", "x86"],
        "mac": ["mac", "darwin"],
        "win": ["win", "windows"],
    }

    # Find which architecture pattern matches the filename
    for arch, patterns in arch_patterns.items():
        if any(pattern in filename_lower for pattern in patterns):
            return arch

    return ""


def get_current_arch() -> str:
    """Get the current system architecture.

    Returns:
        str: Current system architecture (e.g., 'x86_64', 'arm64')
    """
    return platform.machine().lower()
