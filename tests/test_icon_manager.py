#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the IconManager class.

This script tests the functionality of the IconManager to efficiently find and
download icons from GitHub repositories while avoiding API rate limits.
"""

import logging
import os
import sys
import tempfile
import time
import unittest
from typing import Dict, List
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the IconManager class
from src.icon_manager import IconManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class TestIconManager(unittest.TestCase):
    """
    Test cases for the IconManager class.

    Tests the icon finding and downloading capabilities while ensuring
    the class handles API limits gracefully.
    """

    def setUp(self):
        """Set up test environment before each test."""
        # Create a test directory for downloads instead of using real XDG locations
        self.test_dir = tempfile.mkdtemp()
        self.icon_manager = IconManager(api_call_delay=0.1)  # Short delay for faster tests

        # Known repositories that should have icons
        self.known_repos = [
            {"owner": "johannesjo", "repo": "super-productivity"},
            {"owner": "laurent22", "repo": "joplin"},
        ]

        # Previously problematic repositories
        self.potentially_problematic_repos = [{"owner": "siyuan-note", "repo": "siyuan"}]

        # Nonexistent repositories
        self.nonexistent_repos = [{"owner": "nonexistent-user", "repo": "nonexistent-repo"}]

    def tearDown(self):
        """Clean up test environment after each test."""
        # Clean up the temporary directory
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_find_icon_known_repositories(self):
        """Test finding icons in known repositories."""
        print("\n=== Testing Known Repositories ===")

        for repo_info in self.known_repos:
            owner = repo_info["owner"]
            repo = repo_info["repo"]
            print(f"\nFinding icon for {owner}/{repo}")

            # Find an icon
            start_time = time.time()
            icon_info = self.icon_manager.find_icon(owner, repo, api_limit=1)
            elapsed = time.time() - start_time

            if icon_info:
                print(f"✅ Found icon in {elapsed:.2f}s: {icon_info['name']}")
                self.assertIn("download_url", icon_info)
                self.assertIn("name", icon_info)
            else:
                print(f"❌ No icon found (took {elapsed:.2f}s)")

    def test_problematic_repositories(self):
        """Test repositories that have caused problems."""
        print("\n=== Testing Potentially Problematic Repositories ===")

        for repo_info in self.potentially_problematic_repos:
            owner = repo_info["owner"]
            repo = repo_info["repo"]
            print(f"\nFinding icon for {owner}/{repo}")

            # Set API limit to 1 to ensure quick completion
            icon_info = self.icon_manager.find_icon(owner, repo, api_limit=1)

            # We don't assert success here, just test that it completes without hanging
            print(
                f"{'✅ Found icon' if icon_info else '⚠️ No icon found, but test completed without hanging'}"
            )

    def test_nonexistent_repositories(self):
        """Test behavior with nonexistent repositories."""
        print("\n=== Testing Nonexistent Repositories ===")

        for repo_info in self.nonexistent_repos:
            owner = repo_info["owner"]
            repo = repo_info["repo"]
            print(f"\nFinding icon for {owner}/{repo}")

            # Use low API limit and expect None result
            icon_info = self.icon_manager.find_icon(owner, repo, api_limit=1)

            self.assertIsNone(icon_info)
            print("✅ Correctly returned None for nonexistent repository")

    def test_download_icon_to_temp_directory(self):
        """Test downloading icon to a temporary directory."""
        print("\n=== Testing Icon Download to Temp Directory ===")

        # Use a repository known to have an icon
        owner = self.known_repos[0]["owner"]
        repo = self.known_repos[0]["repo"]
        print(f"\nFinding and downloading icon for {owner}/{repo}")

        # Find an icon
        icon_info = self.icon_manager.find_icon(owner, repo, api_limit=1)

        if icon_info:
            # Create a custom download directory
            download_dir = os.path.join(self.test_dir, repo.lower())
            os.makedirs(download_dir, exist_ok=True)

            # Download the icon
            success, result = self.icon_manager.download_icon(icon_info, repo, create_dir=False)

            # Download should fail because create_dir is False and the default path doesn't exist
            self.assertFalse(success)
            print("✅ Download correctly failed with create_dir=False on non-existent path")

            # Now try with a specific path and create_dir=True
            temp_icon_path = os.path.join(self.test_dir, icon_info["name"])

            # Mock the icon directory to use our test directory
            with patch("os.path.expanduser", return_value=self.test_dir):
                success, path = self.icon_manager.download_icon(icon_info, repo)

                # Verify the download succeeded
                self.assertTrue(success)
                self.assertTrue(os.path.exists(path))
                print(f"✅ Icon downloaded successfully to test directory: {path}")

    def test_api_call_limiting(self):
        """Test that the API call limiting logic works."""
        print("\n=== Testing API Call Limiting ===")

        # Set up a mock
        with patch.object(self.icon_manager, "_find_icon_via_api") as mock_api_call:
            # Configure the mock to return None
            mock_api_call.return_value = None

            # Test with an unknown repository
            owner = "some-owner"
            repo = "some-repo"

            # First call should make API calls up to the limit
            self.icon_manager.find_icon(owner, repo, api_limit=2)
            self.assertEqual(mock_api_call.call_count, 1)

            # Reset call counter
            mock_api_call.reset_mock()

            # Call again with API limit of 0 - should not make API calls
            self.icon_manager.find_icon(owner, repo, api_limit=0)
            self.assertEqual(mock_api_call.call_count, 0)

            print("✅ API call limiting works correctly")

    def test_known_paths_preferred(self):
        """Test that known paths are preferred over API calls."""
        print("\n=== Testing Known Paths Priority ===")

        # Add a test path to the known paths
        test_repo = "test-repo"
        test_path = "test/path/icon.png"
        self.icon_manager.KNOWN_ICON_PATHS[test_repo] = [test_path]

        # Mock _check_icon_at_path to return a fake icon for our known path
        original_check_path = self.icon_manager._check_icon_at_path

        def mock_check_path(owner, repo, path):
            if path == test_path:
                return {
                    "name": "icon.png",
                    "path": test_path,
                    "download_url": "https://example.com/icon.png",
                    "branch": "main",
                }
            return original_check_path(owner, repo, path)

        with patch.object(self.icon_manager, "_check_icon_at_path", side_effect=mock_check_path):
            # Mock _find_icon_via_api to track if it gets called
            with patch.object(self.icon_manager, "_find_icon_via_api") as mock_api_call:
                # Find icon for our test repo
                icon_info = self.icon_manager.find_icon("test-owner", test_repo)

                # Verify we got the icon from our known path
                self.assertIsNotNone(icon_info)
                self.assertEqual(icon_info["path"], test_path)

                # Verify the API method was not called
                self.assertEqual(mock_api_call.call_count, 0)

                print("✅ Known paths are correctly prioritized over API calls")


def main():
    """Run the IconManager tests."""
    print("===== Running IconManager Tests =====\n")
    unittest.main(argv=["first-arg-is-ignored"], exit=False)


if __name__ == "__main__":
    main()
