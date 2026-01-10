from my_unicorn.domain.verification.verifier import format_bytes
from my_unicorn.infrastructure.desktop_entry import (
    create_desktop_entry_name,
    sanitize_filename,
)


def test_sanitize_filename_removes_invalid_chars():
    """Test sanitize_filename removes invalid filesystem characters."""
    original = "inva<l>id:/\\|?*file.txt"
    sanitized = sanitize_filename(original)
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
    sanitized = sanitize_filename(original)
    assert "\x00" not in sanitized
    assert "\x1f" not in sanitized
    assert sanitized.endswith(".txt")


def test_sanitize_filename_truncates_long_names():
    """Test sanitize_filename truncates names longer than 255 chars."""
    name = "a" * 300 + ".txt"
    sanitized = sanitize_filename(name)
    assert len(sanitized) <= 255
    assert sanitized.endswith(".txt")


def test_sanitize_filename_strips_whitespace():
    """Test sanitize_filename strips leading/trailing whitespace."""
    original = "   file.txt   "
    sanitized = sanitize_filename(original)
    assert sanitized == "file.txt"


def test_format_bytes_with_floats():
    """Test format_bytes handles float values and produces correct output."""
    assert format_bytes(1536.0) == "1.5 KB"
    assert format_bytes(1572864.0) == "1.5 MB"
    assert format_bytes(1610612736.0) == "1.5 GB"
    assert format_bytes(1127428915.2) == "1.1 GB"
    assert format_bytes(1509949439.0) == "1.4 GB"
    assert format_bytes(1.5 * 1024**4) == "1.5 TB"
    assert format_bytes(1.5 * 1024**5) == "1.5 PB"


def test_create_desktop_entry_name_normalizes():
    """Test create_desktop_entry_name normalizes app name."""
    assert create_desktop_entry_name("QOwnNotes") == "qownnotes.desktop"
    assert create_desktop_entry_name("Siyuan!") == "siyuan.desktop"
    assert create_desktop_entry_name("") == "appimage.desktop"
    assert (
        create_desktop_entry_name("Standard Notes") == "standardnotes.desktop"
    )
    assert (
        create_desktop_entry_name("Standard-Notes") == "standard-notes.desktop"
    )
    assert create_desktop_entry_name("FreeTube") == "freetube.desktop"
