"""Tests for domain/version.py module."""

import pytest

from my_unicorn.domain.version import normalize_version


class TestNormalizeVersion:
    """Tests for version normalization."""

    @pytest.mark.parametrize(
        ("input_version", "expected"),
        [
            # Alpha versions
            ("1.0.0-alpha", "1.0.0a0"),
            ("2.1.0-alpha", "2.1.0a0"),
            ("1.0.0-alpha1", "1.0.0a1"),
            # Beta versions
            ("2.0.0-beta", "2.0.0b0"),
            ("2.0.0-beta1", "2.0.0b1"),
            ("3.5.2-beta5", "3.5.2b5"),
            # RC versions
            ("3.0.0-rc", "3.0.0rc0"),
            ("3.0.0-rc2", "3.0.0rc2"),
            ("1.2.3-rc10", "1.2.3rc10"),
            # v-prefix handling
            ("v1.0.0-alpha", "1.0.0a0"),
            ("v2.0.0-beta1", "2.0.0b1"),
            ("v3.0.0-rc2", "3.0.0rc2"),
            ("v1.2.3", "1.2.3"),
            # Standard versions (no prerelease)
            ("1.2.3", "1.2.3"),
            ("2.0.0", "2.0.0"),
            ("10.5.3", "10.5.3"),
            # Already PEP 440 format
            ("1.0.0a0", "1.0.0a0"),
            ("2.0.0b1", "2.0.0b1"),
            ("3.0.0rc2", "3.0.0rc2"),
        ],
    )
    def test_normalize_version(
        self, input_version: str, expected: str
    ) -> None:
        """Test version normalization with various formats."""
        assert normalize_version(input_version) == expected

    def test_normalize_version_no_match(self) -> None:
        """Test that non-matching versions are returned as-is."""
        # These don't match the regex pattern, so they're returned unchanged
        assert normalize_version("not-a-version") == "not-a-version"
        assert normalize_version("1.2") == "1.2"
        assert normalize_version("1.2.3.4") == "1.2.3.4"
