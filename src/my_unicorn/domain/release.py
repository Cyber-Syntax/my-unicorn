"""Release selection and version comparison logic.

Pure business logic for selecting appropriate releases based on
version specifications and requirements.
"""

from my_unicorn.domain.types import Release, Version


def _parse_version_safe(tag_name: str) -> Version:
    """Parse version from tag name, with fallback for invalid versions.

    Args:
        tag_name: Git tag name

    Returns:
        Version object (or minimal Version for invalid input)
    """
    try:
        return Version.parse(tag_name)
    except ValueError:
        # Return minimal version for unparseable tags
        return Version(major=0, minor=0, patch=0, prerelease=tag_name)


def select_latest_release(
    releases: list[Release], *, include_prerelease: bool = False
) -> Release | None:
    """Select the latest release from a list.

    Args:
        releases: List of releases
        include_prerelease: Whether to include pre-release versions

    Returns:
        Latest release or None if list is empty
    """
    if not releases:
        return None

    # Filter based on prerelease preference
    if not include_prerelease:
        stable_releases = [r for r in releases if not r.prerelease]
        if stable_releases:
            releases = stable_releases

    # Sort by version (newest first)
    sorted_releases = sorted(
        releases, key=lambda r: _parse_version_safe(r.tag_name), reverse=True
    )

    return sorted_releases[0] if sorted_releases else None


def select_version(
    releases: list[Release], version_spec: str | None
) -> Release | None:
    """Select release matching version specification.

    Args:
        releases: List of available releases
        version_spec: Version specification (e.g., "1.2.3", "latest", None)

    Returns:
        Matching release or None if not found
    """
    if not releases:
        return None

    # If no version specified or "latest", return latest stable
    if not version_spec or version_spec.lower() == "latest":
        return select_latest_release(releases, include_prerelease=False)

    # Try exact tag match first
    for release in releases:
        if release.tag_name == version_spec:
            return release

    # Try version match (with or without 'v' prefix)
    normalized_spec = version_spec.lstrip("v")
    for release in releases:
        normalized_tag = release.tag_name.lstrip("v")
        if normalized_tag == normalized_spec:
            return release

    return None


def is_newer_version(current: str, candidate: str) -> bool:
    """Compare two version strings.

    Args:
        current: Current version string
        candidate: Candidate version string

    Returns:
        True if candidate is newer than current
    """
    try:
        current_ver = Version.parse(current)
        candidate_ver = Version.parse(candidate)
    except ValueError:
        # If parsing fails, do string comparison as fallback
        return candidate > current
    else:
        return candidate_ver > current_ver


def get_release_by_tag(releases: list[Release], tag: str) -> Release | None:
    """Get release by exact tag name.

    Args:
        releases: List of releases
        tag: Tag name to match

    Returns:
        Release with matching tag or None
    """
    for release in releases:
        if release.tag_name == tag:
            return release
    return None


def filter_stable_releases(releases: list[Release]) -> list[Release]:
    """Filter to only stable (non-prerelease) releases.

    Args:
        releases: List of all releases

    Returns:
        List of stable releases only
    """
    return [r for r in releases if not r.prerelease]


def filter_prerelease_releases(releases: list[Release]) -> list[Release]:
    """Filter to only prerelease versions.

    Args:
        releases: List of all releases

    Returns:
        List of prerelease versions only
    """
    return [r for r in releases if r.prerelease]
