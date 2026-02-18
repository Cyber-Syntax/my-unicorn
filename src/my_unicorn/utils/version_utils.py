"""Version comparison utilities."""

from packaging.version import InvalidVersion, Version


def compare_versions(current: str, latest: str) -> bool:
    """Compare version strings to determine if update is available.

    Args:
        current: Current version string
        latest: Latest version string

    Returns:
        True if latest is newer than current

    """
    current_clean = current.lstrip("v").lower()
    latest_clean = latest.lstrip("v").lower()

    if current_clean == latest_clean:
        return False

    # Try using packaging.version for proper semantic version comparison
    try:
        current_version = Version(current_clean)
        latest_version = Version(latest_clean)
    except InvalidVersion:
        # Fall through to legacy comparison if parsing fails
        pass
    else:
        return latest_version > current_version

    # Legacy comparison for backward compatibility
    try:
        current_parts = [int(x) for x in current_clean.split(".")]
        latest_parts = [int(x) for x in latest_clean.split(".")]

        # Pad shorter version with zeros
        max_len = max(len(current_parts), len(latest_parts))
        current_parts.extend([0] * (max_len - len(current_parts)))
        latest_parts.extend([0] * (max_len - len(latest_parts)))
    except ValueError:
        # Fallback to string comparison
        return latest_clean > current_clean
    else:
        return latest_parts > current_parts
