#!/usr/bin/env python3
"""Tests for the GitHub release description parser module."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.utils.checksums import (
    ReleaseChecksumExtractor,
    extract_checksums_to_file,
)

# For backwards compatibility during migration
extract_checksums_for_appimage = extract_checksums_to_file

# Import this from checksums package if it exists, otherwise mock it
try:
    from my_unicorn.utils.checksums import get_checksums_from_release
except ImportError:
    # Mock function if it's not in the new structure
    def get_checksums_from_release(owner, repo, appimage_name):
        extractor = ReleaseChecksumExtractor(owner, repo)
        extractor.fetch_release_description()
        return extractor.extract_checksums(appimage_name)


class TestGitHubReleaseParser:
    """Test suite for the GitHub release description parser."""

    SAMPLE_RELEASE_DESC = """# Zen Stable Release
This is just a small update to fix some bugs with the previous version. Please checkout release notes for 1.12b for more details.

## Fixes
- Fixed sidbar in collapsed, compact mode being too small.
- Fixed jitter on compact mode on windows.
- Fixed duplicate newtabs opening when having 'replace-newtab' disabled.
- Fixed custom colors not being able to be removed.

<details>
<summary>File Checksums (SHA-256)</summary>

```
cba77042118d5f55698867e66b592f4dff7ccf8f905e7fb14cdca96dc7ec6c91  zen.source.tar.zst
95d8a2c6cf038b587e7859cc3f3b0f3d0bfb29fdb0210d997a96a590e7a7fdbc  zen.linux-x86_64.tar.xz
b367ca645f35d7640e1497058a6f03aba4609382f6cd80baa005f785eef23273  zen.linux-aarch64.tar.xz
078f4788fd5064c3274ddcfbc53f813a3987d05ad95c965bbc16ab8d821b7382  zen-x86_64.AppImage
8c49aad55d324cd2862bd320729c5035bb5445744daeed319c26ec7dfa08c8fa  zen-x86_64.AppImage.zsync
eecda482661e157d5cb1326c2b2222619a3b101062acaea71772f6d036c22aed  zen-aarch64.AppImage
48fa78d5e399581597b09d9bb63c1d2ed8a15d4f67120e6e54160bf95d3f950f  zen-aarch64.AppImage.zsync
33df8dc55257177fca6709702315587276792b5836dbc7e95c8b26f09ff78715  linux.mar
4f00dfbea42aa1410ac35c7d0e186b2e1e08f2cf9455687dc18b6510b4f251c8  linux-aarch64.mar
1f1e94d45f4c117a04d0936d48786c839ce01108032cde54950c444a70ce9a5c  windows.mar
a202066a1a6ec8bd5cb6dbd43a5de3ce87d0a13d83ef748e87c1d3fec80d22e0  windows-arm64.mar
9a03e910bca3a548da30d9df1e135b7c444673ce41d6a06d0902eea4b8235e30  macos.mar
72cb73b05b9bfcda3cb02d86a56a8f5a5b46879f1a7203b387ead00151cd2fae  zen.installer.exe
678f464161bb39c51804a5a36d70b88775141688e5c4df76dc1f605fc076cc60  zen.installer-arm64.exe
71fe9dffff6d8d8bd45591ed02cbe92791f4fbc3f0ffdf5d615880847f2a2193  zen.macos-universal.dmg
```
</details>
"""

    @pytest.fixture
    def parser(self):
        """Create a parser with mocked authentication."""
        with patch("my_unicorn.auth_manager.GitHubAuthManager.get_auth_headers") as mock_headers:
            mock_headers.return_value = {"Authorization": "Bearer mock_token"}
            parser = ReleaseChecksumExtractor("zen-browser", "desktop")
            parser.release_description = self.SAMPLE_RELEASE_DESC
            yield parser

    def test_parse_checksums_from_description(self, parser):
        """Test parsing checksums from a GitHub release description."""
        checksums = parser._parse_checksums_from_description()
        assert len(checksums) == 15  # Total number of checksums in sample
        assert (
            "078f4788fd5064c3274ddcfbc53f813a3987d05ad95c965bbc16ab8d821b7382  zen-x86_64.AppImage"
            in checksums
        )
        assert (
            "eecda482661e157d5cb1326c2b2222619a3b101062acaea71772f6d036c22aed  zen-aarch64.AppImage"
            in checksums
        )

    def test_extract_checksums_with_target_file(self, parser):
        """Test extracting checksums for a specific target file."""
        checksums = parser.extract_checksums("zen-x86_64.AppImage")
        assert len(checksums) == 1
        assert (
            checksums[0]
            == "078f4788fd5064c3274ddcfbc53f813a3987d05ad95c965bbc16ab8d821b7382  zen-x86_64.AppImage"
        )

    def test_extract_checksums_no_match(self, parser):
        """Test extracting checksums for a file that doesn't match."""
        checksums = parser.extract_checksums("nonexistent.AppImage")
        assert len(checksums) > 0  # Should return all checksums if no match

    def test_write_checksums_file(self, parser):
        """Test writing checksums to a file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "SHA256SUMS.txt")
            result_path = parser.write_checksums_file("zen-x86_64.AppImage", output_path)

            assert result_path == output_path
            assert os.path.exists(output_path)

            # Check file content
            with open(output_path, encoding="utf-8") as f:
                content = f.read().strip()
                assert (
                    "078f4788fd5064c3274ddcfbc53f813a3987d05ad95c965bbc16ab8d821b7382  zen-x86_64.AppImage"
                    in content
                )

    @patch("my_unicorn.utils.checksums.ReleaseChecksumExtractor.fetch_release_description")
    def test_extract_checksums_for_appimage(self, mock_fetch, parser):
        """Test the extract_checksums_for_appimage helper function."""
        # Mock the fetch_release_description method to return True
        mock_fetch.return_value = self.SAMPLE_RELEASE_DESC

        with patch("my_unicorn.utils.checksums.ReleaseChecksumExtractor") as MockParser:
            # set up the mock parser instance
            mock_parser_instance = MagicMock()
            mock_parser_instance.write_checksums_file.return_value = "/tmp/SHA256SUMS.txt"
            MockParser.return_value = mock_parser_instance

            # Call the function under test
            result = extract_checksums_for_appimage("zen-browser", "desktop", "zen-x86_64.AppImage")

            # Verify results
            assert result == "/tmp/SHA256SUMS.txt"
            mock_parser_instance.fetch_release_description.assert_called_once()
            mock_parser_instance.write_checksums_file.assert_called_once_with(
                "zen-x86_64.AppImage", None
            )

    @patch("my_unicorn.utils.checksums.ReleaseChecksumExtractor.extract_checksums")
    @patch("my_unicorn.utils.checksums.ReleaseChecksumExtractor.fetch_release_description")
    def test_get_checksums_from_release(self, mock_fetch, mock_extract, parser):
        """Test the get_checksums_from_release function."""
        # Mock the needed methods
        mock_fetch.return_value = self.SAMPLE_RELEASE_DESC
        mock_extract.return_value = [
            "078f4788fd5064c3274ddcfbc53f813a3987d05ad95c965bbc16ab8d821b7382  zen-x86_64.AppImage"
        ]

        # Call the function under test
        with patch("my_unicorn.utils.checksums.ReleaseChecksumExtractor") as MockParser:
            mock_parser_instance = MagicMock()
            MockParser.return_value = mock_parser_instance
            mock_parser_instance.extract_checksums.return_value = mock_extract.return_value
            mock_parser_instance.fetch_release_description.return_value = True

            result = get_checksums_from_release("zen-browser", "desktop", "zen-x86_64.AppImage")

            # Verify results
            assert len(result) == 1
            assert (
                result[0]
                == "078f4788fd5064c3274ddcfbc53f813a3987d05ad95c965bbc16ab8d821b7382  zen-x86_64.AppImage"
            )
            mock_parser_instance.fetch_release_description.assert_called_once()
            mock_parser_instance.extract_checksums.assert_called_once_with("zen-x86_64.AppImage")


if __name__ == "__main__":
    # Run the tests
    pytest.main(["-xvs", __file__])
