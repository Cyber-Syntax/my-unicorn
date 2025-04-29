#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for AppCatalog functionality.

This module contains tests for the app_catalog module, which provides
a database of applications that can be installed by name.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import pytest
from unittest.mock import MagicMock

# Add the project root to sys.path using pathlib for better cross-platform compatibility
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import modules
from src.app_catalog import (
    AppInfo,
    APP_CATALOG,
    get_app_info,
    get_all_apps,
    get_apps_by_category,
    get_apps_by_tag,
    search_apps,
    get_categories,
    sync_with_icon_paths,
)


@pytest.fixture
def sample_app_info() -> AppInfo:
    """Create a sample AppInfo instance for testing.

    Returns:
        AppInfo: Sample application information
    """
    return AppInfo(
        name="Test App",
        description="A test application",
        owner="testowner",
        repo="testrepo",
        sha_name="test.sha256",
        hash_type="sha256",
        category="Test",
        tags=["test", "sample"],
    )


def test_app_info_init() -> None:
    """Test AppInfo initialization with different parameters."""
    # Test with all parameters
    app_info = AppInfo(
        name="Test App",
        description="A test application",
        owner="testowner",
        repo="testrepo",
        sha_name="test.sha256",
        hash_type="sha256",
        category="Test",
        tags=["test", "sample"],
    )

    assert app_info.name == "Test App"
    assert app_info.description == "A test application"
    assert app_info.owner == "testowner"
    assert app_info.repo == "testrepo"
    assert app_info.sha_name == "test.sha256"
    assert app_info.hash_type == "sha256"
    assert app_info.category == "Test"
    assert app_info.tags == ["test", "sample"]

    # Test with minimal parameters (defaults)
    app_info = AppInfo(
        name="Test App",
        description="A test application",
        owner="testowner",
        repo="testrepo",
    )

    assert app_info.name == "Test App"
    assert app_info.sha_name == "no_sha_file"  # Default value
    assert app_info.hash_type == "sha256"  # Default value
    assert app_info.category == "Other"  # Default value
    assert app_info.tags == []  # Default empty list


def test_app_catalog_contains_entries() -> None:
    """Test that the app catalog contains entries."""
    assert len(APP_CATALOG) > 0

    # Check that some common apps are in the catalog
    assert "joplin" in APP_CATALOG
    assert "freetube" in APP_CATALOG

    # Check that app entries have expected structure
    for app_id, app_info in APP_CATALOG.items():
        assert isinstance(app_info, AppInfo)
        assert app_info.name
        assert app_info.description
        assert app_info.owner
        assert app_info.repo


def test_get_app_info() -> None:
    """Test retrieving app info by app ID."""
    # Test with existing app
    joplin_info = get_app_info("joplin")
    assert joplin_info is not None
    assert joplin_info.name == "Joplin"
    assert joplin_info.owner == "laurent22"

    # Test with non-existent app
    non_existent = get_app_info("non_existent_app")
    assert non_existent is None

    # Test case insensitivity
    joplin_case_insensitive = get_app_info("JoPLiN")
    assert joplin_case_insensitive is not None
    assert joplin_case_insensitive.name == "Joplin"


def test_get_all_apps() -> None:
    """Test retrieving all apps from the catalog."""
    all_apps = get_all_apps()
    assert len(all_apps) == len(APP_CATALOG)
    assert all(isinstance(app, AppInfo) for app in all_apps)

    # Check that each app in the result matches an entry in APP_CATALOG
    catalog_names = {app_info.name for app_info in APP_CATALOG.values()}
    result_names = {app_info.name for app_info in all_apps}
    assert catalog_names == result_names


def test_get_apps_by_category() -> None:
    """Test filtering apps by category."""
    # Test with existing category
    productivity_apps = get_apps_by_category("Productivity")
    assert len(productivity_apps) > 0
    assert all(app.category == "Productivity" for app in productivity_apps)

    # Test with non-existent category
    non_existent = get_apps_by_category("NonExistentCategory")
    assert len(non_existent) == 0

    # Test case insensitivity
    productivity_case_insensitive = get_apps_by_category("productivity")
    assert len(productivity_case_insensitive) > 0
    assert len(productivity_case_insensitive) == len(productivity_apps)


def test_get_apps_by_tag() -> None:
    """Test filtering apps by tag."""
    # Test with existing tag
    notes_apps = get_apps_by_tag("notes")
    assert len(notes_apps) > 0
    assert all("notes" in [t.lower() for t in app.tags] for app in notes_apps)

    # Test with non-existent tag
    non_existent = get_apps_by_tag("non_existent_tag")
    assert len(non_existent) == 0

    # Test case insensitivity
    notes_case_insensitive = get_apps_by_tag("NoTeS")
    assert len(notes_case_insensitive) > 0
    assert len(notes_case_insensitive) == len(notes_apps)


def test_search_apps() -> None:
    """Test searching for apps by query string."""
    # Test searching in name
    note_apps = search_apps("note")
    assert len(note_apps) > 0

    # Test searching in description
    privacy_apps = search_apps("privacy")
    assert len(privacy_apps) > 0

    # Test searching in tags
    markdown_apps = search_apps("markdown")
    assert len(markdown_apps) > 0

    # Test with no matches
    non_existent = search_apps("this_should_not_match_anything")
    assert len(non_existent) == 0

    # Test case insensitivity
    note_case_insensitive = search_apps("NoTe")
    assert len(note_case_insensitive) > 0
    assert len(note_case_insensitive) == len(note_apps)


def test_get_categories() -> None:
    """Test retrieving all categories from the catalog."""
    categories = get_categories()
    assert len(categories) > 0
    assert "Productivity" in categories
    assert "Media" in categories

    # Check that categories are sorted
    assert categories == sorted(categories)

    # Check that each category in the result is unique
    assert len(categories) == len(set(categories))


def test_sync_with_icon_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test synchronization with icon paths.

    Args:
        monkeypatch: Pytest fixture for patching
    """
    # Create a mock logger
    mock_logger = MagicMock()
    monkeypatch.setattr("src.app_catalog.logger", mock_logger)

    # Create a mock ICON_PATHS with some missing entries
    mock_icon_paths = {"joplin": {"exact_path": "path/to/icon.png", "filename": "joplin_icon.png"}}
    monkeypatch.setattr("src.app_catalog.ICON_PATHS", mock_icon_paths)

    # Run the sync function
    sync_with_icon_paths()

    # Check that warnings were logged for missing icons
    assert mock_logger.warning.called
