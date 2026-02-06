"""Desktop entry module - backward compatibility re-exports.

This module provides backward compatibility imports. All desktop entry classes
have been moved to the desktop_entry package for better organization.
"""

# Re-export from the desktop_entry package for backward compatibility
from my_unicorn.core.desktop_entry import (
    DesktopEntry,
    create_desktop_entry_for_app,
    remove_desktop_entry_for_app,
)

__all__ = [
    "DesktopEntry",
    "create_desktop_entry_for_app",
    "remove_desktop_entry_for_app",
]
