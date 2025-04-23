import os
import pytest
import hashlib
from unittest.mock import patch, mock_open, MagicMock
import tempfile
from typing import Dict, Any

from src.verify import VerificationManager, SUPPORTED_HASH_TYPES


class TestVerificationManager:
    """Tests for the VerificationManager class functionality."""

    @pytest.fixture
    def verification_manager(self) -> VerificationManager:
        """Create a basic VerificationManager for testing."""
        return VerificationManager(
            sha_name="test.sha256",
            sha_url="https://example.com/test.sha256",
            appimage_name="test.AppImage",
            hash_type="sha256",
        )

    def test_init(self) -> None:
        """Test initialization with various parameters."""
        # Test with defaults
        vm = VerificationManager()
        assert vm.sha_name is None
        assert vm.sha_url is None
        assert vm.appimage_name is None
        assert vm.hash_type == "sha256"

        # Test with custom values
        vm = VerificationManager(
            sha_name="test.sha512",
            sha_url="https://example.com/test.sha512",
            appimage_name="app.AppImage",
            hash_type="SHA512",  # Test case insensitivity
        )
        assert vm.sha_name == "test.sha512"
        assert vm.sha_url == "https://example.com/test.sha512"
        assert vm.appimage_name == "app.AppImage"
        assert vm.hash_type == "sha512"  # Should be lowercase

        # Test no_hash option
        vm = VerificationManager(hash_type="no_hash")
        assert vm.hash_type == "no_hash"

    def test_validate_hash_type(self) -> None:
        """Test hash type validation."""
        # Test valid hash types
        for hash_type in SUPPORTED_HASH_TYPES:
            vm = VerificationManager(hash_type=hash_type)
            assert vm.hash_type == hash_type

        # Test invalid hash type
        with pytest.raises(ValueError, match="Unsupported hash type"):
            VerificationManager(hash_type="invalid_hash")

    def test_verify_appimage_no_hash(self, verification_manager: VerificationManager) -> None:
        """Test verification when hash_type is no_hash."""
        verification_manager.hash_type = "no_hash"
        assert verification_manager.verify_appimage() is True

    @patch("os.path.exists")
    def test_verify_appimage_no_sha_info(
        self, mock_exists: MagicMock, verification_manager: VerificationManager
    ) -> None:
        """Test verification when no SHA info is available."""
        mock_exists.return_value = True
        verification_manager.sha_name = None
        verification_manager.sha_url = None
        assert verification_manager.verify_appimage() is True

    @patch("os.path.exists")
    def test_verify_appimage_missing_file(
        self, mock_exists: MagicMock, verification_manager: VerificationManager
    ) -> None:
        """Test verification when AppImage file is missing."""
        mock_exists.return_value = False
        assert verification_manager.verify_appimage() is False

    @patch("os.path.exists")
    def test_verify_appimage_fallback(
        self, mock_exists: MagicMock, verification_manager: VerificationManager
    ) -> None:
        """Test verification fallback when SHA name matches AppImage name."""
        mock_exists.return_value = True
        verification_manager.sha_name = verification_manager.appimage_name
        assert verification_manager.verify_appimage() is True

    @patch("src.verify.VerificationManager._download_sha_file")
    @patch("src.verify.VerificationManager._parse_sha_file")
    @patch("os.path.exists")
    def test_verify_appimage_success(
        self,
        mock_exists: MagicMock,
        mock_parse: MagicMock,
        mock_download: MagicMock,
        verification_manager: VerificationManager,
    ) -> None:
        """Test successful verification."""
        mock_exists.return_value = True
        mock_parse.return_value = True

        result = verification_manager.verify_appimage()

        mock_download.assert_called_once()
        mock_parse.assert_called_once()
        assert result is True

    @patch("src.verify.VerificationManager._download_sha_file")
    @patch("src.verify.VerificationManager._parse_sha_file")
    @patch("src.verify.VerificationManager._cleanup_failed_file")
    @patch("os.path.exists")
    def test_verify_appimage_failure_with_cleanup(
        self,
        mock_exists: MagicMock,
        mock_cleanup: MagicMock,
        mock_parse: MagicMock,
        mock_download: MagicMock,
        verification_manager: VerificationManager,
    ) -> None:
        """Test failed verification with cleanup."""
        mock_exists.return_value = True
        mock_parse.return_value = False

        result = verification_manager.verify_appimage(cleanup_on_failure=True)

        mock_download.assert_called_once()
        mock_parse.assert_called_once()
        mock_cleanup.assert_called_once_with(verification_manager.appimage_name)
        assert result is False

    def test_parse_text_sha_standard_format(
        self, verification_manager: VerificationManager
    ) -> None:
        """Test parsing SHA file with standard HASH FILENAME format."""
        # Create a mock SHA file with standard format: HASH FILENAME
        sha_content = (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 test.AppImage"
        )

        # Mock the file open and read operations
        with patch("builtins.open", mock_open(read_data=sha_content)):
            with patch.object(
                verification_manager, "_compare_hashes", return_value=True
            ) as mock_compare:
                result = verification_manager._parse_text_sha()

                # Verify the hash value was extracted and compared correctly
                mock_compare.assert_called_once_with(
                    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                )
                assert result is True

    def test_parse_text_sha_alternate_format(
        self, verification_manager: VerificationManager
    ) -> None:
        """Test parsing SHA file with alternate FILENAME HASH format."""
        # Create a mock SHA file with alternate format: FILENAME HASH
        sha_content = (
            "test.AppImage e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

        # Mock the file open and read operations
        with patch("builtins.open", mock_open(read_data=sha_content)):
            with patch.object(
                verification_manager, "_compare_hashes", return_value=True
            ) as mock_compare:
                result = verification_manager._parse_text_sha()

                # Verify the hash value was extracted and compared correctly
                mock_compare.assert_called_once_with(
                    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                )
                assert result is True

    def test_parse_text_sha_case_insensitive(
        self, verification_manager: VerificationManager
    ) -> None:
        """Test parsing SHA file with case-insensitive matching."""
        # Use mixed case in filename and uppercase hash
        verification_manager.appimage_name = "Test.AppImage"
        sha_content = (
            "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855 test.appimage"
        )

        # Mock the file open and read operations
        with patch("builtins.open", mock_open(read_data=sha_content)):
            with patch.object(
                verification_manager, "_compare_hashes", return_value=True
            ) as mock_compare:
                result = verification_manager._parse_text_sha()

                # Verify the hash value was extracted (lowercase) and compared correctly
                mock_compare.assert_called_once_with(
                    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                )
                assert result is True

    def test_parse_text_sha_invalid_hash_length(
        self, verification_manager: VerificationManager
    ) -> None:
        """Test parsing SHA file with invalid hash length."""
        # Create a mock SHA file with invalid hash length
        sha_content = "e3b0c44298fc1c149afbf4c8996fb924 test.AppImage"  # Too short

        # Mock the file open and read operations
        with patch("builtins.open", mock_open(read_data=sha_content)):
            with patch("logging.warning") as mock_warning:
                with pytest.raises(ValueError, match="No valid hash found"):
                    verification_manager._parse_text_sha()

                # Verify the warning was logged about invalid hash length
                mock_warning.assert_called_once()
                assert "wrong length" in mock_warning.call_args[0][0]

    def test_parse_text_sha_invalid_hash_chars(
        self, verification_manager: VerificationManager
    ) -> None:
        """Test parsing SHA file with invalid hash characters."""
        # Create a mock SHA file with invalid hash characters
        sha_content = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85Z test.AppImage"  # Contains Z

        # Mock the file open and read operations
        with patch("builtins.open", mock_open(read_data=sha_content)):
            with patch("logging.warning") as mock_warning:
                with pytest.raises(ValueError, match="No valid hash found"):
                    verification_manager._parse_text_sha()

                # Verify the warning was logged about invalid hash characters
                mock_warning.assert_called_once()
                assert "Invalid hex characters" in mock_warning.call_args[0][0]

    def test_compare_hashes(self, verification_manager: VerificationManager) -> None:
        """Test the hash comparison function."""
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test data")
            temp_path = temp_file.name

        try:
            verification_manager.appimage_name = temp_path

            # Calculate the actual hash of the test file
            hasher = hashlib.sha256()
            with open(temp_path, "rb") as f:
                hasher.update(f.read())
            actual_hash = hasher.hexdigest()

            # Test with matching hash
            with patch.object(verification_manager, "_log_comparison") as mock_log, patch.object(
                verification_manager, "_cleanup_verification_file"
            ) as mock_cleanup:
                result = verification_manager._compare_hashes(actual_hash)
                mock_log.assert_called_once()
                mock_cleanup.assert_called_once()
                assert result is True

            # Test with non-matching hash
            with patch.object(verification_manager, "_log_comparison") as mock_log, patch.object(
                verification_manager, "_cleanup_verification_file"
            ) as mock_cleanup:
                result = verification_manager._compare_hashes("e" * 64)  # Different hash
                mock_log.assert_called_once()
                mock_cleanup.assert_called_once()
                assert result is False

            # Test with uppercase hash (should still match)
            with patch.object(verification_manager, "_log_comparison") as mock_log, patch.object(
                verification_manager, "_cleanup_verification_file"
            ) as mock_cleanup:
                result = verification_manager._compare_hashes(actual_hash.upper())
                mock_log.assert_called_once()
                mock_cleanup.assert_called_once()
                assert result is True

        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
