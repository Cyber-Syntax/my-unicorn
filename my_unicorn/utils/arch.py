"""Architecture utilities for system compatibility checking.

This module provides utilities for:
- Detecting system CPU architecture
- Validating architecture compatibility
- Mapping between different architecture naming schemes
- Filtering incompatible architectures
"""

import logging
import platform
import re

logger = logging.getLogger(__name__)

# Constants for architecture identification
# TODO: Make sure these architecture keywords are correct
# Stop 32-bit support for now
ARCH_KEYWORDS = {
    "x86_64": ["x86_64", "amd64", "x86-64", "x64"],
    "aarch64": ["aarch64", "arm64", "armv8"],
    "armhf": ["armhf", "arm32", "armv7"],
    "i686": ["i686", "x86", "i386"],
}

ARCH_PATTERNS = [
    (r"(-arm64[^.]*\.appimage)$", "arm64"),
    (r"(-aarch64[^.]*\.appimage)$", "aarch64"),
    (r"(-amd64[^.]*\.appimage)$", "amd64"),
    (r"(-x86_64[^.]*\.appimage)$", "x86_64"),
    (r"(-x86[^.]*\.appimage)$", "x86"),
    (r"(-i686[^.]*\.appimage)$", "i686"),
    (r"(-i386[^.]*\.appimage)$", "i386"),
    (r"(-linux(?:64)?\.appimage)$", "linux"),
]

ALL_ARCH_MARKERS = [
    "arm64",
    "aarch64",
    "armhf",
    "arm32",
    "armv7",
    "armv8",
    "x86_64",
    "amd64",
    "x86-64",
    "x64",
    "i686",
    "x86",
    "i386",
]


def extract_arch_from_filename(filename: str) -> str | None:
    """Extract architecture keyword from an AppImage filename.
    Iterates through known architecture keywords and their markers.
    Uses regex to ensure the marker is a distinct word or segment in the filename.

    Args:
        filename: The AppImage filename to extract from

    Returns:
        str | None: The extracted canonical architecture keyword (e.g., "x86_64") or None

    """
    if not filename:
        return None

    lower_name = filename.lower()

    # Iterate through canonical keywords (x86_64, aarch64, etc.)
    # and their associated markers (amd64, x86-64, arm64, etc.)
    # The order in ARCH_KEYWORDS might matter if markers are ambiguous (e.g., "arm" vs "arm64")
    # More specific markers should ideally be checked first or be distinct enough.
    for canonical_arch, markers in ARCH_KEYWORDS.items():
        for marker in markers:
            # Regex to find the marker as a whole word or delimited by common separators.
            # This helps avoid matching "arm" in "alarm" or "x86" in "someapp-x8600.AppImage".
            # Pattern: (non-alphanumeric OR start of string) + marker + (non-alphanumeric OR end of string OR .appimage)
            # Using word boundaries \b might be too restrictive if markers are like "x86-64".
            # Using lookarounds for more precise matching:
            # (?<=^|[\W_]) ensures start of string or non-word char before.
            # (?=$|[\W_]|\.appimage) ensures end of string, non-word char, or .appimage after.
            # Simpler regex: look for marker surrounded by non-alphanumeric chars or start/end of string.
            # The re.escape(marker) is important if markers contain special regex characters.
            pattern = re.compile(
                rf"(?:^|[^a-zA-Z0-9])({re.escape(marker)})(?:$|[^a-zA-Z0-9])", re.IGNORECASE
            )
            if pattern.search(lower_name):
                return canonical_arch  # Return the canonical keyword

    return None  # No specific architecture keyword found

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
