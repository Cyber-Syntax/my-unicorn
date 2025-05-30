"""Architecture utilities for identifying system CPU architecture and compatibility."""

import platform
import logging
from typing import List

logger = logging.getLogger(__name__)

def get_current_arch() -> str:
    """Returns system CPU architecture.

    Returns:
        str: CPU architecture (e.g., "x86_64", "arm64", "aarch64")
    """
    machine = platform.machine().lower()

    # Map common architecture names to standardized ones
    arch_map = {
        'x86_64': 'x86_64',
        'amd64': 'x86_64',
        'arm64': 'arm64',
        'aarch64': 'arm64'
    }

    return arch_map.get(machine, machine)

def get_compatible_arch_strings(cpu_arch: str) -> List[str]:
    """Returns list of equivalent architecture strings.

    Args:
        cpu_arch: Base architecture string (e.g., "x86_64")

    Returns:
        List of compatible architecture strings
    """
    compatibility_map = {
        'x86_64': ['x86_64', 'amd64'],
        'arm64': ['arm64', 'aarch64'],
        'i386': ['i386', 'x86'],
        'i686': ['i686', 'x86']
    }

    return compatibility_map.get(cpu_arch.lower(), [cpu_arch.lower()])

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
        ],
        # On ARM, filter out x86_64 and other incompatible architectures
        "aarch64": [
            "x86_64",
            "amd64",
            "i686",
            "i386",
        ],
        "arm64": ["x86_64", "amd64", "i686", "i386"],
        # On 32-bit x86, filter out 64-bit and ARM
        "i686": [
            "x86_64",
            "amd64",
            "arm64",
            "aarch64",
        ],
        "i386": [
            "x86_64",
            "amd64",
            "arm64",
            "aarch64",
        ],
    }

    # Return incompatible architectures or empty list if not defined
    return incompatible_map.get(current_arch, [])

def is_keyword_compatible_with_arch(keyword: str, system_cpu_arch: str) -> bool:
    """Checks if a filename keyword/suffix is compatible with system CPU architecture.

    Args:
        keyword: Filename keyword or suffix to check
        system_cpu_arch: System CPU architecture to check against

    Returns:
        bool: True if compatible, False otherwise

    Example:
        >>> is_keyword_compatible_with_arch("x86_64-Qt6", "x86_64")
        True
        >>> is_keyword_compatible_with_arch("arm64", "x86_64")
        False
        >>> is_keyword_compatible_with_arch("linux", "x86_64")
        True
    """
    import re

    keyword = keyword.lower()
    system_cpu_arch = system_cpu_arch.lower()

    # Get incompatible architectures for the current system
    incompatible_archs = get_incompatible_archs(system_cpu_arch)

    # Check if any incompatible architecture is present in the keyword
    for arch in incompatible_archs:
        # Use more specific pattern matching to avoid false positives
        # Look for architecture strings that are either:
        # 1. Standalone words (surrounded by non-alphanumeric chars)
        # 2. At word boundaries
        # 3. Part of architecture-specific patterns

        # Create patterns that match complete architecture identifiers
        patterns = [
            rf'\b{re.escape(arch)}\b',  # Complete word boundaries
            rf'[-_]{re.escape(arch)}[-_]',  # Surrounded by separators
            rf'[-_]{re.escape(arch)}$',  # At end with separator
            rf'^{re.escape(arch)}[-_]',  # At start with separator
        ]

        # Only match if it's a meaningful architecture occurrence
        for pattern in patterns:
            if re.search(pattern, keyword):
                logger.debug(f"Found incompatible architecture '{arch}' in keyword '{keyword}' "
                            f"for system architecture '{system_cpu_arch}'")
                return False

    # If we found no incompatible architectures, the keyword is compatible
    return True
