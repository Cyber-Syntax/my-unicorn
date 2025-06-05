#!/usr/bin/env python3
"""Tests for the GitHub release checksums extractor module."""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.utils.checksums.extractor import ReleaseChecksumExtractor


class TestReleaseChecksumExtractor:
    """Test suite for the ReleaseChecksumExtractor class."""

    SAMPLE_RELEASE_DESC = """# Zen Browser Release

<details>
<summary>File Checksums (SHA-256)</summary>

```
abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage
bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  zen-aarch64.AppImage
cdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abc  zen-x86_64.AppImage.zsync
```
</details>
"""

    @pytest.fixture
    def extractor(self):
        """Create an extractor with mocked authentication."""
        with patch("src.auth_manager.GitHubAuthManager.get_auth_headers") as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer mock_token"}
            extractor = ReleaseChecksumExtractor("zen-browser", "desktop")
            extractor.release_description = self.SAMPLE_RELEASE_DESC
            yield extractor

    def test_init(self):
        """Test initialization of the extractor."""
        extractor = ReleaseChecksumExtractor("test-owner", "test-repo")
        assert extractor.owner == "test-owner"
        assert extractor.repo == "test-repo"
        assert extractor.release_description is None

    @patch("requests.get")
    def test_fetch_release_description_success(self, mock_get, extractor):
        """Test successful fetching of release description."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"body": self.SAMPLE_RELEASE_DESC}
        mock_get.return_value = mock_response

        result = extractor.fetch_release_description()

        assert result == self.SAMPLE_RELEASE_DESC
        assert extractor.release_description == self.SAMPLE_RELEASE_DESC
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_fetch_release_description_http_error(self, mock_get, extractor):
        """Test handling of HTTP error when fetching release description."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError):
            extractor.fetch_release_description()

        assert extractor.release_description is None
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_fetch_release_description_connection_error(self, mock_get, extractor):
        """Test handling of connection error when fetching release description."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            extractor.fetch_release_description()

        assert extractor.release_description is None
        mock_get.assert_called_once()

    @patch("src.utils.checksums.parser.parse_checksums_from_description")
    def test_parse_checksums_from_description(self, mock_parse, extractor):
        """Test parsing checksums from description."""
        expected_checksums = [
            "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage",
            "bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  zen-aarch64.AppImage",
        ]
        mock_parse.return_value = expected_checksums

        checksums = extractor._parse_checksums_from_description()

        assert checksums == expected_checksums
        mock_parse.assert_called_once_with(self.SAMPLE_RELEASE_DESC)

    def test_extract_checksums_with_target_file(self, extractor):
        """Test extracting checksums for a specific target file."""
        checksums = extractor.extract_checksums("zen-x86_64.AppImage")

        assert len(checksums) == 1
        assert (
            "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage"
            in checksums
        )

    def test_extract_checksums_case_insensitive(self, extractor):
        """Test extracting checksums is case-insensitive."""
        checksums = extractor.extract_checksums("ZEN-X86_64.AppImage")

        assert len(checksums) == 1
        assert (
            "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage"
            in checksums
        )

    def test_extract_checksums_no_match(self, extractor):
        """Test extracting checksums for a file that doesn't match."""
        checksums = extractor.extract_checksums("nonexistent.AppImage")

        # Should return all checksums if no match
        assert len(checksums) == 3

    def test_extract_checksums_no_description(self):
        """Test extracting checksums with no release description."""
        extractor = ReleaseChecksumExtractor("owner", "repo")
        # No description set

        checksums = extractor.extract_checksums("zen-x86_64.AppImage")
        assert len(checksums) == 0

    def test_extract_checksums_empty_description(self, extractor):
        """Test extracting checksums with empty release description."""
        extractor.release_description = ""

        checksums = extractor.extract_checksums("zen-x86_64.AppImage")
        assert len(checksums) == 0

    @patch("tempfile.mktemp")
    def test_write_checksums_file_default_path(self, mock_mktemp, extractor):
        """Test writing checksums to a default temporary file path."""
        mock_mktemp.return_value = "/tmp/test_checksums.txt"

        with patch("builtins.open", MagicMock()) as mock_open:
            file_path = extractor.write_checksums_file("zen-x86_64.AppImage")

            assert file_path == "/tmp/test_checksums.txt"
            mock_open.assert_called_once_with("/tmp/test_checksums.txt", "w", encoding="utf-8")
            mock_open.return_value.__enter__.return_value.write.assert_called_once()

    def test_write_checksums_file_specific_path(self, extractor):
        """Test writing checksums to a specified file path."""
        specific_path = "/tmp/specific_checksums.txt"

        with patch("builtins.open", MagicMock()) as mock_open:
            file_path = extractor.write_checksums_file("zen-x86_64.AppImage", specific_path)

            assert file_path == specific_path
            mock_open.assert_called_once_with(specific_path, "w", encoding="utf-8")
            mock_open.return_value.__enter__.return_value.write.assert_called_once()

    def test_write_checksums_file_permission_error(self, extractor):
        """Test handling permission error when writing checksums file."""
        with patch("builtins.open", MagicMock()) as mock_open:
            mock_open.side_effect = PermissionError("Permission denied")

            with pytest.raises(PermissionError):
                extractor.write_checksums_file("zen-x86_64.AppImage", "/root/test.txt")

    def test_write_checksums_file_no_matching_checksums(self, extractor):
        """Test writing checksums file when no matching checksums are found."""
        with patch("builtins.open", MagicMock()) as mock_open:
            file_path = extractor.write_checksums_file("nonexistent.file", "/tmp/test.txt")

            # Should still create the file with all available checksums
            assert file_path == "/tmp/test.txt"
            mock_open.assert_called_once()
            # All 3 checksums should be written
            write_call_args = mock_open.return_value.__enter__.return_value.write.call_args[0][0]
            assert "zen-x86_64.AppImage" in write_call_args
            assert "zen-aarch64.AppImage" in write_call_args
            assert "zen-x86_64.AppImage.zsync" in write_call_args
