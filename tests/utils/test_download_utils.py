"""Tests for download utilities."""

from my_unicorn.utils.download_utils import extract_filename_from_url


def test_extract_filename_from_url_simple():
    """Test extracting filename from simple URL."""
    url = "https://example.com/app.AppImage"
    assert extract_filename_from_url(url) == "app.AppImage"


def test_extract_filename_from_url_with_path():
    """Test extracting filename from URL with path."""
    url = "https://example.com/path/to/file.tar.gz"
    assert extract_filename_from_url(url) == "file.tar.gz"


def test_extract_filename_from_url_with_query():
    """Test extracting filename from URL with query parameters."""
    url = "https://example.com/app.AppImage?version=1.0&build=123"
    assert extract_filename_from_url(url) == "app.AppImage"


def test_extract_filename_from_url_with_fragment():
    """Test extracting filename from URL with fragment."""
    url = "https://example.com/download/app.AppImage#section"
    assert extract_filename_from_url(url) == "app.AppImage"


def test_extract_filename_from_url_github_release():
    """Test extracting filename from real GitHub release URL."""
    url = "https://github.com/owner/repo/releases/download/v1.0.0/MyApp-x86_64.AppImage"
    assert extract_filename_from_url(url) == "MyApp-x86_64.AppImage"


def test_extract_filename_from_url_complex():
    """Test extracting filename with complex URL."""
    url = "https://api.github.com/repos/owner/repo/releases/assets/12345?name=app.AppImage"
    # Query parameter is ignored, only path component matters
    assert extract_filename_from_url(url) == "12345"
