"""Workflow utilities for install and update operations.

This package contains shared workflow logic extracted from install.py and update.py
to eliminate code duplication and improve maintainability.

Modules:
    asset_selection: Unified asset selection logic for AppImages
    github_ops: GitHub URL parsing and config extraction utilities
    verification: Verification workflow orchestration
    appimage_setup: Icon extraction, desktop entry creation, file renaming

"""

from my_unicorn.workflows.appimage_setup import (
    create_desktop_entry,
    rename_appimage,
    setup_appimage_icon,
)
from my_unicorn.workflows.asset_selection import select_best_appimage_asset
from my_unicorn.workflows.github_ops import (
    extract_github_config,
    parse_github_url,
)
from my_unicorn.workflows.verification import verify_appimage_download

__all__ = [
    "create_desktop_entry",
    "extract_github_config",
    "parse_github_url",
    "rename_appimage",
    "select_best_appimage_asset",
    "setup_appimage_icon",
    "verify_appimage_download",
]
