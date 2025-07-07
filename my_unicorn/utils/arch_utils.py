"""Architecture utilities for system compatibility checking.

This module provides utilities for:
- Detecting system CPU architecture
- Validating architecture compatibility
- Mapping between different architecture naming schemes
- Filtering incompatible architectures
"""

import logging
import platform

logger = logging.getLogger(__name__)


def get_current_arch() -> str:
    """Get current system CPU architecture.

    Detects and normalizes the current system's CPU architecture name.

    Returns:
        str: Normalized CPU architecture identifier (e.g., "x86_64", "arm64")

    Example:
        >>> get_current_arch()
        'x86_64'
    """
    machine = platform.machine().lower()

    # Map common architecture names to standardized ones
    arch_map = {"x86_64": "x86_64", "amd64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}

    return arch_map.get(machine, machine)


def get_compatible_arch_strings(cpu_arch: str) -> list[str]:
    """Get equivalent architecture strings for a CPU architecture.
    
    Maps architecture identifiers to their common alternative names used by
    different systems, distributions and package formats.

    Args:
        cpu_arch: Base architecture identifier (e.g., "x86_64", "aarch64")

    Returns:
        list[str]: List of equivalent architecture strings

    Example:
        >>> get_compatible_arch_strings("x86_64")
        ['x86_64', 'amd64']
    """
    compatibility_map = {
        "x86_64": ["x86_64", "amd64"],
        "arm64": ["arm64", "aarch64"],
        "i386": ["i386", "x86"],
        "i686": ["i686", "x86"],
    }

    return compatibility_map.get(cpu_arch.lower(), [cpu_arch.lower()])


def get_incompatible_archs(current_arch: str) -> list[str]:
    """Get architecture strings incompatible with specified architecture.

    Provides a list of architecture identifiers that are known to be incompatible
    with the given architecture, used for filtering out incompatible AppImages.

    Args:
        current_arch: Base architecture to check incompatibilities against

    Returns:
        list[str]: List of incompatible architecture identifiers

    Example:
        >>> get_incompatible_archs("x86_64")
        ['arm64', 'aarch64', 'armhf', 'arm32', 'armv7', 'armv6', 'i686', 'i386']
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
    """Check if a filename component is compatible with system architecture.

    Analyzes filename components using pattern matching to determine if they
    indicate architecture compatibility or incompatibility with the system.

    Args:
        keyword: String to analyze for architecture indicators
        system_cpu_arch: Current system CPU architecture identifier

    Returns:
        bool: True if compatible or neutral, False if incompatible

    Examples:
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

    # Get list of architectures incompatible with current system
    incompatible_archs = get_incompatible_archs(system_cpu_arch)

    # Check each potential incompatible architecture
    for arch in incompatible_archs:
        # Match architecture strings that are:
        # 1. Complete words (bounded by non-alphanumeric chars)
        # 2. Word boundaries or separator-bounded
        # 3. Architecture-specific filename patterns

        # Create patterns that match complete architecture identifiers
        patterns = [
            rf"\b{re.escape(arch)}\b",  # Complete word boundaries
            rf"[-_]{re.escape(arch)}[-_]",  # Surrounded by separators
            rf"[-_]{re.escape(arch)}$",  # At end with separator
            rf"^{re.escape(arch)}[-_]",  # At start with separator
        ]

        # Only match if it's a meaningful architecture occurrence
        for pattern in patterns:
            if re.search(pattern, keyword):
                logger.debug(
                    "Found incompatible architecture '%s' in keyword '%s' "
                    f"for system architecture '%s'",
                    arch, keyword, system_cpu_arch
                )
                return False

    # If we found no incompatible architectures, the keyword is compatible
    return True
