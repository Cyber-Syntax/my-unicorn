#!/usr/bin/env python3
"""Tests for the checksums storage module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from my_unicorn.utils.checksums.storage import save_checksums_file


class TestChecksumStorage:
    """Test suite for the checksum storage functionality."""

    SAMPLE_CHECKSUMS = [
        "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage",
        "bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  zen-aarch64.AppImage",
    ]

    def test_save_checksums_file(self):
        """Test saving checksums to a file using a temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "SHA256SUMS.txt")

            result = save_checksums_file(self.SAMPLE_CHECKSUMS, output_path)

            # Check that the file was created and has the right content
            assert result == output_path
            assert os.path.exists(output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
                for checksum in self.SAMPLE_CHECKSUMS:
                    assert checksum in content

    def test_save_checksums_file_with_pathlib_path(self):
        """Test saving checksums to a file using a pathlib.Path object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "SHA256SUMS.txt"

            result = save_checksums_file(self.SAMPLE_CHECKSUMS, output_path)

            # Check that the file was created and has the right content
            assert str(result) == str(output_path)
            assert output_path.exists()

            content = output_path.read_text(encoding="utf-8")
            for checksum in self.SAMPLE_CHECKSUMS:
                assert checksum in content

    def test_save_checksums_file_empty_list(self):
        """Test saving an empty checksums list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "SHA256SUMS.txt")

            result = save_checksums_file([], output_path)

            # Check that the file was created and is empty
            assert result == output_path
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) == 0

    def test_save_checksums_file_directory_not_exists(self):
        """Test saving checksums to a directory that doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a path with a non-existent subdirectory
            subdir = os.path.join(temp_dir, "subdir")
            output_path = os.path.join(subdir, "SHA256SUMS.txt")

            result = save_checksums_file(self.SAMPLE_CHECKSUMS, output_path)

            # Check that the directory was created and the file exists
            assert result == output_path
            assert os.path.exists(output_path)
            assert os.path.isdir(subdir)

    def test_save_checksums_file_permission_error(self):
        """Test handling permission error when saving checksums."""
        with patch("builtins.open", mock_open()) as m:
            m.side_effect = PermissionError("Permission denied")

            with pytest.raises(PermissionError) as excinfo:
                save_checksums_file(self.SAMPLE_CHECKSUMS, "/root/test.txt")

            assert "Permission denied" in str(excinfo.value)

    def test_save_checksums_file_io_error(self):
        """Test handling IO error when saving checksums."""
        with patch("builtins.open", mock_open()) as m:
            m.side_effect = IOError("Disk full")

            with pytest.raises(IOError) as excinfo:
                save_checksums_file(self.SAMPLE_CHECKSUMS, "/tmp/test.txt")

            assert "Disk full" in str(excinfo.value)

    def test_save_checksums_file_custom_mode(self):
        """Test saving checksums with a custom file mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "SHA256SUMS.txt")

            # First create the file with some content
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("Initial content\n")

            # Now append to it
            result = save_checksums_file(self.SAMPLE_CHECKSUMS, output_path, mode="a")

            # Check that the file was updated
            assert result == output_path

            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "Initial content" in content
                for checksum in self.SAMPLE_CHECKSUMS:
                    assert checksum in content
