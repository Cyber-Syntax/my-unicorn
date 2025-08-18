from pathlib import Path
from unittest.mock import patch

import pytest

from my_unicorn.storage import StorageService


@pytest.fixture
def install_dir(tmp_path: Path) -> Path:
    """Provide a temporary install directory."""
    d = tmp_path / "install"
    d.mkdir()
    return d


@pytest.fixture
def patch_logger():
    """Patch get_logger to avoid real logging output."""
    with patch("my_unicorn.storage.get_logger") as mock_logger:
        yield mock_logger


def test_move_file_success(tmp_path: Path, install_dir: Path, patch_logger):
    """Test StorageService.move_file moves file to destination."""
    src = tmp_path / "source.txt"
    dst = install_dir / "dest.txt"
    src.write_text("hello", encoding="utf-8")

    service = StorageService(install_dir)
    result = service.move_file(src, dst)

    assert result == dst
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "hello"
    assert not src.exists()


def test_make_executable_sets_mode(tmp_path: Path, install_dir: Path, patch_logger):
    """Test StorageService.make_executable sets executable mode."""
    file = tmp_path / "exec.txt"
    file.write_text("run", encoding="utf-8")
    service = StorageService(install_dir)
    service.make_executable(file)
    assert file.stat().st_mode & 0o777 == 0o755


def test_move_file_overwrites_existing(tmp_path: Path, install_dir: Path, patch_logger):
    """Test move_file overwrites destination if exists."""
    src = tmp_path / "src.txt"
    dst = install_dir / "dst.txt"
    src.write_text("new", encoding="utf-8")
    dst.write_text("old", encoding="utf-8")
    service = StorageService(install_dir)
    result = service.move_file(src, dst)
    assert result == dst
    assert dst.read_text(encoding="utf-8") == "new"
    assert not src.exists()


def test_move_to_install_dir_renames(tmp_path: Path, install_dir: Path, patch_logger):
    """Test move_to_install_dir moves and renames file."""
    src = tmp_path / "move.txt"
    src.write_text("abc", encoding="utf-8")
    service = StorageService(install_dir)
    result = service.move_to_install_dir(src, filename="renamed.txt")
    assert result == install_dir / "renamed.txt"
    assert result.read_text(encoding="utf-8") == "abc"
    assert not src.exists()


def test_rename_file_changes_name(tmp_path: Path, install_dir: Path, patch_logger):
    """Test rename_file renames file."""
    file = tmp_path / "old.txt"
    file.write_text("rename", encoding="utf-8")
    service = StorageService(install_dir)
    new_path = service.rename_file(file, "new.txt")
    assert new_path.name == "new.txt"
    assert new_path.read_text(encoding="utf-8") == "rename"
    assert not file.exists()


def test_rename_appimage_adds_extension(tmp_path: Path, install_dir: Path, patch_logger):
    """Test rename_appimage adds .AppImage extension if missing."""
    file = tmp_path / "app"
    file.write_text("img", encoding="utf-8")
    service = StorageService(install_dir)
    new_path = service.rename_appimage(file, "renamed")
    assert new_path.name.endswith(".AppImage")
    assert new_path.read_text(encoding="utf-8") == "img"
    assert not file.exists()


def test_get_clean_appimage_name_removes_extension():
    """Test get_clean_appimage_name removes .AppImage extension."""
    service = StorageService(Path("/tmp"))
    assert service.get_clean_appimage_name("foo.AppImage") == "foo"
    assert service.get_clean_appimage_name("bar.appimage") == "bar"
    assert service.get_clean_appimage_name("baz") == "baz"


def test_remove_file_deletes(tmp_path: Path, install_dir: Path, patch_logger):
    """Test remove_file deletes file if exists."""
    file = tmp_path / "toremove.txt"
    file.write_text("bye", encoding="utf-8")
    service = StorageService(install_dir)
    service.remove_file(file)
    assert not file.exists()


def test_ensure_directory_creates(tmp_path: Path, install_dir: Path, patch_logger):
    """Test ensure_directory creates directory."""
    dir_path = tmp_path / "newdir"
    service = StorageService(install_dir)
    service.ensure_directory(dir_path)
    assert dir_path.exists()
    assert dir_path.is_dir()


def test_copy_file_copies_content(tmp_path: Path, install_dir: Path, patch_logger):
    """Test copy_file copies file content."""
    src = tmp_path / "src.txt"
    dst = install_dir / "dst.txt"
    src.write_text("copy", encoding="utf-8")
    service = StorageService(install_dir)
    result = service.copy_file(src, dst)
    assert result == dst
    assert dst.read_text(encoding="utf-8") == "copy"
    assert src.exists()


def test_cleanup_download_removes_if_different(
    tmp_path: Path, install_dir: Path, patch_logger
):
    """Test cleanup_download removes download if different from install."""
    download = tmp_path / "download.txt"
    install = install_dir / "install.txt"
    download.write_text("dl", encoding="utf-8")
    install.write_text("inst", encoding="utf-8")
    service = StorageService(install_dir)
    service.cleanup_download(download, install)
    assert not download.exists()
    assert install.exists()


def test_storage_error_exception():
    """Test StorageError can be raised and caught."""
    from my_unicorn.storage import StorageError

    try:
        raise StorageError("fail")
    except StorageError as e:
        assert str(e) == "fail"
