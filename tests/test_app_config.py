import json
import os
import tempfile
import unittest

from src.app_config import AppConfigManager


class TestAppConfigManager(unittest.TestCase):
    """Test cases for AppConfigManager class"""

    def setUp(self):
        # Create temporary directory for config files
        self.test_dir = tempfile.TemporaryDirectory()
        # Update expected config file name based on repo name
        self.expected_config_filename = "test_repo.json"
        self.config_path = os.path.join(self.test_dir.name, self.expected_config_filename)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_config_save_load(self):
        """Test saving and loading config file"""
        # Arrange - Create config manager with test path and proper repo name
        config = AppConfigManager(
            owner="test_owner",
            repo="test_repo",  # This will cause the config file to be named "test_repo.json"
            version="1.0.0",
            sha_name="test_sha.txt",
            hash_type="sha256",
            appimage_name="test-1.0.0.appimage",
            arch_keyword=".appimage",
            config_folder=self.test_dir.name
        )

        # Act - First, create a temporary config file, then commit it.
        self.assertTrue(config.temp_save_config(), "Temporary config was not saved.")
        self.assertTrue(config.save_config(), "Config commit failed.")

        # Assert - Check file existence and contents
        self.assertTrue(os.path.exists(self.config_path), "Config file was not created.")
        with open(self.config_path, encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["owner"], "test_owner")
            self.assertEqual(data["repo"], "test_repo")
            self.assertEqual(data["version"], "1.0.0")
            self.assertEqual(data["sha_name"], "test_sha.txt")
            self.assertEqual(data["hash_type"], "sha256")
            self.assertEqual(data["appimage_name"], "test-1.0.0.appimage")
            self.assertEqual(data["arch_keyword"], ".appimage")


if __name__ == '__main__':
    unittest.main()

