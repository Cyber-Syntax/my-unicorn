import hashlib
import os
import unittest
from unittest.mock import MagicMock, patch
import base64
from src.verify import VerificationManager


class TestVerificationManager(unittest.TestCase):
    def setUp(self):
        # Create a dummy AppImage file with known content.
        self.appimage_name = "/tmp/dummy.AppImage"
        self.sha_name = "/tmp/dummy.sha256"
        with open(self.appimage_name, "wb") as f:
            f.write(b"dummy content")
        # Compute the correct sha256 hash of the dummy file.
        hash_func = hashlib.sha256()
        hash_func.update(b"dummy content")
        self.correct_hash = hash_func.hexdigest()
        self.vm = VerificationManager(
            sha_name=self.sha_name,
            sha_url="http://example.com/dummy.sha256",
            appimage_name=self.appimage_name,
            hash_type="sha256",
        )

    def tearDown(self):
        # Cleanup created temporary files.
        if os.path.exists(self.appimage_name):
            os.remove(self.appimage_name)
        if os.path.exists(self.sha_name):
            os.remove(self.sha_name)

    @patch("requests.get")
    def test_download_sha_file(self, mock_get):
        # Simulate successful SHA file download.
        fake_response = MagicMock()
        fake_response.text = f"{self.correct_hash}  {os.path.basename(self.appimage_name)}"
        fake_response.raise_for_status = MagicMock()
        mock_get.return_value = fake_response
        self.vm._download_sha_file()
        with open(self.sha_name, encoding="utf-8") as f:
            content = f.read()
        self.assertIn(self.correct_hash, content)

    @patch("requests.get")
    def test_verify_appimage_success(self, mock_get):
        # Simulate a correct SHA file so that verification passes.
        fake_response = MagicMock()
        fake_response.text = f"{self.correct_hash}  {os.path.basename(self.appimage_name)}"
        fake_response.raise_for_status = MagicMock()
        mock_get.return_value = fake_response
        result = self.vm.verify_appimage()
        self.assertTrue(result)

    @patch("requests.get")
    def test_verify_appimage_failure(self, mock_get):
        # Simulate a SHA file with an incorrect hash.
        wrong_hash = "0" * 64
        fake_response = MagicMock()
        fake_response.text = f"{wrong_hash}  {os.path.basename(self.appimage_name)}"
        fake_response.raise_for_status = MagicMock()
        mock_get.return_value = fake_response
        result = self.vm.verify_appimage()
        self.assertFalse(result)

    @patch("requests.get")
    def test_verify_appimage_sha512(self, mock_get):
        # Create a SHA512 verification manager
        sha512_name = "/tmp/dummy.sha512"

        # Compute the correct sha512 hash of the dummy file
        hash_func = hashlib.sha512()
        hash_func.update(b"dummy content")
        correct_sha512 = hash_func.hexdigest()

        vm_sha512 = VerificationManager(
            sha_name=sha512_name,
            sha_url="http://example.com/dummy.sha512",
            appimage_name=self.appimage_name,
            hash_type="sha512",
        )

        # Simulate a correct SHA512 file
        fake_response = MagicMock()
        fake_response.text = f"{correct_sha512}  {os.path.basename(self.appimage_name)}"
        fake_response.raise_for_status = MagicMock()
        mock_get.return_value = fake_response

        # Verify the AppImage using SHA512
        result = vm_sha512.verify_appimage()
        self.assertTrue(result)

        # Clean up
        if os.path.exists(sha512_name):
            os.remove(sha512_name)

    @patch("requests.get")
    def test_download_sha_file_error(self, mock_get):
        # Test error handling when downloading SHA file fails
        mock_get.side_effect = Exception("Connection error")

        with self.assertRaises(IOError):
            # TODO: need to pass names??
            self.vm._download_sha_file()

    def test_unsupported_hash_type(self):
        # Test initialization with unsupported hash type
        with self.assertRaises(ValueError):
            VerificationManager(
                sha_name="/tmp/dummy.md5",
                sha_url="http://example.com/dummy.md5",
                appimage_name=self.appimage_name,
                hash_type="md5",  # This is not in SUPPORTED_HASH_TYPES
            )

    def test_verify_appimage_missing_file(self):
        # Test verification when AppImage file is missing
        os.remove(self.appimage_name)

        # Should return False when file is missing
        result = self.vm.verify_appimage()
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
