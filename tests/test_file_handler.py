import unittest
from unittest.mock import patch
import sys
import os

# Add the project root to sys.path so that the 'src' package can be imported.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
from src.file_handler import FileHandler


class TestFileHandler(unittest.TestCase):
    def setUp(self):
        # Create a FileHandler instance with dummy paths and settings.
        self.fh = FileHandler(
            appimage_download_folder_path="/tmp/appimages",
            appimage_download_backup_folder_path="/tmp/appimages/backup",
            config_file="/tmp/config.json",
            config_folder="/tmp",
            config_file_name="test.json",
            repo="testrepo",
            version="1.0.0",
            sha_name="test.sha256",
            appimage_name="test.AppImage",
            batch_mode=True,
            keep_backup=True,
        )

    def test_old_appimage_path(self):
        # The old_appimage_path property should correctly join the folder and repo name.
        self.fh.repo = "myrepo"
        self.assertEqual(self.fh.old_appimage_path, "/tmp/appimages/myrepo.AppImage")

    @patch("os.makedirs")
    @patch("builtins.input", lambda prompt: "y")
    def test_ensure_directory_creates_directory(self, mock_makedirs):
        # If the directory does not exist, _ensure_directory should ask and then create it.
        with patch("os.path.exists", return_value=False):
            self.assertTrue(self.fh._ensure_directory("/tmp/newdir"))

    @patch("os.remove")
    @patch("os.path.exists", return_value=True)
    def test_safe_remove(self, mock_exists, mock_remove):
        # _safe_remove should call os.remove when the file exists.
        self.fh._safe_remove("dummy.txt")
        mock_remove.assert_called_with("dummy.txt")

    @patch("os.path.exists", return_value=False)
    def test_make_executable_file_not_found(self, mock_exists):
        # When the target file does not exist, make_executable should raise FileNotFoundError.
        with self.assertRaises(FileNotFoundError):
            self.fh.make_executable("nonexistent")

    @patch("shutil.copy2")
    @patch("os.path.exists", return_value=True)
    @patch("os.makedirs")
    def test_backup_old_appimage(self, mock_makedirs, mock_exists, mock_copy2):
        # backup_old_appimage should call shutil.copy2 with the correct source and destination.
        self.fh.old_appimage_path = "/tmp/appimages/testrepo.AppImage"
        self.fh.backup_path = "/tmp/appimages/backup/testrepo.AppImage"
        self.fh.backup_old_appimage()
        mock_copy2.assert_called_with("/tmp/appimages/testrepo.AppImage", "/tmp/appimages/backup/testrepo.AppImage")

    @patch("shutil.move")
    @patch("os.path.basename", return_value="old.AppImage")
    @patch("os.makedirs")
    def test_rename_and_move_appimage(self, mock_makedirs, mock_basename, mock_move):
        # rename_and_move_appimage should rename and move the file without error.
        self.fh.appimage_name = "old.AppImage"
        self.fh.repo = "testrepo"
        success, error = self.fh.rename_and_move_appimage()
        self.assertTrue(success)
        self.assertEqual(error, "")

if __name__ == '__main__':
    unittest.main()
