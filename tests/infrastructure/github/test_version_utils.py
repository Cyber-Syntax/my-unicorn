"""Tests for GitHub version utilities.

Tests cover version extraction and validation for GitHub releases.
"""

from my_unicorn.infrastructure.github.version_utils import (
    extract_and_validate_version,
)


class TestExtractAndValidateVersion:
    """Test extract_and_validate_version function."""

    def test_valid_extraction_and_validation(self) -> None:
        """Test valid extraction and validation."""
        result = extract_and_validate_version("package@1.2.3")
        assert result == "1.2.3"

    def test_invalid_version_returns_none(self) -> None:
        """Test invalid version returns None."""
        result = extract_and_validate_version("package@abc")
        assert result is None

    def test_valid_complex_package(self) -> None:
        """Test valid complex package."""
        result = extract_and_validate_version("@standardnotes/desktop@3.198.1")
        assert result == "3.198.1"

    def test_simple_version_string(self) -> None:
        """Test simple version string."""
        result = extract_and_validate_version("v1.2.3")
        assert result == "1.2.3"

    def test_empty_string(self) -> None:
        """Test empty string."""
        result = extract_and_validate_version("")
        assert result is None
