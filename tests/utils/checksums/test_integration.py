#!/usr/bin/env python3
"""Integration tests for the checksums package."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.utils.checksums import (
    ReleaseChecksumExtractor,
    extract_checksums_to_file,
    get_checksums_from_release,
    handle_release_description_verification,
)


class TestChecksumIntegration:
    """Integration tests for the checksums package."""

    SAMPLE_RELEASE_DESC = """# Zen Browser Release

<details>
<summary>File Checksums (SHA-256)</summary>

```
abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage
bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  zen-aarch64.AppImage
```
</details>
"""

    @pytest.fixture
    def mock_github_api(self):
        """Mock GitHub API responses."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"body": self.SAMPLE_RELEASE_DESC}
            mock_get.return_value = mock_response
            yield mock_get

    @pytest.fixture
    def mock_auth_headers(self):
        """Mock auth headers for GitHub API."""
        with patch("src.auth_manager.GitHubAuthManager.get_auth_headers") as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer mock_token"}
            yield mock_headers

    @pytest.fixture
    def test_appimage(self):
        """Create a test AppImage file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "zen-x86_64.AppImage")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("Test AppImage content")
            yield file_path, temp_dir

    def test_extract_checksums_to_file_integration(self, mock_github_api, mock_auth_headers):
        """Test extract_checksums_to_file function integration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "SHA256SUMS.txt")
            
            # Call the function under test
            result_path = extract_checksums_to_file(
                owner="zen-browser",
                repo="desktop",
                appimage_name="zen-x86_64.AppImage",
                output_path=output_path
            )
            
            # Verify results
            assert result_path == output_path
            assert os.path.exists(output_path)
            
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "zen-x86_64.AppImage" in content
                assert "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890" in content

    def test_get_checksums_from_release_integration(self, mock_github_api, mock_auth_headers):
        """Test get_checksums_from_release function integration."""
        # Call the function under test
        checksums = get_checksums_from_release(
            owner="zen-browser",
            repo="desktop",
            appimage_name="zen-x86_64.AppImage"
        )
        
        # Verify results
        assert len(checksums) == 1
        assert "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  zen-x86_64.AppImage" in checksums

    @patch("src.utils.checksums.verification.calculate_file_checksum")
    def test_handle_release_description_verification_integration(
        self, mock_calc, mock_github_api, mock_auth_headers, test_appimage
    ):
        """Test the complete verification flow with release description."""
        file_path, _ = test_appimage
        
        # Mock checksum calculation to match our expected value
        mock_calc.return_value = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        
        # Call the function under test
        result = handle_release_description_verification(
            appimage_path=file_path,
            owner="zen-browser",
            repo="desktop"
        )
        
        # Verify results
        assert result is True
        mock_calc.assert_called_once()
        mock_github_api.assert_called_once()

    @patch("src.utils.checksums.verification.calculate_file_checksum")
    def test_handle_release_description_verification_failure_integration(
        self, mock_calc, mock_github_api, mock_auth_headers, test_appimage
    ):
        """Test the complete verification flow with release description (failure case)."""
        file_path, _ = test_appimage
        
        # Mock checksum calculation to NOT match our expected value
        mock_calc.return_value = "different_checksum_value"
        
        # Call the function under test
        result = handle_release_description_verification(
            appimage_path=file_path,
            owner="zen-browser",
            repo="desktop"
        )
        
        # Verify results
        assert result is False
        mock_calc.assert_called_once()
        mock_github_api.assert_called_once()

    @patch("requests.get")
    def test_network_failure_handling_integration(self, mock_get, mock_auth_headers, test_appimage):
        """Test proper handling of network failures in the verification flow."""
        file_path, _ = test_appimage
        
        # Mock a network failure
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        # Call the function and verify it raises the expected exception
        with pytest.raises(requests.exceptions.ConnectionError):
            handle_release_description_verification(
                appimage_path=file_path,
                owner="zen-browser",
                repo="desktop"
            )

    def test_backward_compatibility_functions(self):
        """Test that old function names still work for backward compatibility."""
        # The extract_checksums_for_appimage function should still be available
        assert callable(extract_checksums_to_file)
        
        with patch.object(ReleaseChecksumExtractor, 'fetch_release_description') as mock_fetch:
            with patch.object(ReleaseChecksumExtractor, 'write_checksums_file') as mock_write:
                mock_write.return_value = "/tmp/checksums.txt"
                
                # Should work without errors
                extract_checksums_to_file("owner", "repo", "file.AppImage")
                
                mock_fetch.assert_called_once()
                mock_write.assert_called_once()