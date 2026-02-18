"""Desktop entry module for managing .desktop files for AppImage apps."""

from my_unicorn.core.desktop_entry.entry import DesktopEntry
from my_unicorn.core.desktop_entry.helpers import (
    create_desktop_entry_for_app,
    remove_desktop_entry_for_app,
)

__all__ = [
    "DesktopEntry",
    "create_desktop_entry_for_app",
    "remove_desktop_entry_for_app",
]
