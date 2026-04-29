"""Tests for github_ops utility module."""

import pytest

from my_unicorn.core.github import extract_github_config
from my_unicorn.exceptions import InstallationError
from my_unicorn.utils.github_utils import parse_github_url


class TestParseGitHubUrl:
    """Tests for parse_github_url function."""

    def test_parse_github_url_valid(self):
        """Test parse_github_url with valid URL."""

        result = parse_github_url("https://github.com/AppFlowy-IO/AppFlowy")

        assert result["owner"] == "AppFlowy-IO"
        assert result["repo"] == "AppFlowy"
        assert result["app_name"] == "appflowy"

    def test_parse_github_url_with_trailing_slash(self):
        """Test parse_github_url with trailing slash."""

        result = parse_github_url("https://github.com/owner/repo/")

        assert result["owner"] == "owner"
        assert result["repo"] == "repo"
        assert result["app_name"] == "repo"

    def test_parse_github_url_with_extra_path(self):
        """Test parse_github_url with extra path components."""

        result = parse_github_url("https://github.com/owner/repo/releases")

        assert result["owner"] == "owner"
        assert result["repo"] == "repo"
        assert result["app_name"] == "repo"

    def test_parse_github_url_invalid_format(self):
        """Test parse_github_url with invalid format."""

        with pytest.raises(
            InstallationError, match="Invalid GitHub URL format"
        ):
            parse_github_url("https://github.com/owner")

    def test_parse_github_url_empty(self):
        """Test parse_github_url with empty URL."""

        with pytest.raises(InstallationError):
            parse_github_url("")

    def test_parse_github_url_malformed(self):
        """Test parse_github_url with malformed URL."""

        with pytest.raises(InstallationError):
            parse_github_url("not-a-valid-url")


class TestExtractGitHubConfig:
    """Tests for extract_github_config function."""

    def test_extract_github_config_from_source(self):
        """Test extract_github_config from source."""

        effective_config = {
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            }
        }

        owner, repo, prerelease = extract_github_config(effective_config)

        assert owner == "test-owner"
        assert repo == "test-repo"
        assert prerelease is False

    def test_extract_github_config_missing_source(self):
        """Test extract_github_config with missing source."""

        effective_config = {}

        owner, repo, prerelease = extract_github_config(effective_config)

        assert owner == "unknown"
        assert repo == "unknown"
        assert prerelease is False

    def test_extract_github_config_default_prerelease(self):
        """Test extract_github_config with default prerelease value."""

        effective_config = {
            "source": {"owner": "test-owner", "repo": "test-repo"}
        }

        owner, repo, prerelease = extract_github_config(effective_config)

        assert owner == "test-owner"
        assert repo == "test-repo"
        assert prerelease is False  # Default value

    def test_extract_github_config_with_prerelease_true(self):
        """Test extract_github_config with prerelease set to True."""

        effective_config = {
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": True,
            }
        }

        owner, repo, prerelease = extract_github_config(effective_config)

        assert prerelease is True
