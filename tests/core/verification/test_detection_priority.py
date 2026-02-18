"""Tests for prioritize_checksum_files function.

This module provides comprehensive tests for the checksum file prioritization
function, which orders files by relevance (exact matches, platform-specific,
YAML, etc.) for better verification success.
"""

from __future__ import annotations

from my_unicorn.core.github import ChecksumFileInfo
from my_unicorn.core.verification.detection import prioritize_checksum_files


class TestPrioritizeChecksumFiles:
    """Test prioritize_checksum_files function."""

    def test_prioritize_checksum_files_empty_list(self) -> None:
        """Test with empty checksum files list."""
        result = prioritize_checksum_files([], "app.AppImage")

        assert result == []

    def test_prioritize_checksum_files_single_file(self) -> None:
        """Test with single checksum file."""
        checksum_files = [
            ChecksumFileInfo(
                filename="checksums.txt",
                url="https://example.com/checksums.txt",
                format_type="traditional",
            )
        ]

        result = prioritize_checksum_files(checksum_files, "app.AppImage")

        assert len(result) == 1
        assert result[0].filename == "checksums.txt"

    def test_prioritize_checksum_files_prioritize_exact_digest(self) -> None:
        """Test that exact .DIGEST match gets priority 1."""
        checksum_files = [
            ChecksumFileInfo(
                filename="SHA256SUMS.txt",
                url="https://example.com/SHA256SUMS.txt",
                format_type="traditional",
            ),
            ChecksumFileInfo(
                filename="app.AppImage.DIGEST",
                url="https://example.com/app.AppImage.DIGEST",
                format_type="traditional",
            ),
        ]

        result = prioritize_checksum_files(checksum_files, "app.AppImage")

        assert result[0].filename == "app.AppImage.DIGEST"

    def test_prioritize_checksum_files_prioritize_platform_specific(
        self,
    ) -> None:
        """Test that platform-specific files get priority 2."""
        checksum_files = [
            ChecksumFileInfo(
                filename="SHA256SUMS.txt",
                url="https://example.com/SHA256SUMS.txt",
                format_type="traditional",
            ),
            ChecksumFileInfo(
                filename="app.AppImage.sha256",
                url="https://example.com/app.AppImage.sha256",
                format_type="traditional",
            ),
        ]

        result = prioritize_checksum_files(checksum_files, "app.AppImage")

        assert result[0].filename == "app.AppImage.sha256"

    def test_prioritize_checksum_files_prioritize_yaml(self) -> None:
        """Test that YAML files get priority 3."""
        checksum_files = [
            ChecksumFileInfo(
                filename="SHA256SUMS.txt",
                url="https://example.com/SHA256SUMS.txt",
                format_type="traditional",
            ),
            ChecksumFileInfo(
                filename="latest-linux.yml",
                url="https://example.com/latest-linux.yml",
                format_type="yaml",
            ),
        ]

        result = prioritize_checksum_files(checksum_files, "app.AppImage")

        assert result[0].filename == "latest-linux.yml"

    def test_prioritize_checksum_files_complex_priority_order(self) -> None:
        """Test complex scenario with multiple priority levels."""
        checksum_files = [
            ChecksumFileInfo(
                filename="SHA256SUMS.txt",
                url="https://example.com/SHA256SUMS.txt",
                format_type="traditional",
            ),
            ChecksumFileInfo(
                filename="latest.yml",
                url="https://example.com/latest.yml",
                format_type="yaml",
            ),
            ChecksumFileInfo(
                filename="app.AppImage.DIGEST",
                url="https://example.com/app.AppImage.DIGEST",
                format_type="traditional",
            ),
            ChecksumFileInfo(
                filename="app.AppImage.sha512",
                url="https://example.com/app.AppImage.sha512",
                format_type="traditional",
            ),
        ]

        result = prioritize_checksum_files(checksum_files, "app.AppImage")

        priorities = [cf.filename for cf in result]
        assert priorities[0] == "app.AppImage.DIGEST"  # Priority 1
        assert priorities[1] == "app.AppImage.sha512"  # Priority 2
        assert priorities[2] == "latest.yml"  # Priority 3
        assert priorities[3] == "SHA256SUMS.txt"  # Priority 5

    def test_prioritize_checksum_files_case_insensitive(self) -> None:
        """Test that digest matching is case-insensitive."""
        checksum_files = [
            ChecksumFileInfo(
                filename="SHA256SUMS.txt",
                url="https://example.com/SHA256SUMS.txt",
                format_type="traditional",
            ),
            ChecksumFileInfo(
                filename="app.AppImage.digest",
                url="https://example.com/app.AppImage.digest",
                format_type="traditional",
            ),
        ]

        result = prioritize_checksum_files(checksum_files, "app.AppImage")

        assert result[0].filename == "app.AppImage.digest"

    def test_prioritize_checksum_files_experimental_penalty(self) -> None:
        """Test that experimental variants get lower priority."""
        checksum_files = [
            ChecksumFileInfo(
                filename="SHA256SUMS.txt",
                url="https://example.com/SHA256SUMS.txt",
                format_type="traditional",
            ),
            ChecksumFileInfo(
                filename="SHA256SUMS-EXPERIMENTAL.txt",
                url="https://example.com/SHA256SUMS-EXPERIMENTAL.txt",
                format_type="traditional",
            ),
        ]

        result = prioritize_checksum_files(checksum_files, "app.AppImage")

        assert result[0].filename == "SHA256SUMS.txt"
        assert result[1].filename == "SHA256SUMS-EXPERIMENTAL.txt"

    def test_prioritize_checksum_files_multiple_yaml(self) -> None:
        """Test with multiple YAML files."""
        checksum_files = [
            ChecksumFileInfo(
                filename="latest-mac.yml",
                url="https://example.com/latest-mac.yml",
                format_type="yaml",
            ),
            ChecksumFileInfo(
                filename="latest-linux.yml",
                url="https://example.com/latest-linux.yml",
                format_type="yaml",
            ),
        ]

        result = prioritize_checksum_files(checksum_files, "app.AppImage")

        assert len(result) == 2
        assert all(cf.format_type == "yaml" for cf in result)

    def test_prioritize_checksum_files_all_sha512_variants(self) -> None:
        """Test prioritization of different SHA512 filename formats."""
        checksum_files = [
            ChecksumFileInfo(
                filename="SHA512SUMS",
                url="https://example.com/SHA512SUMS",
                format_type="traditional",
            ),
            ChecksumFileInfo(
                filename="app.AppImage.sha512sum",
                url="https://example.com/app.AppImage.sha512sum",
                format_type="traditional",
            ),
        ]

        result = prioritize_checksum_files(checksum_files, "app.AppImage")

        assert result[0].filename == "app.AppImage.sha512sum"
        assert result[1].filename == "SHA512SUMS"
