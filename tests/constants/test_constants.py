"""Tests for constants module."""

from pathlib import Path

from my_unicorn.constants import LOCKFILE_PATH


class TestLockfilePathConstant:
    """Tests for LOCKFILE_PATH constant."""

    def test_lockfile_path_constant_exists(self) -> None:
        """Test that LOCKFILE_PATH constant is defined."""
        assert LOCKFILE_PATH is not None

    def test_lockfile_path_has_correct_value(self) -> None:
        """Test that LOCKFILE_PATH points to /tmp/my-unicorn.lock."""
        assert str(LOCKFILE_PATH) == "/tmp/my-unicorn.lock"

    def test_lockfile_path_is_path_object(self) -> None:
        """Test that LOCKFILE_PATH is a Path object."""
        assert isinstance(LOCKFILE_PATH, Path)
