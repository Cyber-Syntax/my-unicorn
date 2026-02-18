"""Error formatting utilities for consistent error reporting."""

from typing import Any

from my_unicorn.exceptions import InstallationError


def get_user_friendly_error(error: InstallationError) -> str:
    """Convert InstallationError to user-friendly message.

    Args:
        error: Installation error to convert

    Returns:
        User-friendly error message

    Examples:
        >>> from my_unicorn.exceptions import InstallationError
        >>> error = InstallationError("App not found in catalog")
        >>> get_user_friendly_error(error)
        'App not found in catalog'

        >>> error = InstallationError("No suitable appimage found")
        >>> get_user_friendly_error(error)
        'AppImage not found in release - may still be building'

    """
    error_msg = str(error).lower()
    error_mappings = [
        ("not found in catalog", "App not found in catalog"),
        (
            "no assets found",
            "No assets found in release - may still be building",
        ),
        (
            "no suitable appimage",
            "AppImage not found in release - may still be building",
        ),
        ("already installed", "Already installed"),
    ]
    for pattern, message in error_mappings:
        if pattern in error_msg:
            return message
    return str(error)


def build_install_error_result(
    error: Exception,
    target: str,
    is_url: bool,
) -> dict[str, Any]:
    """Build error result dict for failed installation.

    Args:
        error: The installation error
        target: The app name or URL that failed
        is_url: Whether target is a URL

    Returns:
        Error result dictionary with keys: success, target, name, error, source

    Examples:
        >>> from my_unicorn.exceptions import InstallationError
        >>> error = InstallationError("App not found in catalog")
        >>> result = build_install_error_result(error, "myapp", False)
        >>> result['success']
        False
        >>> result['source']
        'catalog'

    """
    friendly_error = (
        get_user_friendly_error(error)
        if isinstance(error, InstallationError)
        else str(error)
    )
    return {
        "success": False,
        "target": target,
        "name": target,
        "error": friendly_error,
        "source": "url" if is_url else "catalog",
    }


def build_success_result(
    target: str,
    app_name: str,
    is_url: bool,
    installed_path: str | None = None,
) -> dict[str, Any]:
    """Build success result dict for successful installation.

    Args:
        target: The original target (app name or URL)
        app_name: The installed app name
        is_url: Whether target is a URL
        installed_path: Optional path to installed AppImage

    Returns:
        Success result dictionary with keys:
        success, target, name, source, path

    Examples:
        >>> result = build_success_result(
        ...     "myapp", "myapp", False, "/path/to/app"
        ... )
        >>> result['success']
        True
        >>> result['source']
        'catalog'

    """
    result: dict[str, Any] = {
        "success": True,
        "target": target,
        "name": app_name,
        "source": "url" if is_url else "catalog",
    }
    if installed_path:
        result["path"] = installed_path
    return result
