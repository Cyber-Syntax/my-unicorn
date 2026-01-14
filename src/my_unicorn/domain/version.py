"""Version comparison and normalization utilities.

Provides utilities for comparing semantic versions and normalizing semver-style
version strings to PEP 440 format for proper Python version comparison.
"""

import re

from packaging.version import InvalidVersion, Version


def compare_versions(version1: str, version2: str) -> int:
    """Compare two semantic version strings.

    Returns -1 if version1 < version2, 0 if equal, 1 if version1 > version2.
    Uses packaging.Version for robust semantic handling.
    """
    v1_clean = version1.lstrip("v").lower()
    v2_clean = version2.lstrip("v").lower()

    if v1_clean == v2_clean:
        return 0

    try:
        v1 = Version(v1_clean)
        v2 = Version(v2_clean)
        if v1 < v2:
            return -1
        if v1 > v2:
            return 1
        return 0
    except InvalidVersion:
        # Fallback to legacy numeric comparison
        def parse_version(v: str) -> list[int]:
            try:
                return [int(x) for x in v.split(".")]
            except ValueError:
                return [0, 0, 0]

        v1_parts = parse_version(v1_clean)
        v2_parts = parse_version(v2_clean)
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        if v1_parts < v2_parts:
            return -1
        if v1_parts > v2_parts:
            return 1
        return 0


# Map semver prerelease labels to PEP 440 equivalents
_PRERELEASE_MAP = {
    "alpha": "a",
    "beta": "b",
    "rc": "rc",
}

# Regex pattern for detecting semver-style prerelease versions
_PRERELEASE_RE = re.compile(
    r"""
    ^
    (?P<base>\d+\.\d+\.\d+)
    (?:-
        (?P<label>alpha|beta|rc)
        (?P<num>\d*)?
    )?
    $
    """,
    re.VERBOSE,
)


def normalize_version(v: str) -> str:
    """Normalize semver-like versions to PEP 440.

    Converts semantic versioning style prerelease versions to PEP 440 format
    for proper Python version comparison using packaging.version.

    Examples:
        >>> normalize_version("1.0.0-alpha")
        '1.0.0a0'
        >>> normalize_version("2.0.0-beta1")
        '2.0.0b1'
        >>> normalize_version("3.0.0-rc2")
        '3.0.0rc2'
        >>> normalize_version("v1.2.3")
        '1.2.3'
        >>> normalize_version("1.2.3")
        '1.2.3'

    Args:
        v: Version string in semver or PEP 440 format

    Returns:
        Normalized version string in PEP 440 format
    """
    v = v.lstrip("v")

    match = _PRERELEASE_RE.match(v)
    if not match:
        return v

    base = match.group("base")
    label = match.group("label")
    num = match.group("num") or "0"

    if not label:
        return base

    pep_label = _PRERELEASE_MAP[label]
    return f"{base}{pep_label}{num}"
