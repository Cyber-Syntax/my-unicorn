import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add the project root to sys.path so that the 'src' package can be imported.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.app_config import AppConfigManager


class TestAppConfigManager(unittest.TestCase):
    """Test cases for AppConfigManager class"""

    def setUp(self):
        # Create temporary directory for config files
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_dir_path = Path(self.test_dir.name)
        # Update expected config file name based on repo name
        self.expected_config_filename = "test_repo.json"
        self.config_path = self.test_dir_path / self.expected_config_filename

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
            config_folder=self.test_dir_path,  # Use Path object instead of string
        )

        # Act - First, create a temporary config file, then commit it.
        self.assertTrue(config.temp_save_config(), "Temporary config was not saved.")
        self.assertTrue(config.save_config(), "Config commit failed.")

        # Assert - Check file existence and contents
        self.assertTrue(self.config_path.exists(), "Config file was not created.")
        with self.config_path.open(encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["owner"], "test_owner")
            self.assertEqual(data["repo"], "test_repo")
            self.assertEqual(data["version"], "1.0.0")
            self.assertEqual(data["sha_name"], "test_sha.txt")
            self.assertEqual(data["hash_type"], "sha256")
            self.assertEqual(data["appimage_name"], "test-1.0.0.appimage")
            self.assertEqual(data["arch_keyword"], ".appimage")

    def test_load_nonexistent_config(self):
        """Test loading a configuration file that doesn't exist."""
        # Arrange
        config = AppConfigManager(repo="nonexistent_repo", config_folder=self.test_dir_path)

        # Act
        result = config.load_appimage_config("nonexistent.json")

        # Assert
        self.assertIsNone(result, "Should return None for nonexistent config file")

    def test_update_version(self):
        """Test updating version and AppImage name."""
        # Arrange
        config = AppConfigManager(
            owner="test_owner",
            repo="test_repo",
            version="1.0.0",
            appimage_name="old-appimage.appimage",
            config_folder=self.test_dir_path,
        )

        # Ensure config file exists for update
        config.save_config()

        # Act - Update version and appimage name
        config.update_version("2.0.0", "new-appimage.appimage")

        # Assert
        # Reload to verify changes were saved
        config_new = AppConfigManager(repo="test_repo", config_folder=self.test_dir_path)
        config_data = config_new.load_appimage_config("test_repo.json")

        self.assertEqual(config_new.version, "2.0.0")
        self.assertEqual(config_new.appimage_name, "new-appimage.appimage")

    def test_list_json_files(self):
        """Test listing JSON files in configuration directory."""
        # Arrange - Create multiple config files
        config1 = AppConfigManager(repo="app1", config_folder=self.test_dir_path)
        config2 = AppConfigManager(repo="app2", config_folder=self.test_dir_path)

        config1.save_config()
        config2.save_config()

        # Act
        files = config1.list_json_files()

        # Assert
        self.assertEqual(len(files), 2)
        self.assertIn("app1.json", files)
        self.assertIn("app2.json", files)

    def test_to_dict(self):
        """Test conversion of AppConfigManager to dictionary."""
        # Arrange
        config = AppConfigManager(
            owner="test_owner",
            repo="test_repo",
            version="1.0.0",
            sha_name="test_sha.txt",
            hash_type="sha256",
            appimage_name="test-1.0.0.appimage",
            arch_keyword=".appimage",
            config_folder=self.test_dir_path,
        )

        # Act
        config_dict = config.to_dict()

        # Assert
        self.assertEqual(config_dict["owner"], "test_owner")
        self.assertEqual(config_dict["repo"], "test_repo")
        self.assertEqual(config_dict["app_rename"], "test_repo")
        self.assertEqual(config_dict["version"], "1.0.0")
        self.assertEqual(config_dict["sha_name"], "test_sha.txt")
        self.assertEqual(config_dict["hash_type"], "sha256")
        self.assertEqual(config_dict["appimage_name"], "test-1.0.0.appimage")
        self.assertEqual(config_dict["arch_keyword"], ".appimage")

    def test_invalid_json(self):
        """Test loading a configuration file with invalid JSON."""
        # Arrange - Create an invalid JSON file
        invalid_file = self.test_dir_path / "invalid.json"
        with invalid_file.open("w", encoding="utf-8") as f:
            f.write("This is not valid JSON")

        config = AppConfigManager(config_folder=self.test_dir_path)

        # Act & Assert
        with self.assertRaises(ValueError):
            config.load_appimage_config("invalid.json")


if __name__ == "__main__":
    unittest.main()
