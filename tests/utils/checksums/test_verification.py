#!/usr/bin/env python3
"""Tests for the checksums verification module."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.utils.checksums.verification import (
    handle_release_description_verification,
    verify_checksum,
    verify_file,
)


class TestChecksumVerification:
    """Test suite for the checksum verification functionality."""

    SAMPLE_CHECKSUM = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    SAMPLE_CHECKSUMS_FILE_CONTENT = f"{SAMPLE_CHECKSUM}  test-file.AppImage\n"

    @pytest.fixture
    def setup_test_file(self):
        """Create a test file with known content for checksum verification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file with predictable content
            file_path = os.path.join(temp_dir, "test-file.AppImage")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("Test file content")

            # Create a checksums file
            checksums_path = os.path.join(temp_dir, "SHA256SUMS.txt")
            with open(checksums_path, "w", encoding="utf-8") as f:
                f.write(self.SAMPLE_CHECKSUMS_FILE_CONTENT)

            yield file_path, checksums_path, temp_dir

    def test_verify_file_success(self, setup_test_file):
        """Test successful file verification with matching checksums."""
        file_path, checksums_path, _ = setup_test_file

        # Mock the actual checksum calculation to return our fixed value
        with patch("my_unicorn.utils.checksums.verification.calculate_file_checksum") as mock_calc:
            mock_calc.return_value = self.SAMPLE_CHECKSUM

            result = verify_file(file_path, checksums_path)

            assert result is True
            mock_calc.assert_called_once_with(file_path, "sha256")

    def test_verify_file_failure(self, setup_test_file):
        """Test file verification failure with non-matching checksums."""
        file_path, checksums_path, _ = setup_test_file

        # Mock the actual checksum calculation to return a different value
        with patch("my_unicorn.utils.checksums.verification.calculate_file_checksum") as mock_calc:
            mock_calc.return_value = "different_checksum_value"

            result = verify_file(file_path, checksums_path)

            assert result is False
            mock_calc.assert_called_once_with(file_path, "sha256")

    def test_verify_file_missing_file(self, setup_test_file):
        """Test verification with missing file."""
        _, checksums_path, _ = setup_test_file
        nonexistent_file = "/tmp/nonexistent-file.AppImage"

        with pytest.raises(FileNotFoundError):
            verify_file(nonexistent_file, checksums_path)

    def test_verify_file_missing_checksums_file(self, setup_test_file):
        """Test verification with missing checksums file."""
        file_path, _, _ = setup_test_file
        nonexistent_checksums = "/tmp/nonexistent-checksums.txt"

        with pytest.raises(FileNotFoundError):
            verify_file(file_path, nonexistent_checksums)

    def test_verify_file_empty_checksums_file(self, setup_test_file):
        """Test verification with empty checksums file."""
        file_path, _, temp_dir = setup_test_file
        empty_checksums_path = os.path.join(temp_dir, "EMPTY.txt")
        with open(empty_checksums_path, "w", encoding="utf-8") as f:
            pass  # Create empty file

        with pytest.raises(ValueError, match="No checksums found"):
            verify_file(file_path, empty_checksums_path)

    def test_verify_file_no_matching_checksums(self, setup_test_file):
        """Test verification with no matching checksums for the file."""
        file_path, _, temp_dir = setup_test_file

        # Create checksums file with entries for other files
        other_checksums_path = os.path.join(temp_dir, "OTHER.txt")
        with open(other_checksums_path, "w", encoding="utf-8") as f:
            f.write(
                "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  other-file.AppImage\n"
            )

        with pytest.raises(ValueError, match="No checksum entry found"):
            verify_file(file_path, other_checksums_path)

    def test_verify_checksum_success(self):
        """Test successful checksum verification."""
        result = verify_checksum(
            "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "test-file.AppImage",
            "sha256",
        )
        assert result is True

    def test_verify_checksum_failure(self):
        """Test checksum verification failure."""
        result = verify_checksum(
            "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "different_checksum_value",
            "test-file.AppImage",
            "sha256",
        )
        assert result is False

    @patch("my_unicorn.utils.checksums.extractor.ReleaseChecksumExtractor")
    @patch("my_unicorn.utils.checksums.verification.verify_file")
    def test_handle_release_description_verification_success(
        self, mock_verify, mock_extractor_class
    ):
        """Test successful verification using release description."""
        # set up the mocks
        mock_extractor_instance = MagicMock()
        mock_extractor_class.return_value = mock_extractor_instance
        mock_extractor_instance.write_checksums_file.return_value = "/tmp/checksums.txt"
        mock_verify.return_value = True

        result = handle_release_description_verification(
            appimage_path="/tmp/app.AppImage",
            owner="zen-browser",
            repo="desktop",
            cleanup_on_failure=True,
        )

        assert result is True
        mock_extractor_instance.fetch_release_description.assert_called_once()
        mock_extractor_instance.write_checksums_file.assert_called_once()
        mock_verify.assert_called_once_with("/tmp/app.AppImage", "/tmp/checksums.txt")

    @patch("my_unicorn.utils.checksums.extractor.ReleaseChecksumExtractor")
    @patch("my_unicorn.utils.checksums.verification.verify_file")
    def test_handle_release_description_verification_failure(
        self, mock_verify, mock_extractor_class
    ):
        """Test verification failure using release description."""
        # set up the mocks
        mock_extractor_instance = MagicMock()
        mock_extractor_class.return_value = mock_extractor_instance
        mock_extractor_instance.write_checksums_file.return_value = "/tmp/checksums.txt"
        mock_verify.return_value = False

        # Mock os.remove for cleanup
        with patch("os.remove") as mock_remove:
            result = handle_release_description_verification(
                appimage_path="/tmp/app.AppImage",
                owner="zen-browser",
                repo="desktop",
                cleanup_on_failure=True,
            )

            assert result is False
            mock_extractor_instance.fetch_release_description.assert_called_once()
            mock_extractor_instance.write_checksums_file.assert_called_once()
            mock_verify.assert_called_once_with("/tmp/app.AppImage", "/tmp/checksums.txt")
            mock_remove.assert_called_once_with("/tmp/checksums.txt")

    @patch("my_unicorn.utils.checksums.extractor.ReleaseChecksumExtractor")
    def test_handle_release_description_verification_fetch_error(self, mock_extractor_class):
        """Test handling fetch error in release description verification."""
        # set up the mocks to simulate a fetch error
        mock_extractor_instance = MagicMock()
        mock_extractor_class.return_value = mock_extractor_instance
        mock_extractor_instance.fetch_release_description.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            handle_release_description_verification(
                appimage_path="/tmp/app.AppImage", owner="zen-browser", repo="desktop"
            )

        mock_extractor_instance.fetch_release_description.assert_called_once()
        mock_extractor_instance.write_checksums_file.assert_not_called()
