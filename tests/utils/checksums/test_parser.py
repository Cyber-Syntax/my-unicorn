#!/usr/bin/env python3
"""Tests for the GitHub release checksums parser module."""

import pytest

from src.utils.checksums.parser import parse_checksums_from_description


class TestChecksumParser:
    """Test suite for the checksum parser functionality."""

    SAMPLE_RELEASE_DESC = """# Zen Browser Release

## Changelog
- Feature 1
- Feature 2

<details>
<summary>File Checksums (SHA-256)</summary>

```
abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage
bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  zen-aarch64.AppImage
```
</details>
"""

    GITHUB_STYLE_RELEASE_DESC = """# Release v1.0.0

## SHA256 Checksums

```
abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage
bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  zen-aarch64.AppImage
```
"""

    ALTERNATE_FORMAT_DESC = """# Release v1.0.0

## Checksums
zen-x86_64.AppImage abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
zen-aarch64.AppImage bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab
"""

    STAR_FORMAT_DESC = """# Release v1.0.0

## SHA256 Checksums

```
abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890 *zen-x86_64.AppImage
bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab *zen-aarch64.AppImage
```
"""

    EMPTY_DESC = ""
    NO_CHECKSUMS_DESC = "# Release without checksums\n\nThis release has no checksums section."

    def test_parse_checksums_standard_format(self):
        """Test parsing checksums from standard GitHub release description format."""
        checksums = parse_checksums_from_description(self.SAMPLE_RELEASE_DESC)
        
        assert len(checksums) == 2
        assert "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage" in checksums
        assert "bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  zen-aarch64.AppImage" in checksums

    def test_parse_checksums_github_header_format(self):
        """Test parsing checksums from GitHub header style format."""
        checksums = parse_checksums_from_description(self.GITHUB_STYLE_RELEASE_DESC)
        
        assert len(checksums) == 2
        assert "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage" in checksums
        assert "bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  zen-aarch64.AppImage" in checksums

    def test_parse_checksums_alternate_format(self):
        """Test parsing checksums from alternate format with filename first."""
        checksums = parse_checksums_from_description(self.ALTERNATE_FORMAT_DESC)
        
        assert len(checksums) == 2
        # The parser should normalize all checksums to the standard format
        assert "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage" in checksums
        assert "bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  zen-aarch64.AppImage" in checksums

    def test_parse_checksums_with_stars(self):
        """Test parsing checksums with star notation (*filename)."""
        checksums = parse_checksums_from_description(self.STAR_FORMAT_DESC)
        
        assert len(checksums) == 2
        assert "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage" in checksums
        assert "bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  zen-aarch64.AppImage" in checksums

    def test_parse_empty_description(self):
        """Test parsing an empty description."""
        checksums = parse_checksums_from_description(self.EMPTY_DESC)
        assert len(checksums) == 0

    def test_parse_description_without_checksums(self):
        """Test parsing a description without checksums section."""
        checksums = parse_checksums_from_description(self.NO_CHECKSUMS_DESC)
        assert len(checksums) == 0

    def test_parse_description_with_malformed_checksums(self):
        """Test parsing description with malformed checksums."""
        malformed_desc = """# Release
        
## Checksums
- Not a valid checksum line
abcdef  too-short-value
"""
        checksums = parse_checksums_from_description(malformed_desc)
        assert len(checksums) == 0