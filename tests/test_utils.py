import platform
from pathlib import Path

import pytest

from my_unicorn import utils


def test_sanitize_filename_removes_invalid_chars():
    """Test sanitize_filename removes invalid filesystem characters."""
    original = "inva<l>id:/\\|?*file.txt"
    sanitized = utils.sanitize_filename(original)
    assert "<" not in sanitized
    assert ">" not in sanitized
    assert ":" not in sanitized
    assert "/" not in sanitized
    assert "\\" not in sanitized
    assert "|" not in sanitized
    assert "?" not in sanitized
    assert "*" not in sanitized
    assert sanitized.endswith("file.txt")
    assert len(sanitized) <= 255


def test_sanitize_filename_removes_control_chars():
    """Test sanitize_filename removes control characters."""
    original = "abc\x00def\x1fghi.txt"
    sanitized = utils.sanitize_filename(original)
    assert "\x00" not in sanitized
    assert "\x1f" not in sanitized
    assert sanitized.endswith(".txt")


def test_sanitize_filename_truncates_long_names():
    """Test sanitize_filename truncates names longer than 255 chars."""
    name = "a" * 300 + ".txt"
    sanitized = utils.sanitize_filename(name)
    assert len(sanitized) <= 255
    assert sanitized.endswith(".txt")


def test_sanitize_filename_strips_whitespace():
    """Test sanitize_filename strips leading/trailing whitespace."""
    original = "   file.txt   "
    sanitized = utils.sanitize_filename(original)
    assert sanitized == "file.txt"


def test_get_system_architecture_normalizes():
    """Test get_system_architecture normalizes known values."""
    orig_machine = platform.machine
    platform.machine = lambda: "x64"
    assert utils.get_system_architecture() == "x86_64"
    platform.machine = lambda: "amd64"
    assert utils.get_system_architecture() == "x86_64"
    platform.machine = lambda: "arm64"
    assert utils.get_system_architecture() == "aarch64"
    platform.machine = lambda: "armv7l"
    assert utils.get_system_architecture() == "armhf"
    platform.machine = orig_machine


def test_format_bytes_human_readable():
    """Test format_bytes returns human readable sizes."""
    assert utils.format_bytes(512) == "512.0 B"
    assert utils.format_bytes(2048) == "2.0 KB"
    assert utils.format_bytes(1048576) == "1.0 MB"
    assert utils.format_bytes(1073741824) == "1.0 GB"


def test_is_valid_github_repo_owner_repo():
    """Test is_valid_github_repo validates owner/repo format."""
    assert utils.is_valid_github_repo("foo/bar")
    assert not utils.is_valid_github_repo("foo//bar")
    assert not utils.is_valid_github_repo("foo@/bar")
    assert not utils.is_valid_github_repo("foo")
    assert not utils.is_valid_github_repo("http://notgithub.com/foo/bar")


def test_is_valid_github_repo_url():
    """Test is_valid_github_repo validates GitHub URLs."""
    assert utils.is_valid_github_repo("https://github.com/foo/bar")
    assert utils.is_valid_github_repo("http://github.com/foo/bar")
    assert not utils.is_valid_github_repo("https://gitlab.com/foo/bar")


def test_expand_template_success():
    """Test expand_template substitutes variables."""
    template = "Hello {name}, version {version}"
    variables = {"name": "Alice", "version": "1.2.3"}
    assert utils.expand_template(template, variables) == "Hello Alice, version 1.2.3"


def test_expand_template_missing_key():
    """Test expand_template returns template if missing key."""
    template = "Hello {name}, version {version}"
    variables = {"name": "Alice"}
    assert utils.expand_template(template, variables) == template


def test_validate_version_string_semver():
    """Test validate_version_string accepts semantic versions."""
    assert utils.validate_version_string("1.2.3")
    assert utils.validate_version_string("v1.2.3")
    assert utils.validate_version_string("1.2.3-alpha")
    assert utils.validate_version_string("1.2.3-beta.1")
    assert not utils.validate_version_string("notaversion")
    assert not utils.validate_version_string("")


def test_create_desktop_entry_name_normalizes():
    """Test create_desktop_entry_name normalizes app name."""
    assert utils.create_desktop_entry_name("Foo App") == "fooapp.desktop"
    assert utils.create_desktop_entry_name("QOwnNotes") == "qownnotes.desktop"
    assert utils.create_desktop_entry_name("Siyuan!") == "siyuan.desktop"
    assert utils.create_desktop_entry_name("") == "appimage.desktop"


def test_extract_version_from_filename_patterns():
    """Test extract_version_from_filename extracts version."""
    assert utils.extract_version_from_filename("foo-v1.2.3.AppImage") == "1.2.3"
    assert utils.extract_version_from_filename("bar-2.0.1-beta.AppImage") == "2.0.1-beta"
    assert utils.extract_version_from_filename("baz-3.4.AppImage") == "3.4"
    assert utils.extract_version_from_filename("no-version.AppImage") is None


def test_safe_path_join_success(tmp_path: Path):
    """Test safe_path_join joins paths safely."""
    base = tmp_path
    result = utils.safe_path_join(base, "foo", "bar.txt")
    assert str(result).endswith("foo/bar.txt")
    # Should not raise
    result.resolve().relative_to(base.resolve())


def test_safe_path_join_raises_on_traversal(tmp_path: Path):
    """Test safe_path_join raises on directory traversal."""
    base = tmp_path
    with pytest.raises(ValueError):
        utils.safe_path_join(base, "..", "evil.txt")
    with pytest.raises(ValueError):
        utils.safe_path_join(base, "/abs/path.txt")


def test_parse_content_disposition_filename():
    """Test parse_content_disposition extracts filename."""
    header = 'attachment; filename="foo.txt"'
    assert utils.parse_content_disposition(header) == "foo.txt"
    header = "attachment; filename*=UTF-8''bar.txt"
    assert utils.parse_content_disposition(header) == "bar.txt"
    header = ""
    assert utils.parse_content_disposition(header) is None


def test_is_safe_filename_valid_invalid():
    """Test is_safe_filename checks for safe filenames."""
    assert utils.is_safe_filename("foo.txt")
    assert not utils.is_safe_filename("foo/bar.txt")
    assert not utils.is_safe_filename("")
    assert not utils.is_safe_filename("..")
    assert not utils.is_safe_filename("bad\x00name.txt")


def test_check_icon_exists(tmp_path: Path):
    """Test check_icon_exists returns True if icon exists."""
    icon_dir = tmp_path
    icon_name = "icon.png"
    icon_path = icon_dir / icon_name
    icon_path.write_bytes(b"icon")
    assert utils.check_icon_exists(icon_name, icon_dir)
    assert not utils.check_icon_exists("missing.png", icon_dir)


def test_get_icon_path(tmp_path: Path):
    """Test get_icon_path returns correct path."""
    icon_dir = tmp_path
    icon_name = "icon.png"
    result = utils.get_icon_path(icon_name, icon_dir)
    assert result == icon_dir / icon_name
