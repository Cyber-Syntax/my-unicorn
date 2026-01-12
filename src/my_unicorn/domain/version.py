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
