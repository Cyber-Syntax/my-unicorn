"""ASCII rendering utilities for progress display.

This module provides helper functions for formatting data and rendering
ASCII-based progress bars without external UI dependencies.
"""

# Constants for byte conversions
KIB = 1024
MIB = 1024 * 1024
GIB = 1024 * 1024 * 1024


def human_mib(bytes_value: float) -> str:
    """Convert bytes to human-readable MiB format.

    Args:
        bytes_value: Size in bytes

    Returns:
        Formatted string like "15.2 MiB" or "1.5 GiB"

    """
    if bytes_value <= 0:
        return "0 B"

    mib = bytes_value / MIB
    if mib < 1.0:
        kib = bytes_value / KIB
        return f"{kib:.1f} KiB"
    elif mib < KIB:
        return f"{mib:.1f} MiB"
    else:
        gib = mib / KIB
        return f"{gib:.2f} GiB"


def human_speed_bps(bytes_per_sec: float) -> str:
    """Convert bytes per second to human-readable speed format.

    Args:
        bytes_per_sec: Speed in bytes per second

    Returns:
        Formatted string like "5.2 MB/s" or "850 KB/s"

    """
    if bytes_per_sec <= 0:
        return "-- MB/s"

    mb_per_sec = bytes_per_sec / MIB
    if mb_per_sec >= 1.0:
        return f"{mb_per_sec:.1f} MB/s"
    else:
        kb_per_sec = bytes_per_sec / KIB
        return f"{kb_per_sec:.0f} KB/s"


def format_eta(seconds: float) -> str:
    """Format ETA in human-readable format.

    Args:
        seconds: Time remaining in seconds

    Returns:
        Formatted string like "2m 30s", "1h 5m", or "--:--"

    """
    if seconds <= 0 or seconds == float("inf"):
        return "--:--"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def render_bar(completed: float, total: float, width: int = 30) -> str:
    """Render an ASCII progress bar.

    Args:
        completed: Amount completed
        total: Total amount
        width: Width of the progress bar in characters

    Returns:
        ASCII progress bar string like "[========>     ]"

    """
    if total <= 0:
        return "[" + " " * width + "]"

    filled_width = int((completed / total) * width)
    filled_width = max(0, min(filled_width, width))

    if filled_width == width:
        bar = "=" * width
    elif filled_width > 0:
        bar = "=" * (filled_width - 1) + ">" + " " * (width - filled_width)
    else:
        bar = " " * width

    return f"[{bar}]"


def truncate_text(text: str, max_length: int, ellipsis: str = "...") -> str:
    """Truncate text to maximum length with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length including ellipsis
        ellipsis: String to append when truncating

    Returns:
        Truncated text with ellipsis if needed

    """
    if len(text) <= max_length:
        return text

    if max_length <= len(ellipsis):
        return ellipsis[:max_length]

    return text[: max_length - len(ellipsis)] + ellipsis


def format_percentage(completed: float, total: float) -> str:
    """Format completion percentage.

    Args:
        completed: Amount completed
        total: Total amount

    Returns:
        Formatted percentage string like "75%"

    """
    if total <= 0:
        return "0%"

    percentage = (completed / total) * 100
    percentage = max(0.0, min(percentage, 100.0))
    return f"{percentage:>3.0f}%"


def pad_right(text: str, width: int) -> str:
    """Pad text with spaces on the right to reach desired width.

    Args:
        text: Text to pad
        width: Desired width

    Returns:
        Padded text

    """
    return text.ljust(width)


def pad_left(text: str, width: int) -> str:
    """Pad text with spaces on the left to reach desired width.

    Args:
        text: Text to pad
        width: Desired width

    Returns:
        Padded text

    """
    return text.rjust(width)
