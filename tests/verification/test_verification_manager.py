"""Test the refactored verification system.

This test verifies that the new modular verification system works correctly
and maintains compatibility with the original interface.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.verification import VerificationManager


class TestVerificationManager(unittest.TestCase):
    """Test the main VerificationManager functionality."""

    def setUp(self) -> None:
        """set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_appimage = os.path.join(self.temp_dir, "test.AppImage")
        self.test_sha = os.path.join(self.temp_dir, "test.sha256")

        # Create a test AppImage file with known content
        test_content = b"test appimage content"
        with open(self.test_appimage, "wb") as f:
            f.write(test_content)

        # Calculate expected SHA256 hash
        import hashlib

        self.expected_hash = hashlib.sha256(test_content).hexdigest()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self) -> None:
        """Test that VerificationManager initializes correctly."""
        manager = VerificationManager(appimage_name="test.AppImage", hash_type="sha256")

        self.assertEqual(manager.appimage_name, "test.AppImage")
        self.assertEqual(manager.hash_type, "sha256")
        self.assertIsNotNone(manager.config)
        self.assertIsNotNone(manager.logger)
        self.assertIsNotNone(manager.cleanup)

    def test_set_appimage_path(self) -> None:
        """Test setting AppImage path."""
        manager = VerificationManager(appimage_name="test.AppImage", hash_type="sha256")

        manager.set_appimage_path(self.test_appimage)
        self.assertEqual(manager.appimage_path, self.test_appimage)

    def test_verification_skipped_no_hash(self) -> None:
        """Test that verification is skipped when hash_type is no_hash."""
        manager = VerificationManager(
            appimage_name="test.AppImage", hash_type="no_hash", appimage_path=self.test_appimage
        )

        result = manager.verify_appimage()
        self.assertTrue(result)

    @patch("src.global_config.GlobalConfigManager")
    def test_direct_hash_verification(self, mock_config) -> None:
        """Test verification with direct hash."""
        mock_config.return_value.expanded_app_download_path = self.temp_dir

        manager = VerificationManager(
            appimage_name="test.AppImage",
            hash_type="sha256",
            appimage_path=self.test_appimage,
            sha_name="extracted_checksum",
            direct_expected_hash=self.expected_hash,
        )

        result = manager.verify_appimage()
        self.assertTrue(result)

    @patch("src.global_config.GlobalConfigManager")
    def test_direct_hash_verification_failure(self, mock_config) -> None:
        """Test verification failure with wrong direct hash."""
        mock_config.return_value.expanded_app_download_path = self.temp_dir

        wrong_hash = "a" * 64  # Wrong hash
        manager = VerificationManager(
            appimage_name="test.AppImage",
            hash_type="sha256",
            appimage_path=self.test_appimage,
            sha_name="extracted_checksum",
            direct_expected_hash=wrong_hash,
        )

        result = manager.verify_appimage()
        self.assertFalse(result)

    @patch("src.global_config.GlobalConfigManager")
    def test_sha_file_verification(self, mock_config) -> None:
        """Test verification with SHA file."""
        mock_config.return_value.expanded_app_download_path = self.temp_dir

        # Create SHA file with correct hash
        with open(self.test_sha, "w", encoding="utf-8") as f:
            f.write(f"{self.expected_hash}  test.AppImage\n")

        manager = VerificationManager(
            appimage_name="test.AppImage",
            hash_type="sha256",
            appimage_path=self.test_appimage,
            sha_name=self.test_sha,
        )

        result = manager.verify_appimage()
        self.assertTrue(result)

    def test_asset_digest_verification(self) -> None:
        """Test verification with asset digest."""
        asset_digest = f"sha256:{self.expected_hash}"

        manager = VerificationManager(
            appimage_name="test.AppImage",
            hash_type="asset_digest",
            appimage_path=self.test_appimage,
            asset_digest=asset_digest,
        )

        result = manager.verify_appimage()
        self.assertTrue(result)

    def test_missing_appimage_file(self) -> None:
        """Test behavior when AppImage file is missing."""
        manager = VerificationManager(
            appimage_name="missing.AppImage",
            hash_type="sha256",
            appimage_path="/nonexistent/path/missing.AppImage",
            direct_expected_hash=self.expected_hash,
            sha_name="extracted_checksum",
        )

        result = manager.verify_appimage()
        self.assertFalse(result)

    def test_backwards_compatibility(self) -> None:
        """Test that the old interface still works."""
        from src.verify import VerificationManager as OldVerificationManager
        from src.verify import SUPPORTED_HASH_TYPES, STATUS_SUCCESS, STATUS_FAIL

        # Test that we can still import from the old location
        manager = OldVerificationManager(appimage_name="test.AppImage", hash_type="sha256")

        self.assertEqual(manager.appimage_name, "test.AppImage")
        self.assertEqual(manager.hash_type, "sha256")

        # Test constants are available
        self.assertIn("sha256", SUPPORTED_HASH_TYPES)
        self.assertEqual(STATUS_SUCCESS, "✓ ")
        self.assertEqual(STATUS_FAIL, "✗ ")


if __name__ == "__main__":
    unittest.main()
