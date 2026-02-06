"""Browser detection and browser-specific desktop entry handling."""

from my_unicorn.constants import DESKTOP_BROWSER_NAMES


def is_browser_app(app_name: str) -> bool:
    """Check if an application is a browser based on its name.

    Args:
        app_name: Name of the application

    Returns:
        True if the app is detected as a browser

    """
    app_name_lower = app_name.lower()
    return any(browser in app_name_lower for browser in DESKTOP_BROWSER_NAMES)


def get_browser_mime_types() -> list[str]:
    """Get standard browser MIME types for web browsers.

    Returns:
        List of MIME types that browsers should handle

    """
    return [
        "text/html",
        "text/xml",
        "application/xhtml+xml",
        "application/xml",
        "application/rss+xml",
        "application/rdf+xml",
        "image/gif",
        "image/jpeg",
        "image/png",
        "x-scheme-handler/http",
        "x-scheme-handler/https",
        "x-scheme-handler/ftp",
        "x-scheme-handler/chrome",
        "video/webm",
        "application/x-xpinstall",
    ]
