"""Input validation utilities for security."""

import re

# GitHub API limits
GITHUB_IDENTIFIER_MAX_LENGTH = 100

# Filesystem limits
APP_NAME_MAX_LENGTH = 255


def validate_github_identifier(identifier: str, name: str) -> None:
    """Validate GitHub owner/repo identifier for security.

    Prevents path traversal and injection attacks by validating
    that identifiers don't contain dangerous characters.

    Args:
        identifier: The identifier to validate (owner or repo name)
        name: Name of the identifier for error messages ("GitHub owner", "GitHub repo")

    Raises:
        ValueError: If identifier is invalid or contains dangerous characters

    Security:
        - Prevents path traversal (../, ..)
        - Prevents null byte injection
        - Enforces GitHub's length limits
        - Blocks directory separators

    Example:
        >>> validate_github_identifier("Cyber-Syntax", "GitHub owner")  # OK
        >>> validate_github_identifier("../etc", "GitHub owner")  # Raises ValueError
    """
    if not identifier:
        msg = f"{name} must not be empty"
        raise ValueError(msg)

    # Check for dangerous characters
    invalid_chars = ["/", "\\", "..", "\x00", "\n", "\r", "\t"]
    for char in invalid_chars:
        if char in identifier:
            msg = f"Invalid {name}: {identifier!r} (contains {char!r})"
            raise ValueError(msg)

    # Enforce GitHub's length limit (100 chars)
    if len(identifier) > GITHUB_IDENTIFIER_MAX_LENGTH:
        msg = f"{name} too long: {len(identifier)} chars (max {GITHUB_IDENTIFIER_MAX_LENGTH})"
        raise ValueError(msg)

    # Check for valid characters (alphanumeric, hyphen, underscore, period)
    # GitHub allows: A-Z, a-z, 0-9, hyphen, underscore, period
    valid_pattern = r"^[A-Za-z0-9._-]+$"
    if not re.match(valid_pattern, identifier):
        msg = f"Invalid {name}: {identifier!r} (must be alphanumeric with .-_)"
        raise ValueError(msg)


def validate_app_name(app_name: str) -> None:
    """Validate app name for file system safety.

    Args:
        app_name: App name to validate

    Raises:
        ValueError: If app name is invalid
    """
    if not app_name:
        msg = "App name must not be empty"
        raise ValueError(msg)

    # Similar validation as GitHub identifiers
    invalid_chars = ["/", "\\", "..", "\x00", "\n", "\r", "\t"]
    for char in invalid_chars:
        if char in app_name:
            msg = f"Invalid app name: {app_name!r} (contains {char!r})"
            raise ValueError(msg)

    if len(app_name) > APP_NAME_MAX_LENGTH:  # Typical filesystem limit
        msg = f"App name too long: {len(app_name)} chars (max {APP_NAME_MAX_LENGTH})"
        raise ValueError(msg)
