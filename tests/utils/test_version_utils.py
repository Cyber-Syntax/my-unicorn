#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for version utility functions.

This module contains tests for the version utility functions in src/utils/version_utils.py.
"""


import pytest

from src.utils.version_utils import (
    normalize_version_for_comparison,
    extract_base_version,
    extract_version,
    extract_version_from_filename,
    repo_uses_beta,
)


class TestNormalizeVersionForComparison:
    """Tests for normalize_version_for_comparison function."""

    def test_normal_versions(self) -> None:
        """Test normalizing regular version strings."""
        assert normalize_version_for_comparison("1.2.3") == "1.2.3"
        assert normalize_version_for_comparison("0.10.5") == "0.10.5"
        assert normalize_version_for_comparison("2.0.0") == "2.0.0"

    def test_with_v_prefix(self) -> None:
        """Test normalizing versions with 'v' prefix."""
        assert normalize_version_for_comparison("v1.2.3") == "1.2.3"
        assert normalize_version_for_comparison("V1.2.3") == "1.2.3"
        assert normalize_version_for_comparison("v0.10.5") == "0.10.5"

    def test_with_suffix(self) -> None:
        """Test normalizing versions with suffixes."""
        assert normalize_version_for_comparison("1.2.3-beta") == "1.2.3-beta"
        assert normalize_version_for_comparison("v1.2.3-rc1") == "1.2.3-rc1"
        assert normalize_version_for_comparison("1.2.3+build123") == "1.2.3+build123"

    def test_with_none(self) -> None:
        """Test normalizing None value."""
        assert normalize_version_for_comparison(None) == ""

    def test_with_empty_string(self) -> None:
        """Test normalizing empty string."""
        assert normalize_version_for_comparison("") == ""


class TestExtractBaseVersion:
    """Tests for extract_base_version function."""

    def test_simple_versions(self) -> None:
        """Test extracting base from simple version strings."""
        assert extract_base_version("1.2.3") == "1.2.3"
        assert extract_base_version("0.10.5") == "0.10.5"
        assert extract_base_version("2.0.0") == "2.0.0"

    def test_beta_versions(self) -> None:
        """Test extracting base from beta version strings."""
        assert extract_base_version("1.2.3-beta") == "1.2.3"
        assert extract_base_version("1.2.3-beta.1") == "1.2.3"
        assert extract_base_version("1.2.3-rc1") == "1.2.3"

    def test_build_versions(self) -> None:
        """Test extracting base from version strings with build metadata."""
        assert extract_base_version("1.2.3+build123") == "1.2.3"
        assert extract_base_version("1.2.3+20230425") == "1.2.3"

    def test_underscore_versions(self) -> None:
        """Test extracting base from version strings with underscore."""
        assert extract_base_version("1.2.3_alpha") == "1.2.3"
        assert extract_base_version("1.2.3_dev") == "1.2.3"


class TestExtractVersion:
    """Tests for extract_version function."""

    def test_standard_versions(self) -> None:
        """Test extracting standard semantic versions."""
        assert extract_version("v1.2.3") == "1.2.3"
        assert extract_version("1.2.3") == "1.2.3"
        assert extract_version("0.10.5") == "0.10.5"
        assert extract_version("2.0.0") == "2.0.0"

    def test_beta_versions(self) -> None:
        """Test extracting versions from beta tags."""
        assert extract_version("v1.2.3-beta", False) == "1.2.3"
        assert extract_version("v1.2.3-beta", True) == "1.2.3"
        assert extract_version("v1.2.3-beta.1", True) == "1.2.3"

    def test_stable_suffix(self) -> None:
        """Test extracting versions with stable suffix."""
        assert extract_version("v1.2.3-stable") == "1.2.3"
        assert extract_version("1.2.3-stable") == "1.2.3"

    def test_prefixed_versions(self) -> None:
        """Test extracting versions with prefixes."""
        assert extract_version("release-1.2.3") == "1.2.3"
        assert extract_version("version-1.2.3") == "1.2.3"
        assert extract_version("app-1.2.3") == "1.2.3"

    def test_non_standard_versions(self) -> None:
        """Test extracting non-standard version formats."""
        assert extract_version("version10") == "10"
        assert extract_version("v10") == "10"
        assert extract_version("release10.2") == "10.2"

    def test_complex_tags(self) -> None:
        """Test extracting versions from complex tag formats."""
        assert extract_version("app-v1.2.3-linux-x86_64") == "1.2.3"
        assert extract_version("release_1.2.3_20230425") == "1.2.3"


class TestExtractVersionFromFilename:
    """Tests for extract_version_from_filename function."""

    def test_standard_patterns(self) -> None:
        """Test extracting versions from standard filename patterns."""
        assert extract_version_from_filename("app-1.2.3-x86_64.AppImage") == "1.2.3"
        assert extract_version_from_filename("app-v1.2.3.AppImage") == "1.2.3"
        assert extract_version_from_filename("app-linux-1.2.3.AppImage") == "1.2.3"

    def test_complex_filenames(self) -> None:
        """Test extracting versions from complex filenames."""
        assert extract_version_from_filename("app-linux-x86_64-1.2.3.AppImage") == "1.2.3"
        assert extract_version_from_filename("app_1.2.3_amd64.deb") == "1.2.3"
        assert extract_version_from_filename("app-1.2.3+20230425-x86_64.AppImage") == "1.2.3"

    def test_missing_version(self) -> None:
        """Test filenames with missing version information."""
        assert extract_version_from_filename("app-latest.AppImage") is None
        assert extract_version_from_filename("app.deb") is None
        assert extract_version_from_filename("latest.AppImage") is None

    def test_with_none(self) -> None:
        """Test with None input."""
        assert extract_version_from_filename(None) is None


class TestRepoUsesBeta:
    """Tests for repo_uses_beta function."""

    def test_known_beta_repos(self) -> None:
        """Test known repositories that use beta releases."""
        assert repo_uses_beta("FreeTube") is True

    def test_other_repos(self) -> None:
        """Test repositories not known to use beta releases."""
        assert repo_uses_beta("some-repo") is False
        assert repo_uses_beta("another-app") is False
        assert repo_uses_beta("") is False
