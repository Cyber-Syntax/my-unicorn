from pathlib import Path
from unittest.mock import patch

import pytest

from my_unicorn.infrastructure.file_ops import FileOperations


@pytest.fixture
def install_dir(tmp_path: Path) -> Path:
    """Provide a temporary install directory."""
    d = tmp_path / "install"
    d.mkdir()
    return d


@pytest.fixture
def patch_logger():
    """Patch get_logger to avoid real logging output."""
    with patch("my_unicorn.infrastructure.file_ops.get_logger") as mock_logger:
        yield mock_logger


def test_move_file_success(tmp_path: Path, install_dir: Path, patch_logger):
    """Test FileOperations.move_file moves file to destination."""
    src = tmp_path / "source.txt"
    dst = install_dir / "dest.txt"
    src.write_text("hello", encoding="utf-8")

    service = FileOperations(install_dir)
    result = service.move_file(src, dst)

    assert result == dst
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "hello"
    assert not src.exists()


def test_make_executable_sets_mode(
    tmp_path: Path, install_dir: Path, patch_logger
):
    """Test FileOperations.make_executable sets executable mode."""
    file = tmp_path / "exec.txt"
    file.write_text("run", encoding="utf-8")
    service = FileOperations(install_dir)
    service.make_executable(file)
    assert file.stat().st_mode & 0o777 == 0o755


def test_move_file_overwrites_existing(
    tmp_path: Path, install_dir: Path, patch_logger
):
    """Test move_file overwrites destination if exists."""
    src = tmp_path / "src.txt"
    dst = install_dir / "dst.txt"
    src.write_text("new", encoding="utf-8")
    dst.write_text("old", encoding="utf-8")
    service = FileOperations(install_dir)
    result = service.move_file(src, dst)
    assert result == dst
    assert dst.read_text(encoding="utf-8") == "new"
    assert not src.exists()


def test_move_to_install_dir_renames(
    tmp_path: Path, install_dir: Path, patch_logger
):
    """Test move_to_install_dir moves and renames file."""
    src = tmp_path / "move.txt"
    src.write_text("abc", encoding="utf-8")
    service = FileOperations(install_dir)
    result = service.move_to_install_dir(src, filename="renamed.txt")
    assert result == install_dir / "renamed.txt"
    assert result.read_text(encoding="utf-8") == "abc"
    assert not src.exists()


def test_rename_file_changes_name(
    tmp_path: Path, install_dir: Path, patch_logger
):
    """Test rename_file renames file."""
    file = tmp_path / "old.txt"
    file.write_text("rename", encoding="utf-8")
    service = FileOperations(install_dir)
    new_path = service.rename_file(file, "new.txt")
    assert new_path.name == "new.txt"
    assert new_path.read_text(encoding="utf-8") == "rename"
    assert not file.exists()


def test_rename_appimage_adds_extension(
    tmp_path: Path, install_dir: Path, patch_logger
):
    """Test rename_appimage adds .AppImage extension if missing."""
    file = tmp_path / "app"
    file.write_text("img", encoding="utf-8")
    service = FileOperations(install_dir)
    new_path = service.rename_appimage(file, "renamed")
    assert new_path.name.endswith(".AppImage")
    assert new_path.read_text(encoding="utf-8") == "img"
    assert not file.exists()


def test_get_clean_appimage_name_removes_extension():
    """Test get_clean_appimage_name removes .AppImage extension."""
    service = FileOperations(Path("/tmp"))
    assert service.get_clean_appimage_name("foo.AppImage") == "foo"
    assert service.get_clean_appimage_name("bar.appimage") == "bar"
    assert service.get_clean_appimage_name("baz") == "baz"


def test_install_update_naming_consistency(
    tmp_path: Path, install_dir: Path, patch_logger
):
    """Test that install and update commands produce consistent AppImage naming."""
    service = FileOperations(install_dir)

    # Simulate what install command should do (after the fix)
    # 1. Move file to install directory
    original_file = tmp_path / "joplin-1.2.3.AppImage"
    original_file.write_text("appimage content", encoding="utf-8")

    # Step 1: Move to install dir (what install template does first)
    moved_file = service.move_to_install_dir(original_file)

    # Step 2: Apply renaming with .AppImage extension (what _handle_appimage_renaming does)
    clean_name = service.get_clean_appimage_name("joplin")
    final_file = service.rename_appimage(moved_file, clean_name)

    # Verify install produces .AppImage extension
    assert final_file.name == "joplin.AppImage"
    assert final_file.exists()
    assert final_file.read_text(encoding="utf-8") == "appimage content"

    # Simulate what update command would do
    # Create another version to "update" from
    old_file = install_dir / "joplin-old.AppImage"
    old_file.write_text("old content", encoding="utf-8")

    # Update command renaming (same logic as install now)
    clean_name_update = service.get_clean_appimage_name("joplin")
    updated_file = service.rename_appimage(old_file, clean_name_update)

    # Verify update also produces .AppImage extension
    assert updated_file.name == "joplin.AppImage"

    # Both install and update should produce the same naming pattern
    assert final_file.name == updated_file.name
    print(f"✅ Install and update both create: {final_file.name}")
