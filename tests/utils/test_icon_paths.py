#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for icon path utility functions.

This module contains tests for the icon path utility functions in src/utils/icon_paths.py.
"""

from typing import Dict, Any, Optional

import pytest

from src.utils.icon_paths import get_icon_paths, ICON_PATHS


class TestGetIconPaths:
    """Tests for get_icon_paths function."""

    def test_exact_repo_match(self) -> None:
        """Test getting icon paths with exact repository name match."""
        # Test with a known repository
        result = get_icon_paths("joplin")

        assert result is not None
        assert "exact_path" in result
        assert "paths" in result
        assert "filename" in result
        assert result["exact_path"] == "Assets/LinuxIcons/256x256.png"
        assert result["filename"] == "joplin_icon.png"

    def test_case_insensitive_match(self) -> None:
        """Test case-insensitive repository name matching."""
        # Test with uppercase
        upper_result = get_icon_paths("JOPLIN")
        lower_result = get_icon_paths("joplin")

        assert upper_result is not None
        assert upper_result == lower_result

        # Test with mixed case
        mixed_result = get_icon_paths("FreeTube")
        lowercase_result = get_icon_paths("freetube")

        assert mixed_result is not None
        assert mixed_result == lowercase_result

    def test_owner_repo_format(self) -> None:
        """Test repository name with owner/repo format."""
        # Test with owner/repo format
        result = get_icon_paths("siyuan-note/siyuan")

        assert result is not None
        assert "exact_path" in result
        assert result["exact_path"] == "app/src/assets/icon.png"

        # Test with only repo part
        repo_only = get_icon_paths("siyuan")
        assert repo_only == result

    def test_unknown_repo(self) -> None:
        """Test with unknown repository names."""
        # Unknown repository
        result = get_icon_paths("unknown-repo")
        assert result is None

        # Empty repository name
        result = get_icon_paths("")
        assert result is None

        # None repository name
        result = get_icon_paths(None)  # type: ignore
        assert result is None

    def test_all_config_structures(self) -> None:
        """Test all configuration structure variations."""
        # Test repositories with different configuration structures
        # Make sure we can handle all the different ways a repo can be configured

        # Check each repo in ICON_PATHS
        for repo_name, config in ICON_PATHS.items():
            result = get_icon_paths(repo_name)
            assert result is not None
            assert result == config

            # Verify it works with uppercase too
            if repo_name.upper() != repo_name:  # Only if name can be uppercased
                upper_result = get_icon_paths(repo_name.upper())
                assert upper_result is not None
                assert upper_result == config


class TestIconPathsConstant:
    """Tests for the ICON_PATHS constant."""

    def test_icon_paths_structure(self) -> None:
        """Test the structure of the ICON_PATHS dictionary."""
        assert isinstance(ICON_PATHS, dict)

        for repo, config in ICON_PATHS.items():
            # Each repo should have a string key
            assert isinstance(repo, str)
            assert len(repo) > 0

            # Each config should be a dictionary
            assert isinstance(config, dict)

            # Config should have at least one of these keys
            assert "exact_path" in config or "paths" in config

            # Check types of standard fields if present
            if "exact_path" in config:
                assert isinstance(config["exact_path"], str)

            if "paths" in config:
                assert isinstance(config["paths"], list)
                for path in config["paths"]:
                    assert isinstance(path, str)

            if "filename" in config:
                assert isinstance(config["filename"], str)
